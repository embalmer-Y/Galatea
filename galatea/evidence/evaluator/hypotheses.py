"""EvidenceResult schema 与判定执行（L13 §2.2 evd.evidence_result / §4.3 / §10 hypotheses.py）。

纪律：三态判定 + 未知清单（unknown ≠ negative）；root 门槛载体（R0）；
含统计计划引用与可复算标志。判定执行（本模块下半部，M2 准备单元交付）：
SUPPORTED = 达冻结阈值 **且负控通过**（L13 §4.3）；INCONCLUSIVE = 功效不足或冲突；
REFUTED = 反证条件成立。确定性阶段统计量退化（一臂方差为 0）按 ADR-G-0007
口径处理：effect_size = estimand 标度（配对采用率差），CI 退化区间如实呈现，
饱和判定以 estimand 上确界单调性为准。
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
