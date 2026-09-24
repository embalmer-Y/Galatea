"""EvidenceResult schema（L13 §2.2 evd.evidence_result / §10 hypotheses.py——"结论"分 schema 承载点）。

纪律：三态判定 + 未知清单（unknown ≠ negative）；root 门槛载体（R0）；
含统计计划引用与可复算标志。F0 范围 = schema 合同（L13 §9 F0 行）；
判定执行逻辑归 R0/E1。
"""
import enum
from dataclasses import dataclass

from galatea.kernel.unknown import Unknown


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
