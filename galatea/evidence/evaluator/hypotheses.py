"""EvidenceResult schema 与判定执行（L13 §2.2 evd.evidence_result / §4.3 / §10 hypotheses.py）。

纪律：三态判定 + 未知清单（unknown ≠ negative）；root 门槛载体（R0）；
含统计计划引用与可复算标志。判定执行（M2 准备单元交付 + M2 收尾增补）：
SUPPORTED = 达冻结阈值 **且负控通过**（L13 §4.3）；INCONCLUSIVE = 功效不足或冲突；
REFUTED = 反证条件成立。三判定器：real_vs_pseudo（M1）/ wording_null（M1，χ²）/ carryover（M2）。
"""
import enum
import math
from dataclasses import dataclass

from galatea.kernel.unknown import Unknown, UnknownReason


class HypothesisVerdict(enum.StrEnum):
    """假设判定三态（L13 §4.3：禁把 unknown 当阴性）。"""

    SUPPORTED = "SUPPORTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    REFUTED = "REFUTED"


@dataclass(frozen=True, slots=True)
class ConfidenceInterval:
    """效应量区间（estimand 标度；float64 = Q-T10）。"""

    lower: float
    upper: float
    level: float  # 如 0.95


@dataclass(frozen=True, slots=True)
class EvidenceResult:
    """根证据结果（L13 §2.2：SUPPORTED/INCONCLUSIVE/REFUTED + unknowns + refutations）。"""

    result_id: str
    hypothesis_refs: tuple[str, ...]
    stat_plan_ref: str
    estimand: str
    effect_size: float | None
    ci: ConfidenceInterval | None
    p_or_bayes: float | None
    verdict: HypothesisVerdict
    unknowns: tuple[Unknown, ...]
    refutations: tuple[str, ...]
    data_refs: tuple[str, ...]
    recompute_ok: bool

    def __post_init__(self) -> None:
        if not self.hypothesis_refs or not self.stat_plan_ref:
            raise ValueError("EvidenceResult requires hypothesis_refs and stat_plan_ref（claim 冻结先于运行）")
        if self.verdict is HypothesisVerdict.SUPPORTED:
            if not self.recompute_ok:
                raise ValueError("SUPPORTED verdict requires recompute_ok（I1 复算通过是门禁条件，L13 §1）")
            if self.effect_size is None or self.ci is None:
                raise ValueError("SUPPORTED requires effect_size and CI（estimand 完整性，L13 §4.3；R9⑨）")


# ==========================================================================
# 判定执行（M2 准备单元：EvidenceResult 首评，ADR-G-0007 口径钉死）
# ==========================================================================


def _mcnemar_exact_two_sided(n10: int, n01: int) -> float:
    """配对二值 McNemar 精确检验（双侧）：discordant = n10+n01，
    p = 2·Σ_{k≤min} C(n_d,k)/2^{n_d}（上截 1.0）。纯整数算术，确定性。"""
    n_d = n10 + n01
    if n_d == 0:
        return 1.0
    n_min = min(n10, n01)
    cum = 0.0
    for k in range(n_min + 1):
        cum += math.comb(n_d, k) / (2 ** n_d)
    return min(1.0, 2.0 * cum)


def _paired_rate_stats(
    arm_a: tuple[bool, ...], arm_b: tuple[bool, ...]
) -> tuple[float, float, float, float, float]:
    """配对二值统计：返回 (rate_a, rate_b, rate_diff, ci_lower, ci_upper)。

    CI = 配对差 Wald 区间（SE = sqrt((n_d − d²/n)/n²)，d = discordance 差）；
    确定性饱和（SE=0）时区间退化为 [diff, diff]——如实呈现（ADR-G-0007 口径）。
    """
    if len(arm_a) != len(arm_b) or not arm_a:
        raise ValueError("paired arms must be non-empty and equal length")
    n = len(arm_a)
    n10 = sum(1 for a, b in zip(arm_a, arm_b) if a and not b)   # a 采纳 b 未采纳
    n01 = sum(1 for a, b in zip(arm_a, arm_b) if b and not a)   # b 采纳 a 未采纳
    rate_a = sum(arm_a) / n
    rate_b = sum(arm_b) / n
    diff = rate_a - rate_b
    se2 = (n10 + n01 - (n10 - n01) ** 2 / n) / (n * n)
    half = 1.959963984540054 * math.sqrt(max(se2, 0.0))          # z=1.959964（95%）
    return rate_a, rate_b, diff, diff - half, diff + half


