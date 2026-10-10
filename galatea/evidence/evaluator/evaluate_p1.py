"""P1 三 claim 判定器（stat plan p1_physio v1.0/v1.1 冻结承载；Q-L13-13）。

- fidelity / lgrade_safety = 确定性门（门全过 p=0.0 / 任一失败 p=1.0——c4_calibration
  同式，单调安全）；signal = Pearson r ≥ 0.5 + Fisher z 95% CI 下界 > 0（Q-L13-09 族
  首例 r 型）。
- 复合 = evaluate_c1_composite 体例（Holm 族 = 3 claim 主判定 p，REV-0014 R3 机械执行；
  leakage=0 + I1（= 重放 bit-exact——记录-重放范式的复算面）+ recompute 前置）。
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
    """确定性门 claim 通用体（_c5_gate_claim 同式）。"""
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


def evaluate_p1_channel_fidelity(result_id: str, stat_plan_ref: str, corpus_verified: bool,
                                 derive_recompute_ok: bool, replay_bit_exact: bool,
                                 due_window_formation_rate: float,
                                 channel_source_invariance: bool,
                                 detected_by: str = "evidence.evaluator") -> EvidenceResult:
    """claim1 p1_channel_fidelity（确定性门四断言——stat plan primary_endpoints）。"""
    return _gate_claim(
        result_id, stat_plan_ref, "p1_channel_fidelity",
        "replay_bit_exact_and_formation_rate_and_source_invariance",
        {
            "corpus_stream_digest_verified": corpus_verified,
            "derive_recompute_ok": derive_recompute_ok,
            "replay_bit_exact": replay_bit_exact,
            "due_window_formation_rate_1_0": due_window_formation_rate == 1.0,
            "channel_source_invariance": channel_source_invariance,
        },
        data_ref=f"sealed_corpus_due_formation_rate={due_window_formation_rate}",
        recompute_ok=replay_bit_exact and derive_recompute_ok,
        detected_by=detected_by,
    )


def evaluate_p1_lgrade_safety(result_id: str, stat_plan_ref: str, scenario_results: dict[str, bool],
                              detected_by: str = "evidence.evaluator") -> EvidenceResult:
    """claim2 p1_lgrade_safety（确定性门 = 冻结场景电池逐项）。"""
    return _gate_claim(
        result_id, stat_plan_ref, "p1_lgrade_safety",
        "safety_path_coverage_all_deterministic",
        dict(scenario_results),
        data_ref=f"scenarios={len(scenario_results)}",
        recompute_ok=True,                       # 场景电池零随机——重放即重算
        detected_by=detected_by,
    )


def _pearson_p_two_sided(r: float, n: int) -> float:
    """Pearson r 的双侧 p（t 分布；r=±1 饱和 → p=0；不完全 gamma 正则化）。"""
    if abs(r) >= 1.0:
        return 0.0
    df = n - 2
    if df <= 0:
        return 1.0
    t = r * math.sqrt(df / (1.0 - r * r))

    def lower_regularized_gamma(s: float, x: float) -> float:
        # NIST lah 正则化下不完全 gamma（确定性；df 为整数/半整数均可）
        if x < 0 or s <= 0:
            return 0.0
        gln = math.lgamma(s)
        if x < s + 1.0:
            ap = s
            total = 1.0 / s
            delta = total
            for _ in range(500):
                ap += 1.0
                delta *= x / ap
                total += delta
                if abs(delta) < abs(total) * 1e-15:
                    break
            return total * math.exp(-x + s * math.log(x) - gln)
        b, c, d = x + 1.0 - s, 1e300, 1.0 / (x + 1.0 - s)
        h = d
        for i in range(1, 500):
            an = -i * (i - s)
            b += 2.0
            d = an * d + b
            d = 1e-300 if abs(d) < 1e-300 else d
            c = b + an / c
            c = 1e-300 if abs(c) < 1e-300 else c
            d = 1.0 / d
            delta = d * c
            h *= delta
            if abs(delta - 1.0) < 1e-15:
                break
        return 1.0 - math.exp(-x + s * math.log(x) - gln) * h

    p_one = lower_regularized_gamma(df / 2.0, (t * t) / 2.0)   # P(T ≤ |t|) 单侧上积分
    return max(0.0, min(1.0, 2.0 * (1.0 - p_one)))


def evaluate_p1_signal_carriage(result_id: str, stat_plan_ref: str, pearson_r: float,
                                ci_lower: float, ci_upper: float, n_windows: int,
                                r_min: float = 0.5,
                                structural_expected: int | None = None,
                                detected_by: str = "evidence.evaluator") -> EvidenceResult:
    """claim3 p1_physical_signal_carriage（r ≥ r_min ∧ CI 下界 > 0；p = Pearson 双侧）。

    structural_expected（REV-0026 R1 机械闭环）：语料结构可评窗数 =
    capture_cycles − W_align（对齐窗尾未关）− 1（首帧派生差分 Unknown）− 1（busy 首
    差分无基线）；n_windows ≠ structural_expected → REFUTED（窗被静默丢弃即判据失真）。
    min_effects min_n=64 为零实测期功效推定初值（结构性上界 59 < 64 如实在 ADR 记账；
    饱和效应 p=0.0 对任意 n≥3 不变——功效范畴不适用于本 claim 判定方向）。
    """
    inputs_ok = n_windows >= 3
    structure_ok = structural_expected is None or n_windows == structural_expected
    passed = inputs_ok and structure_ok and pearson_r >= r_min and ci_lower > 0.0
    p = _pearson_p_two_sided(pearson_r, n_windows) if inputs_ok else 1.0
    refutations: tuple[str, ...] = ()
    if inputs_ok and not structure_ok:
        refutations = (f"window_account_broken: n_windows={n_windows} != "
                       f"structural_expected={structural_expected}",)
    elif inputs_ok and pearson_r < r_min:
        refutations = (f"pearson_r {pearson_r:.4g} < r_min {r_min}",)
    elif inputs_ok and ci_lower <= 0.0:
        refutations = (f"ci_lower {ci_lower:.4g} <= 0",)
    data_refs = [f"n_windows={n_windows}", f"r_min={r_min}"]
    if structural_expected is not None:
        data_refs.append(f"structural_expected={structural_expected}")
    return EvidenceResult(
        result_id=result_id, hypothesis_refs=("p1_physical_signal_carriage",),
        stat_plan_ref=stat_plan_ref,
        estimand="pearson_r_minus_delta_busy_vs_formed_energy_rate",
        effect_size=pearson_r if inputs_ok else 0.0,
        ci=ConfidenceInterval(lower=ci_lower, upper=ci_upper, level=0.95),
        p_or_bayes=p,
        verdict=HypothesisVerdict.SUPPORTED if passed else HypothesisVerdict.REFUTED,
        unknowns=(),
        refutations=refutations,
        data_refs=tuple(data_refs),
        recompute_ok=inputs_ok,
    )


def evaluate_p1_composite(result_id: str, stat_plan_ref: str,
                          fidelity: EvidenceResult, safety: EvidenceResult,
                          signal: EvidenceResult, *,
                          leakage_free: bool, recompute_ok: bool,
                          alpha: float = 0.05,
                          detected_by: str = "evidence.evaluator") -> EvidenceResult:
    """P1 复合（Holm 族 = 3 claim 主判定 p；统计核 = signal claim；I1 = fidelity 重放）。"""
    i1_match = bool(fidelity.recompute_ok)
    mechanical_ok = True                          # 机械面已并入 fidelity/safety 门集
    return evaluate_c1_composite(
        result_id=result_id, stat_plan_ref=stat_plan_ref,
        constituent_results=(fidelity, safety, signal),
        mechanical_ok=mechanical_ok, leakage_free=leakage_free, i1_match=i1_match,
        recompute_ok=recompute_ok, statistical_core=signal, alpha=alpha,
        detected_by=detected_by, composite_label="p1_physio",
    )
