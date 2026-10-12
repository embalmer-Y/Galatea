"""P4-α 三 claim 判定器（stat plan p4_alpha v1.0 冻结承载；顺延终止条款第八次执行）。

- heldout_vs_persistence：median gate（64 cell 比率中位数 < 冻结阈 0.1——profile
  heldout_margin_vs_persistence 的多 cell 泛化操作化，stat plan 头部依据）；
- vs_table_baseline：配对对数比率差 Wald（mean d > 0 ∧ CI lower > 0——几何均值
  优越，Q-L04-12③ 表格基线 = ADR-G-0030 §2 线性冻结形）；
- training_replay_bit_exact：确定性门（64/64 重放恒等 + 谱系链 + 十字段——
  Q-L13-20① 宪法语义，I1 = 本判据）。
- 复合 = evaluate_c1_composite 体例（Holm 族 = 3 claim 主判定 p，REV-0014 R3
  机械执行；leakage=0 + I1 + recompute 前置；statistical_core = margin claim）。
"""
from __future__ import annotations

import math

from galatea.evidence.evaluator.hypotheses import (
    ConfidenceInterval,
    EvidenceResult,
    HypothesisVerdict,
    evaluate_c1_composite,
)


def _gate_claim(result_id: str, stat_plan_ref: str, claim_id: str, estimand: str,
                gates: dict[str, bool], data_ref: str, recompute_ok: bool,
                detected_by: str = "evidence.evaluator") -> EvidenceResult:
    """确定性门 claim 通用体（evaluate_p1._gate_claim 同式）。"""
    passed = all(gates.values())
    return EvidenceResult(
        result_id=result_id, hypothesis_refs=(claim_id,),
        stat_plan_ref=stat_plan_ref, estimand=estimand,
        effect_size=1.0 if passed else 0.0,
        ci=ConfidenceInterval(lower=1.0 if passed else 0.0, upper=1.0 if passed else 0.0, level=1.0),
        p_or_bayes=0.0 if passed else 1.0,
        verdict=HypothesisVerdict.SUPPORTED if passed else HypothesisVerdict.REFUTED,
        unknowns=(),
        refutations=tuple(f"gate {name} failed" for name, ok in gates.items() if not ok),
        data_refs=(data_ref,),
        recompute_ok=recompute_ok,
    )


def evaluate_p4_margin_median(result_id: str, stat_plan_ref: str,
                              ratios: tuple[float, ...], margin: float,
                              detected_by: str = "evidence.evaluator") -> EvidenceResult:
    """claim1 p4_alpha_heldout_vs_persistence（median gate——冻结阈多 cell 泛化）。"""
    ordered = sorted(ratios)
    n = len(ordered)
    mid = n // 2
    median = ordered[mid] if n % 2 == 1 else (ordered[mid - 1] + ordered[mid]) / 2.0
    passed = median < margin
    return EvidenceResult(
        result_id=result_id, hypothesis_refs=("p4_alpha_heldout_vs_persistence",),
        stat_plan_ref=stat_plan_ref,
        estimand="median_per_cell_heldout_mse_ratio_vs_persistence",
        effect_size=median,
        ci=ConfidenceInterval(lower=ordered[0], upper=ordered[-1], level=0.95),
        p_or_bayes=0.0 if passed else 1.0,
        verdict=HypothesisVerdict.SUPPORTED if passed else HypothesisVerdict.REFUTED,
        unknowns=(),
        refutations=() if passed else (
            f"median ratio {median:.6f} >= frozen margin {margin}",),
        data_refs=(f"n_cells={n} mean={sum(ordered) / n:.6f} "
                   f"min={ordered[0]:.6f} max={ordered[-1]:.6f}",),
        recompute_ok=True,                       # 比率确定性重算（median = 排序统计量）
    )


