"""SC6 正式 runner（L13 §10 control/runs.py SC6 块；REV-0009 R9 三点保真度）。

断言：①regime 网格继承（世界布局随 sealed 单元 regime 分化）；②naive 断连经
fault 机制（fault_missing_signal；两臂共享 round1 记忆库）；③ITT 冻结流驱动臂
身份（确定性 + 按分配记账）+ recorder 四分区落盘 + I1 bit-exact + P12 数据探针通过。
"""
from pathlib import Path

import pytest

from galatea.env.world.mw0 import MW0World
from galatea.evidence.control.runs import (
    ExperimentRunControl,
    SubjectTrialRunner,
    _derive_regime_profile,
    load_sc6_scenario,
)
from galatea.evidence.evaluator.leakage import run_leakage_suite
from galatea.evidence.evaluator.sealed import GridCell, generate_split, load_split_policy
from galatea.kernel.rng import RngDirectory, chacha8_block

_ROOT = Path(__file__).resolve().parents[3]
_M2_PLAN = _ROOT / "config" / "evidence" / "stat_plans" / "m2_continuity_sc5_sc6.yaml"
_SPLIT_SEED = bytes.fromhex("19" * 32)   # Q-L13-11 ③ 冻结常数


def _sealed_cells() -> tuple[GridCell, ...]:
    policy = load_split_policy(_ROOT)
    cells = tuple(
        GridCell(cell_id=f"{r}:{i}", regime=r, seed_index=i)
        for r in ("abundance", "scarcity", "volatile")
        for i in range(32)
    )
    return generate_split(cells, _SPLIT_SEED, policy).sealed.cells


def _control(tmp_path: Path) -> ExperimentRunControl:
    return ExperimentRunControl(
        SubjectTrialRunner(_ROOT, tmp_path / "runner-tmp"), master_seed=b"m2-carryover-sealed"
    )


def test_sealed_grid_has_cells() -> None:
    cells = _sealed_cells()
    assert 15 <= len(cells) <= 45   # 96 cells × 名义 30%（粗界）
    assert {c.regime for c in cells} <= {"abundance", "scarcity", "volatile"}


def test_regime_inheritance_changes_world_layout(tmp_path: Path) -> None:
    """保真度①：regime 继承真实参数化世界（布局密度随 regime 分化，非标签装饰）。"""
    profile = SubjectTrialRunner(_ROOT, tmp_path / "probe").mw0_profile
    worlds = {}
    for regime in ("abundance", "scarcity", "volatile"):
        derived = _derive_regime_profile(profile, regime)
        worlds[regime] = MW0World(derived.params, RngDirectory(b"regime-probe", chacha8_block), branch_id="B")
    assert worlds["abundance"].state_digest() != worlds["scarcity"].state_digest()
    coverage = {r: worlds[r].coverage() for r in worlds}
    assert coverage["abundance"] > coverage["scarcity"]   # 冻结密度 0.35 vs 0.10
    scenario = load_sc6_scenario(_M2_PLAN)
    assert (scenario.round1_cycles, scenario.round2_cycles, scenario.fault_from) == (56, 12, 4)


def test_run_carryover_pair_mechanics(tmp_path: Path) -> None:
    """两配对端到端：携带臂知晓 / naive 经 fault 断连失明；I1 match；recorder 落盘。"""
    control = _control(tmp_path)
    evaluation = control.run_carryover(
        _sealed_cells(), tmp_path / "run", _M2_PLAN, split_digest="0" * 64, n_limit=2
    )
    assert len(evaluation.pairs) == 2
    for record in evaluation.pairs:
        assert record.carry_aware is True
        assert record.naive_aware is False
        assert record.carry_mode == "retrieved"
        assert record.naive_mode == "fault_missing_signal"    # 保真度②：断连 = fault 机制
        assert record.memory_items_digest                     # 两臂共享 round1 记忆库
        assert record.intero_blocked_ok is True               # 感知退化核验
        assert record.regime in {"abundance", "scarcity", "volatile"}   # 保真度①
    assert evaluation.i1_match is True
    assert evaluation.recompute_ok is True
    assert set(dict(evaluation.recorder_refs)) >= {
        "manifest", "trace", "metrics", "evidence", "run_manifest"
    }


def test_run_carryover_itt_stream_deterministic(tmp_path: Path) -> None:
    """保真度③：同 master 种子 → 同分配序列 + 同配对记录（重放恒等）。"""
    cells = _sealed_cells()
    a = _control(tmp_path).run_carryover(cells, tmp_path / "a", _M2_PLAN, "0" * 64, n_limit=2)
    b = _control(tmp_path).run_carryover(cells, tmp_path / "b", _M2_PLAN, "0" * 64, n_limit=2)
    assert [r.assigned_arm for r in a.pairs] == [r.assigned_arm for r in b.pairs]
    assert [r.digest for r in a.pairs] == [r.digest for r in b.pairs]
    assert a.assignment_balance == b.assignment_balance


def test_p12_data_probe_passes_on_formal_trace(tmp_path: Path) -> None:
    """正式 runner 的 trace 行经 P12 探针（两臂记忆 digest 恒等 + 断连机制）→ 无检出。"""
    evaluation = _control(tmp_path).run_carryover(
        _sealed_cells(), tmp_path / "run", _M2_PLAN, "0" * 64, n_limit=2
    )
    trace_rows: list[dict[str, object]] = []
    for record in evaluation.pairs:
        trace_rows.extend(record.trace_rows())
    report = run_leakage_suite({}, trace_rows)   # type: ignore[arg-type]
    assert report.leakage_free, [d.detail for d in report.detections]


def test_n_limit_never_exceeds_frozen_plan(tmp_path: Path) -> None:
    """n_limit 为测试截断 affordance：正式评价不传（n = 计划冻结值）。"""
    control = _control(tmp_path)
    with pytest.raises(ValueError):
        control.run_carryover(_sealed_cells(), tmp_path / "run", _M2_PLAN, "0" * 64, n_limit=0)
