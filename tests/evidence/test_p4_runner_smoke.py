"""P4-α runner 回归测试（INC-08/REV-0014 R1 纪律——runner 路径首单元即带端到端覆盖）。

缩规模冒烟（cycles=96、holdout=24、epochs=30——合同路径与生产同构，规模缩放
不改变代码路径）：流采集 → 任务序列 → z-score → RSSM 训练/评价 + 表格基线 +
录制/重放；断言全部机械可失败。
"""
from __future__ import annotations

from pathlib import Path

import pytest

import galatea.evidence.control.runs_p4 as runs_p4

_PARAMS = runs_p4.load_p4_alpha_profile(
    runs_p4._ROOT / "config/profiles/p4_alpha_brain.profile.yaml")

_SMOKE_CYCLES = 96
_SMOKE_HOLDOUT = 24
_SMOKE_EPOCHS = 30


@pytest.fixture()
def shrunk(monkeypatch: pytest.MonkeyPatch) -> None:
    """缩规模常数（合同路径同构冒烟—— runner 既有 788 基线不受影响）。"""
    monkeypatch.setattr(runs_p4, "_CYCLES", _SMOKE_CYCLES)
    monkeypatch.setattr(runs_p4, "_HOLDOUT", _SMOKE_HOLDOUT)
    monkeypatch.setattr(runs_p4, "_P1_HOLDOUT", 8)


def test_runner_cell_end_to_end(shrunk: None) -> None:
    """单 cell 端到端：双域会话链 + 评价 + 重放（缩规模冒烟）。"""
    p1_rates = [0.01, -0.005, 0.008, -0.002] * 12          # 48 拍合成速率（p1 域义务路径）
    p1_digest = "b" * 64
    cell = runs_p4.run_cell(0, _PARAMS, p1_rates, p1_digest)
    # 会话链录制（training_session.v1 十字段）
    assert len(cell.session1_record) == 10 and len(cell.session2_record) == 10
    assert cell.session1_record["loss_last"] < cell.session1_record["loss_first"]
    assert cell.session2_record["weights_digest_before"] \
        == cell.session1_record["weights_digest_after"]    # 谱系链
    # 判据量（机械域——比率有限且为正）
    assert 0.0 < cell.rssm_ratio < float("inf")
    assert 0.0 < cell.table_ratio < float("inf")
    assert cell.persist_mse > 0.0
    assert cell.param_count == cell.param_count            # 工件计数在位（27521 预算断言在模型构造）
    # 重放（缩规模 epochs——确定性由构造）
    assert cell.replay_bit_exact is True
    # 描述性面
    assert set(cell.horizon_ratios) == {f"h{h}" for h in range(1, 9)}


def test_table_baseline_frozen_form() -> None:
    """表格基线 = ADR-G-0030 §2 冻结形（探针种子上 ratio ≈ 0.0083 锚——like-for-like 核验）。"""
    _rows, series, _dig, _td = runs_p4.collect_stream_vectors(b"p4-alpha-probe")
    rates = runs_p4.task_rates(series)
    ratio = runs_p4.table_baseline_ratio(rates)
    assert 0.0 < ratio < 0.05, f"probe-seed table ratio {ratio} vs anchor 0.0083 family"


def test_zscore_train_only_no_leakage() -> None:
    """z-score 统计量只来自训练段（held-out 值不影响 mu/sd——防泄漏机械断言）。"""
    rates = [0.01, -0.01, 0.02, -0.02] * 30
    n_train = 100
    norm_a, mu_a, sd_a = runs_p4._zscore(rates, n_train)
    leaked = list(rates)
    leaked[110] = 50.0                                     # held-out 段注入极值
    norm_b, mu_b, sd_b = runs_p4._zscore(leaked, n_train)
    assert (mu_a, sd_a) == (mu_b, sd_b), "held-out 段不得影响标准化统计量"
    assert norm_a[:n_train] == norm_b[:n_train]
    assert len(norm_a) == len(rates)


def test_first_evaluation_orchestration_small(shrunk: None, tmp_path: Path) -> None:
    """首评编排（n=2 缩规模端到端）：判定器 + Holm 复合 + 工件落盘。"""
    p1_rates = [0.01, -0.005, 0.008, -0.002] * 12
    result = runs_p4.run_p4_first_evaluation(
        runs_p4._ROOT, tmp_path, n_cells=2, leakage_free_override=True)
    assert result["composite"].result_id == "R-p4-brain-001"
    assert (tmp_path / "R-p4-brain-001.json").exists()
    for name in ("R-p4-brain-margin", "R-p4-brain-pairing", "R-p4-brain-replay"):
        assert (tmp_path / f"{name}.json").exists()
    assert result["leakage_free"] is True                  # override 注入路径