def evaluate_p4_table_pairing(result_id: str, stat_plan_ref: str,
                              rssm_ratios: tuple[float, ...],
                              table_ratios: tuple[float, ...],
                              detected_by: str = "evidence.evaluator") -> EvidenceResult:
    """claim2 p4_alpha_vs_table_baseline（配对对数比率差 Wald——几何均值优越）。

    d_i = ln(table_ratio_i) − ln(rssm_ratio_i)；截断 10 = ln 域有限性防御面
    （stat plan unknown_handling 冻结；实测比率有限）。
    """
    if len(rssm_ratios) != len(table_ratios) or not rssm_ratios:
        raise ValueError("paired arms must be non-empty and equal length")

    def _log_floor(value: float) -> float:
        bounded = min(value, 10.0)
        return math.log(max(bounded, 1e-12))

    diffs = tuple(_log_floor(t) - _log_floor(r) for r, t in zip(rssm_ratios, table_ratios))
    n = len(diffs)
    mean = sum(diffs) / n
    var = sum((d - mean) ** 2 for d in diffs) / (n - 1) if n > 1 else 0.0
    se = math.sqrt(var / n)
    z = 1.959963984540054
    lower, upper = mean - z * se, mean + z * se
    passed = mean > 0.0 and lower > 0.0
    # p = 单侧 Wald（mean > 0）
    p = 1.0 - 0.5 * (1.0 + math.erf(mean / se / 2.0 ** 0.5)) if se > 0 else (0.0 if mean > 0 else 1.0)
    return EvidenceResult(
        result_id=result_id, hypothesis_refs=("p4_alpha_vs_table_baseline",),
        stat_plan_ref=stat_plan_ref,
        estimand="paired_log_ratio_difference_vs_frozen_table_baseline",
        effect_size=mean,
        ci=ConfidenceInterval(lower=lower, upper=upper, level=0.95),
        p_or_bayes=max(p, 0.0),
        verdict=HypothesisVerdict.SUPPORTED if passed else HypothesisVerdict.REFUTED,
        unknowns=(),
        refutations=() if passed else (
            f"paired log-diff mean {mean:.6f} CI [{lower:.6f}, {upper:.6f}] "
            "not positive-above-zero",),
        data_refs=(f"n_cells={n} wins={sum(1 for d in diffs if d > 0)}/{n}",),
        recompute_ok=True,
    )


def evaluate_p4_dual_domain_gate(result_id: str, stat_plan_ref: str,
                                 lineage_ok: tuple[bool, ...],
                                 schema_ok: tuple[bool, ...],
                                 detected_by: str = "evidence.evaluator") -> EvidenceResult:
    """claim2 p4_alpha_dual_domain_training_delivered（确定性门——Q-L04-12② 双源义务）。"""
    return _gate_claim(
        result_id, stat_plan_ref, "p4_alpha_dual_domain_training_delivered",
        "dual_domain_training_deterministic_assertions",
        {
            "all_cells_dual_sessions_executed": all(lineage_ok) and all(schema_ok),
            "lineage_chain_continuous": all(lineage_ok),
            "record_schema_complete": all(schema_ok),
        },
        data_ref=f"n_cells={len(lineage_ok)}",
        recompute_ok=True,
        detected_by=detected_by,
    )


def evaluate_p4_replay_gate(result_id: str, stat_plan_ref: str,
                            replay_ok: tuple[bool, ...],
                            detected_by: str = "evidence.evaluator") -> EvidenceResult:
    """claim3 p4_alpha_training_replay_bit_exact（确定性门 64/64——宪法语义 + I1）。"""
    return _gate_claim(
        result_id, stat_plan_ref, "p4_alpha_training_replay_bit_exact",
        "training_replay_deterministic_assertions",
        {
            "all_cells_replay_bit_exact": all(replay_ok),
        },
        data_ref=f"n_cells={len(replay_ok)}",
        recompute_ok=True,                       # 重放即复算（零随机）
        detected_by=detected_by,
    )


def evaluate_p4_composite(result_id: str, stat_plan_ref: str,
                          margin: EvidenceResult, dual: EvidenceResult,
                          replay: EvidenceResult,
                          leakage_free: bool,
                          detected_by: str = "evidence.evaluator") -> EvidenceResult:
    """P4-α 复合（evaluate_c1_composite 体例——Holm 族 3 claim + leakage=0 + I1）。

    v1.2 判据域立法（Q-L04-12 补裁②）：配对比较 = 语境工件非门判据——复合门 =
    margin（profile 冻结契约）+ 双域义务（Q-L04-12②）+ replay（Q-L13-20①）。
    """
    return evaluate_c1_composite(
        result_id, stat_plan_ref, (margin, dual, replay),
        mechanical_ok=True,
        leakage_free=leakage_free,
        i1_match=bool(replay.recompute_ok and replay.verdict is HypothesisVerdict.SUPPORTED),
        recompute_ok=all(r.recompute_ok for r in (margin, dual, replay)),
        statistical_core=margin,
        detected_by=detected_by,
        composite_label="p4_alpha_brain_core",
    )
