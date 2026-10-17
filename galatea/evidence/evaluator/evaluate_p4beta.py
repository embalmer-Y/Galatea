"""P4-β 三 claim 判定器（stat plan p4_beta_mind v1.0 冻结承载；GCTB P4-β 子集）。

- two_step_dissociation：配对种子 Wald 检验（MB − habit 调节差）+ 冻结双阈值
  （sep > 0.01 ∧ dominance > 0.5）——门判据核心（Q-L13-21①）；
- optout_economy：单臂 Wald（增益均值 > 0，单侧）；
- think_first_advantage：确定性门（全 included seeds TFA ∧ 矛盾开火；资源不足
  seed 剔除留痕为合法 unknown 形态——stat plan unknown_handling）；
- 复合 = Holm 族 3 claim + leakage=0 + I1（evaluate_c1_composite 体例；
  statistical_core = two_step——Q-L13-21① 门判据核心）。
"""
from __future__ import annotations

import math
from typing import Any

from galatea.kernel.unknown import Unknown, UnknownReason
from galatea.evidence.evaluator.hypotheses import (
    ConfidenceInterval,
    EvidenceResult,
    HypothesisVerdict,
    evaluate_c1_composite,
)

_Z_95 = 1.959963984540054


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _one_sided_p(mean: float, sd: float, n: int) -> float:
    """单侧 Wald p（H1: mean > 0；sd=0 且 mean>0 → 饱和 p=0）。"""
    if n < 2:
        raise ValueError("Wald requires n≥2")
    if sd == 0.0:
        return 0.0 if mean > 0 else (1.0 if mean < 0 else 1.0)
    se = sd / math.sqrt(n)
    return max(0.0, min(1.0, 1.0 - _normal_cdf(mean / se)))


def _paired_stats(a: tuple[float, ...], b: tuple[float, ...]) -> tuple[float, float, int]:
    diffs = [x - y for x, y in zip(a, b)]
    n = len(diffs)
    mean = sum(diffs) / n
    var = sum((d - mean) ** 2 for d in diffs) / (n - 1)
    return mean, math.sqrt(var), n


def evaluate_p4beta_two_step(result_id: str, stat_plan_ref: str,
                             mb: tuple[float, ...], habit: tuple[float, ...],
                             separation_threshold: float, dominance_threshold: float,
                             data_ref: str,
                             detected_by: str = "evidence.evaluator") -> EvidenceResult:
    """claim1 p4_beta_two_step_dissociation（配对种子比较 + v2 重冻双阈值——Q-L13-22 α）。"""
    if len(mb) != len(habit) or len(mb) < 2:
        raise ValueError("two_step requires equal-length paired sequences n≥2")
    mean, sd, n = _paired_stats(mb, habit)
    dominance = sum(1 for a, b in zip(mb, habit) if a > b) / n
    half = _Z_95 * sd / math.sqrt(n)
    sep_ok = mean > separation_threshold
    dom_ok = dominance > dominance_threshold
    passed = sep_ok and dom_ok
    p = _one_sided_p(mean, sd, n)
    return EvidenceResult(
        result_id=result_id, hypothesis_refs=("p4_beta_two_step_dissociation",),
        stat_plan_ref=stat_plan_ref,
        estimand="regression_interaction_separation_mb_minus_habit",
        effect_size=mean,
        ci=ConfidenceInterval(lower=mean - half, upper=mean + half, level=0.95),
        p_or_bayes=p,
        verdict=HypothesisVerdict.SUPPORTED if passed else HypothesisVerdict.REFUTED,
        unknowns=(),
        refutations=() if passed else tuple(filter(None, (
            None if sep_ok else f"separation {mean:.6f} <= frozen {separation_threshold}",
            None if dom_ok else f"dominance {dominance:.4f} <= frozen {dominance_threshold}"))),
        data_refs=(data_ref, f"dominance={dominance:.4f} sd={sd:.6f}"),
        recompute_ok=True,                       # 排序/差分统计量确定性重算
    )