def evaluate_real_vs_pseudo(
    result_id: str,
    stat_plan_ref: str,
    healthy_adoption: tuple[bool, ...],
    depleted_adoption: tuple[bool, ...],
    pseudo_inert: bool,
    recompute_ok: bool,
    n_expected: int = 64,
    detected_by: str = "evidence.evaluator",
) -> EvidenceResult:
    """real_vs_pseudo_motive 判定（冻结协议：stat plan v1.1 claim 1）。

    判据：② 真实理由扰动改变采纳（配对差达冻结阈值 d≥0.5；estimand = 配对采用率差）
    且 ③ 伪理由注入惰性（negative control）→ SUPPORTED；
    ③ 失效 → REFUTED（RequestDirectWriteSuspect，S1）；② 无效应 → REFUTED
    （真实理由非因果 = PseudoReasonDetected 判据面）；n 不足 → INCONCLUSIVE。
    饱和处理：确定性阶段两臂方差为 0 → d 不可定义，判定以 estimand 上确界
    单调性承载（rate_diff=1.0 为该标度最大值），未知清单如实记录。
    """
    if len(healthy_adoption) != n_expected or len(depleted_adoption) != n_expected:
        return EvidenceResult(
            result_id=result_id,
            hypothesis_refs=("real_vs_pseudo_motive",),
            stat_plan_ref=stat_plan_ref,
            estimand="adoption_rate_discrimination",
            effect_size=None, ci=None, p_or_bayes=None,
            verdict=HypothesisVerdict.INCONCLUSIVE,
            unknowns=(
                Unknown(
                    reason=UnknownReason.INSUFFICIENT_OBSERVATION,
                    evidence_refs=("trial_count",),
                    detail=f"n={len(healthy_adoption)}/{len(depleted_adoption)} < frozen n={n_expected}",
                    detected_by=detected_by,
                    virtual_time=0,
                ),
            ),
            refutations=(), data_refs=(), recompute_ok=recompute_ok,
        )
    rate_h, rate_d, diff, ci_lo, ci_hi = _paired_rate_stats(healthy_adoption, depleted_adoption)
    p_value = _mcnemar_exact_two_sided(
        sum(1 for a, b in zip(healthy_adoption, depleted_adoption) if a and not b),
        sum(1 for a, b in zip(healthy_adoption, depleted_adoption) if b and not a),
    )
    saturated = diff > 0.0 and all(a != b for a, b in zip(healthy_adoption, depleted_adoption))
    unknowns: list[Unknown] = []
    if saturated:
        unknowns.append(
            Unknown(
                reason=UnknownReason.CALIBRATION_UNCERTAIN,
                evidence_refs=("cohens_d",),
                detail=(
                    "cohens_d undefined: zero within-arm variance in deterministic phase"
                    "（ADR-G-0007 口径：estimand rate_diff=1.0 = 标度上确界，阈值单调满足）"
                ),
                detected_by=detected_by,
                virtual_time=0,
            )
        )
    refutations: list[str] = []
    if not pseudo_inert:
        refutations.append("RequestDirectWriteSuspect")   # ③ 失效（S1 语义，L08 §6）
    if diff <= 0.0:
        refutations.append("PseudoReasonDetected")        # ② 无效应：真实理由非因果

    if refutations:
        verdict = HypothesisVerdict.REFUTED
    elif saturated:
        verdict = HypothesisVerdict.SUPPORTED if recompute_ok else HypothesisVerdict.INCONCLUSIVE
    else:
        # 非饱和路径：以 rate_diff ≥ 0.5 为 d≥0.5 的可计算代理（二值标度单调对应），
        # CI 下界 > 0 为显著性条件——正式噪声阶段由 L13 evaluator 换统计基线（protection_suite 注）。
        verdict = (
            HypothesisVerdict.SUPPORTED
            if (recompute_ok and diff >= 0.5 and ci_lo > 0.0)
            else HypothesisVerdict.INCONCLUSIVE
        )
    return EvidenceResult(
        result_id=result_id,
        hypothesis_refs=("real_vs_pseudo_motive",),
        stat_plan_ref=stat_plan_ref,
        estimand="adoption_rate_discrimination",
        effect_size=diff,
        ci=ConfidenceInterval(lower=ci_lo, upper=ci_hi, level=0.95),
        p_or_bayes=p_value,
        verdict=verdict,
        unknowns=tuple(unknowns),
        refutations=tuple(refutations),
        data_refs=(f"trials:healthy={rate_h:.6f}", f"trials:depleted={rate_d:.6f}"),
        recompute_ok=recompute_ok,
    )


