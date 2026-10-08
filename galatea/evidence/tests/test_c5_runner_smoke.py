"""C5 runner 冒烟（run 0 机械验证面；INC-08——runner 路径首单元即带覆盖）。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from galatea.evidence.control.runs_c5 import (
    C5Runner,
    _trial_seed,
    _EVAL_MASTER_SEED_C5,
    run_c5_evaluation,
)

_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def runner(tmp_path_factory: pytest.TempPathFactory) -> C5Runner:
    return C5Runner(_ROOT, tmp_path_factory.mktemp("c5run"))


def test_learning_beats_frozen_prior_on_coverage_tracking(runner: C5Runner) -> None:
    """scarcity 网格（真值 0.10 远离先验 0.35）：学习增益面；abundance（≈prior）= 无空间如实。"""
    seed = _trial_seed(_EVAL_MASTER_SEED_C5, 0)
    learn = runner.run_learning(seed, learn=True, regime="scarcity")
    nolearn = runner.run_learning(seed, learn=False, regime="scarcity")
    assert learn["consolidations"] == 2 and nolearn["consolidations"] == 0
    assert nolearn["posterior_resource"] == 0.35
    assert learn["world_digest_final"] == nolearn["world_digest_final"]   # 同流（D-10）
    truth = learn["truth_coverage"]
    assert abs(learn["posterior_resource"] - truth) < abs(0.35 - truth)   # 学习更近真值
    # abundance（真值≈prior）：学习无增益空间——观测截断偏差可致微劣，如实由统计聚合承载
    a_learn = runner.run_learning(seed, learn=True, regime="abundance")
    assert abs(a_learn["posterior_resource"] - a_learn["truth_coverage"]) <= 0.10   # 偏差带宽内


def test_learning_double_run_bit_exact(runner: C5Runner) -> None:
    seed = _trial_seed(_EVAL_MASTER_SEED_C5, 1)
    a = runner.run_learning(seed, learn=True, regime="volatile")
    b = runner.run_learning(seed, learn=True, regime="volatile")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_protection_scenario_gates(runner: C5Runner) -> None:
    s = runner.run_protection()
    assert s["harmful_proposal_rejected"]
    assert s["pending_cleared_on_rollback"]
    assert s["protection_result_unchanged"]


def test_correction_loop_closes(runner: C5Runner) -> None:
    s = runner.run_correction()
    assert s["correction_loop_four_steps"], s["steps"]
    assert s["original_resubmission_rejected"]


def test_evaluation_smoke_n2(tmp_path: Path) -> None:
    """run_c5_evaluation 端到端 n=2 冒烟（I1 + recorder 全链）。"""
    from galatea.evidence.evaluator.statplan import load_stat_plan
    plan_path = _ROOT / "config" / "evidence" / "stat_plans" / "c5_continued_learning.yaml"
    records, plan_digest, split_digest, i1 = run_c5_evaluation(
        _ROOT, tmp_path / "run", tmp_path / "tmp",
        sealed_cells=(type("C", (), {"cell_id": "abundance:0", "regime": "abundance"})(),
                       type("C", (), {"cell_id": "scarcity:1", "regime": "scarcity"})()),
        stat_plan_path=plan_path, split_digest="smoke", n_limit=2,
    )
    assert len(records) == 8   # 2 runs × 4 arms
    assert i1
    assert plan_digest and split_digest == "smoke"
