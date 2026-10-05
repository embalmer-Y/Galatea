"""C1 评价 runner 端到端回归（REV-0014 R1③：runner 取包路径零覆盖缺口——INC-08 纪律）。

REV-0014 R1（S1）教训：test_stack_bit_exact 以手工文本包驱动 sensorium，从不经过
C1ModelsRunner 的 registry 取包路径——`str(bytes)` 序列化回归使提交态 runner 全包
判损坏（零帧崩止）而无任何测试拦截。本测试经**真实 registry blob 取包路径**全链
运行，断言窗口成帧 > 0（对被检对象可见且能失败）。
"""
import math
from pathlib import Path

import pytest

from galatea.evidence.control.runs_c1 import (
    C1ModelsRunner,
    _EVAL_MASTER_SEED_C1,
    _trial_seed,
    c1_accuracy_diffs,
    c1_criterion_diffs,
    c1_ece_samples,
    c1_world_mse_diffs,
    load_c1_scenario,
)

_ROOT = Path(__file__).resolve().parents[3]
_PLAN = _ROOT / "config" / "evidence" / "stat_plans" / "c1_perception_models.yaml"


def test_runner_produces_frames_through_real_registry_path(tmp_path: Path) -> None:
    """真实 registry blob 路径全链：runner 单 run 必须成帧（R1 回归拦截面）。"""
    runner = C1ModelsRunner(_ROOT, tmp_path)
    scenario = load_c1_scenario(_PLAN)
    record = runner.run_trial(
        _trial_seed(_EVAL_MASTER_SEED_C1, 0), scenario, "e2e#0", "abundance:0"
    )
    # REV-0014 R1 断言：成帧必须发生（回归态 formation=(0,0,0) 即在此拦截）
    assert record.formation_counts[0] > 0, "runner produced zero frames（R1 序列化回归面）"
    assert record.formation_counts[0] == record.formation_counts[1] == record.formation_counts[2]
    assert len(record.window_rows) > 0
    # 可复算性：同 (seed, cell, scenario) 双跑 digest bit-exact
    replay = C1ModelsRunner(_ROOT, tmp_path / "replay").run_trial(
        _trial_seed(_EVAL_MASTER_SEED_C1, 0), scenario, "e2e#0", "abundance:0"
    )
    assert replay.digest == record.digest


def test_evaluation_orchestration_end_to_end(tmp_path: Path) -> None:
    """run_c1_evaluation 最小编排（n=2）：指标有限、I1、解离机械断言全过。"""
    from galatea.evidence.control.runs_c1 import run_c1_evaluation
    from galatea.evidence.evaluator.sealed import GridCell, generate_split, load_split_policy
    from galatea.evidence.control.runs import seal_split_master_seed

    grid = tuple(
        GridCell(cell_id=f"{r}:{i}", regime=r, seed_index=i)
        for r in ("abundance", "scarcity", "volatile")
        for i in range(32)
    )
    split = generate_split(grid, seal_split_master_seed(), load_split_policy(_ROOT))
    records, mechanical, plan_digest, split_digest, i1 = run_c1_evaluation(
        _ROOT, tmp_path / "run", tmp_path / "runner-tmp", split.sealed.cells,
        _PLAN, split.split_digest, n_limit=2,
    )
    assert len(records) == 2
    assert i1 is True
    assert all(mechanical.values()), mechanical
    assert all(r.formation_counts[0] > 0 for r in records)
    # 指标有限性（I1 复算共用核可运行）
    acc = c1_accuracy_diffs(records)
    mse = c1_world_mse_diffs(records, load_c1_scenario(_PLAN))
    crit1, crit2, crit3 = c1_criterion_diffs(records, load_c1_scenario(_PLAN))
    assert all(math.isfinite(x) for x in acc + mse + crit1 + crit2 + crit3)
    assert len(c1_ece_samples(records)) > 0
    assert plan_digest and split_digest