def evaluate_carryover(
    result_id: str,
    stat_plan_ref: str,
    carry_aware: tuple[bool, ...],
    naive_aware: tuple[bool, ...],
    recompute_ok: bool,
    n_expected: int = 64,
    detected_by: str = "evidence.evaluator",
) -> EvidenceResult:
    """m2_continuity_carryover 判定（冻结协议：stat plan m2_continuity_sc5_sc6 v1.0）。

    判据（HLD §10.2 M2 行"经历经非初始化路径进入下一轮"的统计面）：round2 感知
    退化（intero fault）下携带臂危害知晓率 − naive 臂失明率 ≥ 冻结最小效应
    （min_effects#m2_continuity_carryover，estimand = 配对率差，二值标度以
    rate_diff ≥ 0.5 为 d≥0.5 代理——承 M1 首评先例）；naive 臂未失明（知晓）为
    反证 → REFUTED（记忆无因果贡献或场景退化失败）。n 不足 → INCONCLUSIVE。
    饱和处理同 evaluate_real_vs_pseudo（确定性/高效应下 d 不可定义，如实记录）。
    """
    if len(carry_aware) != n_expected or len(naive_aware) != n_expected:
        return EvidenceResult(
            result_id=result_id,
            hypothesis_refs=("m2_continuity_carryover",),
            stat_plan_ref=stat_plan_ref,
            estimand="hazard_awareness_carryover",
            effect_size=None, ci=None, p_or_bayes=None,
            verdict=HypothesisVerdict.INCONCLUSIVE,
            unknowns=(
                Unknown(
                    reason=UnknownReason.INSUFFICIENT_OBSERVATION,
                    evidence_refs=("trial_count",),
                    detail=f"n={len(carry_aware)}/{len(naive_aware)} < frozen n={n_expected}",
                    detected_by=detected_by,
                    virtual_time=0,
                ),
            ),
            refutations=(), data_refs=(), recompute_ok=recompute_ok,
        )
    rate_c, rate_n, diff, ci_lo, ci_hi = _paired_rate_stats(carry_aware, naive_aware)
    p_value = _mcnemar_exact_two_sided(
        sum(1 for a, b in zip(carry_aware, naive_aware) if a and not b),
        sum(1 for a, b in zip(carry_aware, naive_aware) if b and not a),
    )
    saturated = diff > 0.0 and all(a != b for a, b in zip(carry_aware, naive_aware))
    unknowns: list[Unknown] = []
    if saturated:
        unknowns.append(
            Unknown(
                reason=UnknownReason.CALIBRATION_UNCERTAIN,
                evidence_refs=("cohens_d",),
                detail=(
                    "cohens_d undefined: zero within-arm variance in deterministic/high-effect phase"
                    "（estimand rate_diff 单调承载阈值判定，ADR-G-0007 口径同源）"
                ),
                detected_by=detected_by,
                virtual_time=0,
            )
        )
    refutations: list[str] = []
    if diff <= 0.0:
        refutations.append("carryover_absent")            # 记忆无跨期因果贡献
    if rate_n > 0.5:
        refutations.append("naive_arm_not_blind")         # 负控面失败：感知退化未生效
    if refutations:
        verdict = HypothesisVerdict.REFUTED
    elif saturated:
        verdict = HypothesisVerdict.SUPPORTED if recompute_ok else HypothesisVerdict.INCONCLUSIVE
    else:
        verdict = (
            HypothesisVerdict.SUPPORTED
            if (recompute_ok and diff >= 0.5 and ci_lo > 0.0)
            else HypothesisVerdict.INCONCLUSIVE
        )
    return EvidenceResult(
        result_id=result_id,
        hypothesis_refs=("m2_continuity_carryover",),
        stat_plan_ref=stat_plan_ref,
        estimand="hazard_awareness_carryover",
        effect_size=diff,
        ci=ConfidenceInterval(lower=ci_lo, upper=ci_hi, level=0.95),
        p_or_bayes=p_value,
        verdict=verdict,
        unknowns=tuple(unknowns),
        refutations=tuple(refutations),
        data_refs=(f"trials:carry={rate_c:.6f}", f"trials:naive={rate_n:.6f}"),
        recompute_ok=recompute_ok,
    )


def _chi2_sf(x: float, df: int) -> float:
    """χ² 上侧概率 = Q(df/2, x/2)（正则化上不完全 Gamma：级数 + 连分数，NR 体例）。"""
    if x <= 0.0:
        return 1.0
    a = df / 2.0
    xx = x / 2.0
    log_prefactor = -xx + a * math.log(xx) - math.lgamma(a)
    if xx < a + 1.0:
        term = 1.0 / a
        total = term
        n = 1
        while n < 1000:
            term *= xx / (a + n)
            total += term
            if term < total * 1e-16:
                break
            n += 1
        p = total * math.exp(log_prefactor)
        return max(0.0, min(1.0, 1.0 - p))
    b = xx + 1.0 - a
    c = 1e300
    d = 1.0 / b
    h = d
    for i in range(1, 300):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
        c = b + an / c
        c = c if abs(c) > 1e-300 else 1e-300
        h *= d * c
        if abs(d * c - 1.0) < 1e-15:
            break
    q = math.exp(log_prefactor) * h
    return max(0.0, min(1.0, q))


