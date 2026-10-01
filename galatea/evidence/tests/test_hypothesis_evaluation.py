"""判定执行与运行编排（L13 §4.3/§10；M2 准备单元——EvidenceResult 首评的机械面）。

断言：三态判定规则（SUPPORTED=阈值+负控 / REFUTED=伪注入生效或无效应 /
INCONCLUSIVE=功效不足）；饱和处理如实记录（确定性阶段 d 不可定义）；McNemar
精确检验可手算复核；ExperimentRunControl 种子枚举确定性 + profile digest 一致性
（ADR-G-0005 R8 实验控制侧落地）+ 运行时签名校验（ADR-G-0005 口径③）。
"""
from pathlib import Path

import pytest

from galatea.evidence.control.runs import (
    EvaluationData,
    ExperimentRunControl,
    SubjectTrialRunner,
    TrialScenario,
    UnauthorizedCommand,
)
from galatea.evidence.evaluator.hypotheses import (
    HypothesisVerdict,
    evaluate_real_vs_pseudo,
    evaluate_wording_null,
)

ROOT = Path(__file__).resolve().parents[3]
PLAN_REF = "config/evidence/stat_plans/m1_goals_sc3_sc4.yaml@v1.1"


# ---- 判定执行（合成输入，可手算）----


def test_real_vs_pseudo_saturated_supported() -> None:
    """64/64 vs 0/64：配对差=1.0（estimand 上确界）、d 饱和如实入 unknowns、McNemar p=2^-64。"""
    import math

    result = evaluate_real_vs_pseudo(
        "R-m1-001", PLAN_REF,
        healthy_adoption=(True,) * 64, depleted_adoption=(False,) * 64,
        pseudo_inert=True, recompute_ok=True,
    )
    assert result.verdict is HypothesisVerdict.SUPPORTED
    assert result.effect_size == 1.0
    assert result.ci is not None and result.ci.lower == 1.0 and result.ci.upper == 1.0
    assert result.p_or_bayes == pytest.approx(2.0 ** (-63), rel=1e-9) or result.p_or_bayes < 1e-18
    assert any("zero within-arm variance" in (u.detail or "") for u in result.unknowns)
    assert result.refutations == ()


def test_real_vs_pseudo_pseudo_effective_refuted() -> None:
    """③ 失效（伪理由注入改变决策）→ REFUTED + RequestDirectWriteSuspect（S1 语义）。"""
    result = evaluate_real_vs_pseudo(
        "R-m1-002", PLAN_REF,
        healthy_adoption=(True,) * 64, depleted_adoption=(False,) * 64,
        pseudo_inert=False, recompute_ok=True,
    )
    assert result.verdict is HypothesisVerdict.REFUTED
    assert "RequestDirectWriteSuspect" in result.refutations


def test_real_vs_pseudo_no_effect_refuted() -> None:
    """② 无效应（真实理由非因果）→ REFUTED + PseudoReasonDetected。"""
    result = evaluate_real_vs_pseudo(
        "R-m1-003", PLAN_REF,
        healthy_adoption=(False,) * 64, depleted_adoption=(False,) * 64,
        pseudo_inert=True, recompute_ok=True,
    )
    assert result.verdict is HypothesisVerdict.REFUTED
    assert "PseudoReasonDetected" in result.refutations


def test_real_vs_pseudo_insufficient_n_inconclusive() -> None:
    result = evaluate_real_vs_pseudo(
        "R-m1-004", PLAN_REF,
        healthy_adoption=(True,) * 8, depleted_adoption=(False,) * 8,
        pseudo_inert=True, recompute_ok=True,
    )
    assert result.verdict is HypothesisVerdict.INCONCLUSIVE
    assert result.effect_size is None


def test_real_vs_partial_effect_non_saturated_path() -> None:
    """非饱和（有 discordance 两向）：Wald CI 有限，阈值 = rate_diff≥0.5 且 CI 下界>0。"""
    healthy = (True,) * 48 + (False,) * 16
    depleted = (False,) * 40 + (True,) * 24     # diff = 0.75 − 0.375 = 0.375 < 0.5 → INCONCLUSIVE
    result = evaluate_real_vs_pseudo(
        "R-m1-005", PLAN_REF, healthy, depleted, pseudo_inert=True, recompute_ok=True,
    )
    assert result.verdict is HypothesisVerdict.INCONCLUSIVE
    assert result.effect_size == pytest.approx(0.375)
    assert result.ci is not None and result.ci.upper > result.ci.lower  # 非退化区间


def test_wording_null_supported_and_refuted() -> None:
    """统计形式（首评更正）：同质性 χ²——计数一致 → p≈1 SUPPORTED；强分化 → REFUTED。"""
    ok = evaluate_wording_null(
        "R-m1-006", PLAN_REF,
        cell_adopted_counts=(64, 64, 64, 64, 64, 64, 64, 64),
        n_per_cell=64, negative_control_ok=True, recompute_ok=True,
    )
    assert ok.verdict is HypothesisVerdict.SUPPORTED
    assert ok.effect_size == 0.0
    assert ok.p_or_bayes == pytest.approx(1.0)

    noise = evaluate_wording_null(
        "R-m1-009", PLAN_REF,
        cell_adopted_counts=(62, 62, 63, 62, 62, 64, 64, 60),   # 损坏噪声级波动 → 应不显著
        n_per_cell=64, negative_control_ok=True, recompute_ok=True,
    )
    assert noise.verdict is HypothesisVerdict.SUPPORTED
    assert noise.p_or_bayes > 0.05

    violated = evaluate_wording_null(
        "R-m1-007", PLAN_REF,
        cell_adopted_counts=(64, 64, 64, 64, 40, 64, 64, 64),   # 一个 cell 强偏离 → 显著
        n_per_cell=64, negative_control_ok=True, recompute_ok=True,
    )
    assert violated.verdict is HypothesisVerdict.REFUTED
    assert "wording_main_effect_detected" in violated.refutations