def evaluate_p4beta_optout(result_id: str, stat_plan_ref: str,
                           gains: tuple[float, ...], data_ref: str,
                           detected_by: str = "evidence.evaluator") -> EvidenceResult:
    """claim2 p4_beta_optout_economy（增益均值 > 0，单侧 Wald）。"""
    n = len(gains)
    if n < 2:
        raise ValueError("optout requires n≥2")
    mean = sum(gains) / n
    var = sum((g - mean) ** 2 for g in gains) / (n - 1)
    sd = math.sqrt(var)
    half = _Z_95 * sd / math.sqrt(n)
    passed = mean > 0
    p = _one_sided_p(mean, sd, n)
    return EvidenceResult(
        result_id=result_id, hypothesis_refs=("p4_beta_optout_economy",),
        stat_plan_ref=stat_plan_ref,
        estimand="optout_economic_gain_vs_always_gamble",
        effect_size=mean,
        ci=ConfidenceInterval(lower=mean - half, upper=mean + half, level=0.95),
        p_or_bayes=p,
        verdict=HypothesisVerdict.SUPPORTED if passed else HypothesisVerdict.REFUTED,
        unknowns=(),
        refutations=() if passed else (f"mean gain {mean:.6f} <= 0",),
        data_refs=(data_ref, f"sd={sd:.6f}"),
        recompute_ok=True,
    )


def evaluate_p4beta_think_first(result_id: str, stat_plan_ref: str,
                                trials: tuple[dict[str, Any], ...], data_ref: str,
                                detected_by: str = "evidence.evaluator") -> EvidenceResult:
    """claim3 p4_beta_think_first_advantage（确定性门——TFA ∧ 矛盾开火，逐 trial）。"""
    included = [t for t in trials if t["included"]]
    excluded = [t for t in trials if not t["included"]]
    if not included:
        return EvidenceResult(
            result_id=result_id, hypothesis_refs=("p4_beta_think_first_advantage",),
            stat_plan_ref=stat_plan_ref,
            estimand="tfa_correction_on_trapped_scenario",
            effect_size=0.0,
            ci=ConfidenceInterval(lower=0.0, upper=0.0, level=1.0), p_or_bayes=1.0,
            verdict=HypothesisVerdict.INCONCLUSIVE,
            unknowns=(Unknown(reason=UnknownReason.INSUFFICIENT_OBSERVATION,
                             evidence_refs=(data_ref,), detail="all world seeds excluded",
                             detected_by=detected_by, virtual_time=0),),
            refutations=("all world seeds excluded（布局资源不足）",),
            data_refs=(data_ref,), recompute_ok=True)
    failures = [f"seed {t['index']}: tfa={t['tfa_corrected']} cx={t['contradiction_fired']}"
                f" without={t['without']} with={t['with']} true_best={t['true_best']}"
                for t in included if not (t["tfa_corrected"] and t["contradiction_fired"])]
    passed = not failures
    return EvidenceResult(
        result_id=result_id, hypothesis_refs=("p4_beta_think_first_advantage",),
        stat_plan_ref=stat_plan_ref,
        estimand="tfa_correction_on_trapped_scenario",
        effect_size=1.0 if passed else 0.0,
        ci=ConfidenceInterval(lower=1.0 if passed else 0.0, upper=1.0 if passed else 0.0, level=1.0),
        p_or_bayes=0.0 if passed else 1.0,
        verdict=HypothesisVerdict.SUPPORTED if passed else HypothesisVerdict.REFUTED,
        unknowns=tuple(
            Unknown(reason=UnknownReason.INSUFFICIENT_OBSERVATION,
                    evidence_refs=(f"think_first/{t['index']}",),
                    detail=str(t["exclusion_reason"]),
                    detected_by=detected_by, virtual_time=0)
            for t in excluded),
        refutations=tuple(failures),
        data_refs=(data_ref, f"excluded={len(excluded)}"),
        recompute_ok=True,                       # 机械门重算 = 同数据逐 trial 重判定
    )


def evaluate_p4beta_composite(result_id: str, stat_plan_ref: str,
                              two_step: EvidenceResult, optout: EvidenceResult,
                              think_first: EvidenceResult,
                              leakage_free: bool, i1_match: bool,
                              detected_by: str = "evidence.evaluator") -> EvidenceResult:
    """P4-β 复合（Holm 族 3 claim + leakage=0 + I1；statistical_core = two_step）。"""
    return evaluate_c1_composite(
        result_id, stat_plan_ref, (two_step, optout, think_first),
        mechanical_ok=True,
        leakage_free=leakage_free,
        i1_match=i1_match,
        recompute_ok=all(r.recompute_ok for r in (two_step, optout, think_first)),
        statistical_core=two_step,
        detected_by=detected_by,
        composite_label="p4_beta_mind",
    )