def evaluate_root_composite(
    result_id: str,
    stat_plan_ref: str,
    constituent_results: tuple[EvidenceResult, ...],
    leakage_free: bool,
    i1_match: bool,
    recompute_ok: bool,
    statistical_core: EvidenceResult,
    detected_by: str = "evidence.evaluator",
) -> EvidenceResult:
    """根复合判定（R0；Q-L13-11 ①：r0_root_causal_auditability）。

    判据（root stat plan v1.0）：子主张全 SUPPORTED 且 leakage=0 且 I1 match →
    根 SUPPORTED（recompute_ok 强制）；任一子主张 REFUTED → 根 REFUTED；
    否则 INCONCLUSIVE（unknown ≠ negative，禁升格）。
    effect_size/CI/p 由统计核（sealed carryover 首评）承载（Q-L13-11 ①）。
    """
    if not constituent_results:
        raise ValueError("root composite requires constituent results")
    refuted = [r for r in constituent_results if r.verdict is HypothesisVerdict.REFUTED]
    supported = [r for r in constituent_results if r.verdict is HypothesisVerdict.SUPPORTED]
    refutation_codes = [code for r in refuted for code in r.refutations]
    if refutation_codes:
        verdict = HypothesisVerdict.REFUTED
    elif len(supported) == len(constituent_results) and leakage_free and i1_match and recompute_ok:
        verdict = HypothesisVerdict.SUPPORTED
    else:
        verdict = HypothesisVerdict.INCONCLUSIVE
    unknowns: list[Unknown] = list(statistical_core.unknowns)
    if not leakage_free:
        unknowns.append(
            Unknown(
                reason=UnknownReason.CONFLICTING_EVIDENCE,
                evidence_refs=("leakage_report",),
                detail="leakage probes reported detections（root 判定不得在泄漏未清时 SUPPORTED）",
                detected_by=detected_by,
                virtual_time=0,
            )
        )
    if not i1_match:
        unknowns.append(
            Unknown(
                reason=UnknownReason.CONFLICTING_EVIDENCE,
                evidence_refs=("recompute_report",),
                detail="I1 recompute mismatch（recorder 数据复算不 bit-exact）",
                detected_by=detected_by,
                virtual_time=0,
            )
        )
    return EvidenceResult(
        result_id=result_id,
        hypothesis_refs=("r0_root_causal_auditability", "m0_intervention_signatures", "m2_sc5_four_arm_signatures")
        + tuple(ref for r in constituent_results for ref in r.hypothesis_refs),
        stat_plan_ref=stat_plan_ref,
        estimand="root_composite_causal_auditability",
        effect_size=statistical_core.effect_size,
        ci=statistical_core.ci,
        p_or_bayes=statistical_core.p_or_bayes,
        verdict=verdict,
        unknowns=tuple(unknowns),
        refutations=tuple(refutation_codes),
        data_refs=statistical_core.data_refs,
        recompute_ok=recompute_ok,
    )


def evaluate_wording_null(
    result_id: str,
    stat_plan_ref: str,
    cell_adopted_counts: tuple[int, ...],
    n_per_cell: int,
    negative_control_ok: bool,
    recompute_ok: bool,
    alpha: float = 0.05,
    n_expected_cells: int = 8,
    detected_by: str = "evidence.evaluator",
) -> EvidenceResult:
    """wording_manipulation_null 判定（冻结协议：stat plan v1.1 claim 2；Q-L08-06）。

    判定形式（首评更正，2026-09-26）：**采纳率跨 cell 同质性 χ² 检验**（df = cells−1）。
    冻结的 0.01 传输损坏率使 trial 真实带噪——ADR-G-0007 的"指纹全等"确定性 shortcut
    前提不成立，回落到冻结计划的统计断言原文（采纳率不得随措辞显著变化）。
    estimand = 采纳率措辞主效应（max−min cell 极差）；CI = 极值两 cell 之差的 Wald 区间。
    p > α 且负控通过 → SUPPORTED；p ≤ α → REFUTED（措辞操纵生效，M1 硬条件失败）。
    """
    if len(cell_adopted_counts) != n_expected_cells or n_per_cell <= 0:
        return EvidenceResult(
            result_id=result_id,
            hypothesis_refs=("wording_manipulation_null",),
            stat_plan_ref=stat_plan_ref,
            estimand="adoption_rate_wording_main_effect",
            effect_size=None, ci=None, p_or_bayes=None,
            verdict=HypothesisVerdict.INCONCLUSIVE,
            unknowns=(
                Unknown(
                    reason=UnknownReason.INSUFFICIENT_OBSERVATION,
                    evidence_refs=("cell_count",),
                    detail=f"cells={len(cell_adopted_counts)} < frozen {n_expected_cells}",
                    detected_by=detected_by,
                    virtual_time=0,
                ),
            ),
            refutations=(), data_refs=(), recompute_ok=recompute_ok,
        )
    n_total = n_per_cell * len(cell_adopted_counts)
    adopted_total = sum(cell_adopted_counts)
    expected_adopted = adopted_total / len(cell_adopted_counts)
    expected_not = n_per_cell - expected_adopted
    chi2 = 0.0
    for observed in cell_adopted_counts:
        if expected_adopted > 0:
            chi2 += (observed - expected_adopted) ** 2 / expected_adopted
        if expected_not > 0:
            chi2 += ((n_per_cell - observed) - expected_not) ** 2 / expected_not
    p_value = _chi2_sf(chi2, df=len(cell_adopted_counts) - 1)

    rates = [c / n_per_cell for c in cell_adopted_counts]
    main_effect = max(rates) - min(rates)
    hi, lo = max(rates), min(rates)
    se = math.sqrt(hi * (1 - hi) / n_per_cell + lo * (1 - lo) / n_per_cell)
    half = 1.959963984540054 * se

    refutations: list[str] = []
    if p_value <= alpha:
        refutations.append("wording_main_effect_detected")
    if not negative_control_ok:
        refutations.append("negative_control_violated")
    verdict = (
        HypothesisVerdict.SUPPORTED
        if (recompute_ok and not refutations)
        else (HypothesisVerdict.REFUTED if refutations else HypothesisVerdict.INCONCLUSIVE)
    )
    return EvidenceResult(
        result_id=result_id,
        hypothesis_refs=("wording_manipulation_null",),
        stat_plan_ref=stat_plan_ref,
        estimand="adoption_rate_wording_main_effect",
        effect_size=main_effect,
        ci=ConfidenceInterval(lower=max(0.0, main_effect - half), upper=min(1.0, main_effect + half), level=0.95),
        p_or_bayes=p_value,
        verdict=verdict,
        unknowns=(),
        refutations=tuple(refutations),
        data_refs=(
            f"cells={len(cell_adopted_counts)}",
            f"chi2={chi2:.4f}",
            f"adopted_total={adopted_total}/{n_total}",
        ),
        recompute_ok=recompute_ok,
    )