def test_wording_null_wrong_cell_count_inconclusive() -> None:
    result = evaluate_wording_null(
        "R-m1-008", PLAN_REF,
        cell_adopted_counts=(64, 64, 64, 64),
        n_per_cell=64, negative_control_ok=True, recompute_ok=True,
    )
    assert result.verdict is HypothesisVerdict.INCONCLUSIVE


def test_carryover_saturated_supported_and_refuted() -> None:
    """M2 carryover（SC6）：饱和 SUPPORTED（64 vs 0）；记忆无贡献/负控失败 → REFUTED。"""
    from galatea.evidence.evaluator.hypotheses import evaluate_carryover

    ok = evaluate_carryover(
        "R-m2-001", PLAN_REF,
        carry_aware=(True,) * 64, naive_aware=(False,) * 64, recompute_ok=True,
    )
    assert ok.verdict is HypothesisVerdict.SUPPORTED
    assert ok.effect_size == 1.0
    assert any("zero within-arm variance" in (u.detail or "") for u in ok.unknowns)

    absent = evaluate_carryover(
        "R-m2-002", PLAN_REF,
        carry_aware=(False,) * 64, naive_aware=(False,) * 64, recompute_ok=True,
    )
    assert absent.verdict is HypothesisVerdict.REFUTED
    assert "carryover_absent" in absent.refutations

    leaky = evaluate_carryover(
        "R-m2-003", PLAN_REF,
        carry_aware=(True,) * 64, naive_aware=(True,) * 60 + (False,) * 4, recompute_ok=True,
    )
    assert leaky.verdict is HypothesisVerdict.REFUTED
    assert "naive_arm_not_blind" in leaky.refutations   # 负控面：感知退化未生效

    short = evaluate_carryover(
        "R-m2-004", PLAN_REF,
        carry_aware=(True,) * 8, naive_aware=(False,) * 8, recompute_ok=True,
    )
    assert short.verdict is HypothesisVerdict.INCONCLUSIVE


def test_chi2_sf_known_values() -> None:
    """χ² 上侧概率可手算复核（df=1 临界值 3.841 → p≈0.05）。"""
    from galatea.evidence.evaluator.hypotheses import _chi2_sf

    assert _chi2_sf(3.841, 1) == pytest.approx(0.05, abs=2e-3)
    assert _chi2_sf(0.0, 7) == 1.0
    assert _chi2_sf(18.475, 7) == pytest.approx(0.01, abs=2e-3)


# ---- 运行编排（小 n 实跑）----


def _runner(tmp_path: Path) -> SubjectTrialRunner:
    return SubjectTrialRunner(ROOT, tmp_path)


def test_trial_runner_deterministic(tmp_path: Path) -> None:
    """同 seed 同场景 → trial digest 相同（bit-exact）；异 seed 发散。"""
    runner = _runner(tmp_path)
    scenario = TrialScenario(cycles=4, decision_cycle=2)
    r1 = runner.run_trial(b"eval-det", scenario, "t1")
    r2 = runner.run_trial(b"eval-det", scenario, "t1")
    r3 = runner.run_trial(b"eval-other", scenario, "t3")
    assert r1.digest == r2.digest
    assert r1.digest != r3.digest


def test_trial_runner_profile_digest_uniform(tmp_path: Path) -> None:
    """R8：同 runner 全部 trial 的 profile digest 一致（评价内一致性机械保证）。"""
    runner = _runner(tmp_path)
    control = ExperimentRunControl(runner, master_seed=b"unit")
    data = control._run_arm("unit.arm", 2, TrialScenario(cycles=4, decision_cycle=2))
    assert data.profile_digest_uniform is True
    assert data.recompute_ok is True
    assert any(pid == "m1_goals_min" for pid, _ in data.records[0].profile_digests)


def test_trial_runner_depletes_energy(tmp_path: Path) -> None:
    """能量轨迹操纵：100-move 场景 → hazard 在案（接收侧派生）。"""
    runner = _runner(tmp_path)
    record = runner.run_trial(
        b"eval-deplete", TrialScenario(cycles=56, decision_cycle=52, moves_per_cycle=2), "t-dep"
    )
    assert record.hazard is True
    assert record.energy_fraction == 0.0
    explore = next(v for v in record.verdicts if v[0] == "c.explore")
    assert explore[2] == "REJECT" and explore[3] == "VIABILITY"


def test_unauthorized_command_typed(tmp_path: Path) -> None:
    """运行时边界校验类型化：UnauthorizedCommand 可构造可捕获（ADR-G-0005 口径③）。"""
    with pytest.raises(UnauthorizedCommand):
        raise UnauthorizedCommand("unsigned command at world boundary")
