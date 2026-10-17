"""p4_beta_mind profile typed loader fail-closed 测试（INC-11 纪律）。

正向：v1.1 冻结值逐项装载（慢环阈值锚既有常数/收敛操作化/GCTB 判据数值）。
负向：torch 版本漂移拒（pending 认证态下 CUDA 版本不放行——Q-T02 补裁③ 门）/缺键拒。
临时 profile 一律 mkdtemp（INC-13 清理纪律）。
"""
from pathlib import Path

import pytest
import yaml

from galatea.subject.p4profile import P4AlphaProfileViolation, load_p4_beta_profile

_ROOT = Path(__file__).resolve().parents[3]


def _temp_profile(tmp_path: Path, mutate) -> Path:
    doc = yaml.safe_load((_ROOT / "config/profiles/p4_beta_mind.profile.yaml").read_text(encoding="utf-8"))
    mutate(doc)
    out = tmp_path / "p4_beta_mind.profile.yaml"
    out.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return out


def test_loads_frozen_v1_1_values() -> None:
    p = load_p4_beta_profile()
    assert p.hypothesis_schema == "DraftHypothesis"
    assert p.status_vocabulary == ("open", "evaluated", "superseded", "contradicted")
    assert p.non_belief_principle is True
    assert p.loop_beats == ("generate", "evaluate", "contradict", "revise")
    assert p.think_steps_budget == 8
    assert p.convergence_mode == "no_new_successor"
    assert p.arousal_low == 0.1 and p.urgency_idle == 0.0 and p.check_interval_cycles == 1
    assert p.two_step_trials == 120 and p.two_step_reversal == 60
    assert p.criterion_separation == 0.01 and p.criterion_dominance == 0.5
    assert p.optout_safe_harbor == 0.3
    assert p.device_cert_status == "certified_cuda"   # v1.2 认证翻转
    assert p.cublas_workspace_config == ":4096:8"


def test_torch_version_drift_rejected(tmp_path: Path) -> None:
    """torch 漂移 + pending 认证态 → 拒（认证路径需 certified_cuda + CUBLAS 冻结值）。"""
    path = _temp_profile(tmp_path, lambda d: d["determinism"].__setitem__(
        "torch_version", "9.9.9+cpu"))
    with pytest.raises(P4AlphaProfileViolation, match="torch runtime"):
        load_p4_beta_profile(path)


def test_cuda_version_pending_status_rejected(tmp_path: Path, monkeypatch) -> None:
    """CUDA venv + 认证态未翻转 → 拒（正式认证前置——冒烟绿 ≠ 认证绿）。"""
    import torch

    monkeypatch.setenv("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    monkeypatch.setattr(torch, "__version__", "2.14.1+cu130")

    def mutate(d: dict) -> None:
        # frozen 保持 CPU 值；runtime 被桩为 cu130 → 走认证路径 → pending 态必须拦
        d["determinism"]["device_certification"]["status"] = "pending_probe_layer_a_rerun"

    with pytest.raises(P4AlphaProfileViolation, match="certified_cuda"):
        load_p4_beta_profile(_temp_profile(tmp_path, mutate))


def test_cuda_certified_path_accepted(tmp_path: Path, monkeypatch) -> None:
    """认证态翻转 + CUDA 运行时 + CUBLAS 冻结值 → CUDA 路径放行（Q-T02 补裁③）。"""
    import torch

    monkeypatch.setenv("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    monkeypatch.setattr(torch, "__version__", "2.14.1+cu130")
    p = load_p4_beta_profile()          # v1.2 已翻转 certified_cuda——真实 profile 直载
    assert p.torch_version == "2.14.1+cu130"
    assert p.device_cert_status == "certified_cuda"
    # CUBLAS 环境变量缺失/错值 → 同态仍拒（三项合同逐字校验）
    monkeypatch.delenv("CUBLAS_WORKSPACE_CONFIG")
    with pytest.raises(P4AlphaProfileViolation, match="certified_cuda"):
        load_p4_beta_profile()


def test_missing_key_rejected(tmp_path: Path) -> None:
    path = _temp_profile(tmp_path, lambda d: d["slow_clock"].pop("arousal_low"))
    with pytest.raises(P4AlphaProfileViolation, match="arousal_low"):
        load_p4_beta_profile(path)


def test_status_vocabulary_drift_rejected(tmp_path: Path) -> None:
    path = _temp_profile(tmp_path, lambda d: d["scratchpad"].__setitem__(
        "status_vocabulary", ["open", "believed"]))
    with pytest.raises(P4AlphaProfileViolation, match="status_vocabulary"):
        load_p4_beta_profile(path)