# ==========================================================================
# C1 判定执行（stat plan c1_perception_models v1.0；顺延终止条款首次执行）
# ==========================================================================

_Z_95 = 1.959963984540054


def _paired_continuous_stats(
    diffs: tuple[float, ...], n_expected: int, detected_by: str
) -> tuple[EvidenceResult | None, float, float, float, float, float, float]:
    """per-run 配对连续差统计：返回 (insufficient_result|None, mean, sd, d, ci_lo, ci_hi, p)。

    Wald 正态近似（n=64；承 M1/M2 Wald 先例）；d = mean/sd（sd=0 → 饱和处理，
    上层按 estimand 单调性判定——ADR-G-0007 口径）；p = 双侧正态 z 检验。
    """
    if len(diffs) != n_expected:
        result = EvidenceResult(
            result_id="", hypothesis_refs=(), stat_plan_ref="",
            estimand="", effect_size=None, ci=None, p_or_bayes=None,
            verdict=HypothesisVerdict.INCONCLUSIVE,
            unknowns=(Unknown(
                reason=UnknownReason.INSUFFICIENT_OBSERVATION, evidence_refs=("trial_count",),
                detail=f"n={len(diffs)} < frozen n={n_expected}",
                detected_by=detected_by, virtual_time=0,
            ),),
            refutations=(), data_refs=(), recompute_ok=False,
        )
        return result, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0
    n = len(diffs)
    mean = sum(diffs) / n
    variance = sum((d - mean) ** 2 for d in diffs) / (n - 1) if n > 1 else 0.0
    sd = math.sqrt(variance)
    if sd == 0.0:
        d = float("inf") if mean > 0 else (float("-inf") if mean < 0 else 0.0)
        half = 0.0
        p = 0.0 if mean != 0 else 1.0
    else:
        d = mean / sd
        half = _Z_95 * sd / math.sqrt(n)
        p = min(1.0, 2.0 * (1.0 - _normal_cdf(abs(mean) / (sd / math.sqrt(n)))))
    return None, mean, sd, d, mean - half, mean + half, p


def _normal_cdf(x: float) -> float:
    """标准正态 CDF（erf；与 c1profile.normal_cdf 同式——评价面独立实现防循环导入）。"""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _c1_verdict_from_diff(
    mean: float, d: float, ci_lo: float, p: float, recompute_ok: bool, d_threshold: float
) -> tuple[HypothesisVerdict, tuple[str, ...], list[Unknown]]:
    """配对差判定共享核：d≥阈 且 CI 下界>0 且 p<0.05 → SUPPORTED；
    mean ≤ 0（方向反转）→ REFUTED；饱和（sd=0, mean>0）→ 阈值单调满足。"""
    unknowns: list[Unknown] = []
    refutations: list[str] = []
    saturated = math.isinf(d) and mean > 0
    if saturated:
        unknowns.append(Unknown(
            reason=UnknownReason.CALIBRATION_UNCERTAIN, evidence_refs=("cohens_d",),
            detail="cohens_d undefined: zero variance across runs（estimand 单调承载阈值，ADR-G-0007 口径）",
            detected_by="evidence.evaluator", virtual_time=0,
        ))
    if mean <= 0.0:
        refutations.append("paired_difference_non_positive")
    saturated_pass = saturated or (d >= d_threshold and ci_lo > 0.0 and p < 0.05)
    if refutations:
        return HypothesisVerdict.REFUTED, tuple(refutations), unknowns
    if recompute_ok and saturated_pass:
        return HypothesisVerdict.SUPPORTED, (), unknowns
    return HypothesisVerdict.INCONCLUSIVE, (), unknowns


def evaluate_c1_perception_tracking(
    result_id: str,
    stat_plan_ref: str,
    accuracy_diffs: tuple[float, ...],
    ece: float,
    ece_max: float,
    recompute_ok: bool,
    n_expected: int = 64,
    detected_by: str = "evidence.evaluator",
) -> EvidenceResult:
    """c1_perception_tracking 判定（stat plan v1.0 claim 1）。

    EP1 = per-run 准确率差（d≥0.5 + CI 下界>0 + p<0.05，Holm 族内单终点即本点）；
    EP2 = ECE ≤ ece_max（Q-L03-04 确定性阈值断言）。双 EP 满足 → SUPPORTED；
    EP1 方向反转 → REFUTED；EP2 越阈 → REFUTED（校准失败 = C1 硬条件失败）。
    """
    insufficient, mean, _sd, d, ci_lo, _ci_hi, p = _paired_continuous_stats(
        accuracy_diffs, n_expected, detected_by
    )
    hypothesis_refs = ("c1_perception_tracking",)
    if insufficient is not None:
        return EvidenceResult(
            result_id=result_id, hypothesis_refs=hypothesis_refs, stat_plan_ref=stat_plan_ref,
            estimand="per_run_cell_decision_accuracy_difference",
            effect_size=None, ci=None, p_or_bayes=None,
            verdict=HypothesisVerdict.INCONCLUSIVE,
            unknowns=insufficient.unknowns, refutations=(), data_refs=(), recompute_ok=recompute_ok,
        )
    verdict, refutations, unknowns = _c1_verdict_from_diff(mean, d, ci_lo, p, recompute_ok, 0.5)
    if ece > ece_max and verdict is not HypothesisVerdict.REFUTED:
        refutations = ("ece_above_frozen_threshold",)
        verdict = HypothesisVerdict.REFUTED
    elif ece > ece_max:
        refutations = refutations + ("ece_above_frozen_threshold",)
    return EvidenceResult(
        result_id=result_id, hypothesis_refs=hypothesis_refs, stat_plan_ref=stat_plan_ref,
        estimand="per_run_cell_decision_accuracy_difference",
        effect_size=d if not math.isinf(d) else mean,
        ci=ConfidenceInterval(lower=ci_lo, upper=_ci_hi, level=0.95),
        p_or_bayes=p,
        verdict=verdict, unknowns=tuple(unknowns), refutations=refutations,
        data_refs=(f"mean_diff={mean:.6f}", f"ece={ece:.6f}/{ece_max}"),
        recompute_ok=recompute_ok,
    )


def evaluate_c1_world_prediction(
    result_id: str,
    stat_plan_ref: str,
    mse_diffs: tuple[float, ...],
    recompute_ok: bool,
    n_expected: int = 64,
    detected_by: str = "evidence.evaluator",
) -> EvidenceResult:
    """c1_world_prediction 判定（stat plan v1.0 claim 2；阈值 d≥0.5）。"""
    insufficient, mean, _sd, d, ci_lo, _ci_hi, p = _paired_continuous_stats(
        mse_diffs, n_expected, detected_by
    )
    hypothesis_refs = ("c1_world_prediction",)
    if insufficient is not None:
        return EvidenceResult(
            result_id=result_id, hypothesis_refs=hypothesis_refs, stat_plan_ref=stat_plan_ref,
            estimand="per_run_post_move_window_mse_difference",
            effect_size=None, ci=None, p_or_bayes=None,
            verdict=HypothesisVerdict.INCONCLUSIVE,
            unknowns=insufficient.unknowns, refutations=(), data_refs=(), recompute_ok=recompute_ok,
        )
    verdict, refutations, unknowns = _c1_verdict_from_diff(mean, d, ci_lo, p, recompute_ok, 0.5)
    return EvidenceResult(
        result_id=result_id, hypothesis_refs=hypothesis_refs, stat_plan_ref=stat_plan_ref,
        estimand="per_run_post_move_window_mse_difference",
        effect_size=d if not math.isinf(d) else mean,
        ci=ConfidenceInterval(lower=ci_lo, upper=_ci_hi, level=0.95),
        p_or_bayes=p,
        verdict=verdict, unknowns=tuple(unknowns), refutations=refutations,
        data_refs=(f"mean_diff={mean:.6f}",),
        recompute_ok=recompute_ok,
    )



def evaluate_c1_body_incorporation(
    result_id: str,
    stat_plan_ref: str,
    criterion_diffs: tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]],
    recompute_ok: bool,
    n_expected: int = 64,
    detected_by: str = "evidence.evaluator",
) -> EvidenceResult:
    """c1_body_incorporation 判定（stat plan v1.0 claim 3；Q-L04-03：三判据各 d≥0.4 且联合）。

    joint = 三判据全部 SUPPORTED；任一方向反转 → REFUTED；否则 INCONCLUSIVE。
    effect_size = 三判据最小 d（联合短板，Q-L04-03 联合判定的保守估计量）。
    """
    names = ("criterion1_sensory_motor", "criterion2_cross_modal", "criterion3_efference")
    verdicts: list[HypothesisVerdict] = []
    ds: list[float] = []
    cis: list[ConfidenceInterval | None] = []
    refutations: list[str] = []
    unknowns: list[Unknown] = []
    p_values: list[float] = []
    for name, diffs in zip(names, criterion_diffs):
        insufficient, mean, _sd, d, ci_lo, ci_hi, p = _paired_continuous_stats(
            diffs, n_expected, detected_by
        )
        if insufficient is not None:
            verdicts.append(HypothesisVerdict.INCONCLUSIVE)
            ds.append(float("nan"))
            cis.append(None)
            continue
        v, refs, unks = _c1_verdict_from_diff(mean, d, ci_lo, p, recompute_ok, 0.4)
        verdicts.append(v)
        ds.append(d if not math.isinf(d) else mean)
        cis.append(ConfidenceInterval(lower=ci_lo, upper=ci_hi, level=0.95))
        refutations.extend(f"{name}:{r}" for r in refs)
        unknowns.extend(unks)
        p_values.append(p)
    if HypothesisVerdict.REFUTED in verdicts:
        verdict = HypothesisVerdict.REFUTED
    elif all(v is HypothesisVerdict.SUPPORTED for v in verdicts) and recompute_ok:
        verdict = HypothesisVerdict.SUPPORTED
    else:
        verdict = HypothesisVerdict.INCONCLUSIVE
    # REV-0014 R2：effect = 联合短板（min-d 判据），CI = 该判据的 Wald 95% 区间
    #（REV-0014 R2 前为点估计占位——评审发现 S3，修复）
    finite = [(d, ci) for d, ci in zip(ds, cis) if not math.isnan(d)]
    if finite:
        effect, effect_ci = min(finite, key=lambda pair: pair[0])
    else:
        effect, effect_ci = None, None
    max_p = max(p_values) if p_values else None
    return EvidenceResult(
        result_id=result_id,
        hypothesis_refs=("c1_body_incorporation",) + names,
        stat_plan_ref=stat_plan_ref,
        estimand="per_run_three_criteria_paired_differences",
        effect_size=effect,
        ci=effect_ci,
        p_or_bayes=max_p,
        verdict=verdict, unknowns=tuple(unknowns), refutations=tuple(refutations),
        data_refs=tuple(
            f"{n}:d={d:.4f}" if not math.isnan(d) else f"{n}:n/a" for n, d in zip(names, ds)
        )
        + (("p<1e-16（float64 下溢呈现，REV-0014 R2）",) if max_p == 0.0 else ()),
        recompute_ok=recompute_ok,
    )


def holm_bonferroni(
    p_values: tuple[float, ...], alpha: float = 0.05
) -> tuple[tuple[bool, ...], tuple[float, ...]]:
    """Holm–Bonferroni 逐步下降校正（Q-L13-01 冻结默认；族 = 单 EvidenceResult 内
    全部主终点）。返回 (rejected_mask, adjusted_stepdown_ps)。

    程序：p 升序，p_(i) ≤ α/(m−i+1) → 拒绝并继续；首个不拒绝处停止，其后全保留。
    adjusted p（step-down）= max over j≤i of (m−j+1)·p_(j)（单调化，截 1.0）。
    """
    m = len(p_values)
    if m == 0:
        return (), ()
    order = sorted(range(m), key=lambda i: p_values[i])
    rejected = [False] * m
    adjusted = [1.0] * m
    running_max = 0.0
    for i, idx in enumerate(order):
        stepdown = (m - i) * p_values[idx]
        running_max = max(running_max, stepdown)
        adjusted[idx] = min(1.0, running_max)
        if p_values[idx] <= alpha / (m - i):
            rejected[idx] = True
        else:
            break   # 首个不拒绝处停止——其后（更大 p）全部保留
    return tuple(rejected), tuple(adjusted)


def evaluate_c1_composite(
    result_id: str,
    stat_plan_ref: str,
    constituent_results: tuple[EvidenceResult, ...],
    mechanical_ok: bool,
    leakage_free: bool,
    i1_match: bool,
    recompute_ok: bool,
    statistical_core: EvidenceResult,
    alpha: float = 0.05,
    detected_by: str = "evidence.evaluator",
) -> EvidenceResult:
    """C1 复合判定（解离机械判据 + leakage=0 + I1 + 子主张全 SUPPORTED → SUPPORTED）。

    承 evaluate_root_composite 体例（Q-L13-11①）；effect_size/CI/p 由统计核
    （c1_perception_tracking）承载；mechanical_ok = 解离三断言全过（M2 SC5 先例：
    机械判据与统计 claim 分立、联合判定）。
    REV-0014 R3：Holm–Bonferroni 校正机械执行——族 = 各 claim 主判定 p
    （stat plan correction: holm_bonferroni）；校正后任一 claim 不再显著 → 该
    主张的 SUPPORTED 降级 INCONCLUSIVE（unknown ≠ negative，禁升格）。
    """
    if not constituent_results:
        raise ValueError("c1 composite requires constituent results")
    # Holm 族：各子主张的主判定 p（body claim 取其 max p = 最保守）
    claim_ps = tuple(
        float(r.p_or_bayes) if r.p_or_bayes is not None else 1.0
        for r in constituent_results
    )
    rejected, adjusted = holm_bonferroni(claim_ps, alpha)
    downgraded: list[str] = []
    effective: list[EvidenceResult] = []
    for res, rej, adj in zip(constituent_results, rejected, adjusted):
        if res.verdict is HypothesisVerdict.SUPPORTED and not rej:
            downgraded.append(f"{res.hypothesis_refs[0]}:holm_nonsignificant(adj_p={adj:.4g})")
            effective.append(EvidenceResult(
                result_id=res.result_id,
                hypothesis_refs=res.hypothesis_refs,
                stat_plan_ref=res.stat_plan_ref,
                estimand=res.estimand,
                effect_size=res.effect_size, ci=res.ci, p_or_bayes=res.p_or_bayes,
                verdict=HypothesisVerdict.INCONCLUSIVE,
                unknowns=res.unknowns, refutations=res.refutations,
                data_refs=res.data_refs, recompute_ok=res.recompute_ok,
            ))
        else:
            effective.append(res)
    refuted = [r for r in effective if r.verdict is HypothesisVerdict.REFUTED]
    supported = [r for r in effective if r.verdict is HypothesisVerdict.SUPPORTED]
    refutation_codes = [code for r in refuted for code in r.refutations]
    if refutation_codes:
        verdict = HypothesisVerdict.REFUTED
    elif (
        len(supported) == len(effective) and mechanical_ok
        and leakage_free and i1_match and recompute_ok
    ):
        verdict = HypothesisVerdict.SUPPORTED
    else:
        verdict = HypothesisVerdict.INCONCLUSIVE
    unknowns: list[Unknown] = list(statistical_core.unknowns)
    for res, rej, adj in zip(constituent_results, rejected, adjusted):
        if f"{res.hypothesis_refs[0]}:" in "".join(downgraded):
            unknowns.append(Unknown(
                reason=UnknownReason.DECISION_PATH_UNRESOLVED,
                evidence_refs=(f"holm.adj_p={adj:.6g}",),
                detail=f"REV-0014 R3：Holm 校正后降级 {res.hypothesis_refs[0]}"
                       f"（族 m={len(claim_ps)}，α={alpha}，adj_p={adj:.4g}）",
                detected_by=detected_by, virtual_time=0,
            ))
    if not mechanical_ok:
        unknowns.append(Unknown(
            reason=UnknownReason.CONFLICTING_EVIDENCE, evidence_refs=("dissociation_checks",),
            detail="dissociation mechanical checks failed（解离判据失败：形成/知觉选择性面破损）",
            detected_by=detected_by, virtual_time=0,
        ))
    if not leakage_free:
        unknowns.append(Unknown(
            reason=UnknownReason.CONFLICTING_EVIDENCE, evidence_refs=("leakage_report",),
            detail="leakage probes reported detections（C1 判定不得在泄漏未清时 SUPPORTED）",
            detected_by=detected_by, virtual_time=0,
        ))
    if not i1_match:
        unknowns.append(Unknown(
            reason=UnknownReason.CONFLICTING_EVIDENCE, evidence_refs=("recompute_report",),
            detail="I1 recompute mismatch（recorder 数据复算不 bit-exact）",
            detected_by=detected_by, virtual_time=0,
        ))
    return EvidenceResult(
        result_id=result_id,
        hypothesis_refs=("c1_models_formation",)
        + tuple(ref for r in constituent_results for ref in r.hypothesis_refs),
        stat_plan_ref=stat_plan_ref,
        estimand="c1_composite_model_formation",
        effect_size=statistical_core.effect_size,
        ci=statistical_core.ci,
        p_or_bayes=statistical_core.p_or_bayes,
        verdict=verdict,
        unknowns=tuple(unknowns),
        refutations=tuple(refutation_codes),
        data_refs=statistical_core.data_refs,
        recompute_ok=recompute_ok,
    )
