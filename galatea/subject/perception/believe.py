"""PerceptualBelief 构造/冻结构造（L03 §2/§10 believe.py——"信念"分 schema 承载点）。

纪律：表示层级恒为 PERCEIVED（禁提升/降级改写，L00 §8）；置信走校准标度
（calibration_version 必填）；多假设保留，禁过早塌缩；禁裸 None（typed unknown）。
F0 范围 = schema 合同；表格融合行为（fusion.py）归 C1。
"""
import enum
from dataclasses import dataclass, field

from galatea.kernel.digest import content_digest
from galatea.kernel.packet import AccessScope, ArtifactRef, Provenance
from galatea.kernel.unknown import Unknown, ensure_typed_confidence


class BeliefKind(enum.StrEnum):
    """信念类别（L03 §2：OBJECT/EVENT/STATE/SOURCE/AFFORDANCE/FIELD）。"""

    OBJECT = "OBJECT"
    EVENT = "EVENT"
    STATE = "STATE"
    SOURCE = "SOURCE"
    AFFORDANCE = "AFFORDANCE"
    FIELD = "FIELD"


@dataclass(frozen=True, slots=True)
class AltHypothesis:
    """备择假设（L03 §2：多假设保留，禁过早塌缩）。"""

    content_ref: ArtifactRef
    posterior: float


@dataclass(frozen=True, slots=True)
class PerceptualBelief:
    """知觉信念（L03 §2 对象图；subject_state 域，表示层级恒 PERCEIVED）。"""

    belief_id: str
    kind: BeliefKind
    content: ArtifactRef
    confidence: "float | Unknown"
    alternatives: tuple[AltHypothesis, ...]
    modality_support: tuple[tuple[str, tuple[str, ...]], ...]
    ood_flag: bool
    ood_score: "float | Unknown"
    calibration_version: str
    provenance: Provenance
    causal_parent_ids: tuple[str, ...]
    cycle_id: int
    representation_level: str = field(default="PERCEIVED", init=False)  # 恒定且构造不可指定（REV-0003 R4）
    access_scope: AccessScope = AccessScope.MODULE_LOCAL

    def __post_init__(self) -> None:
        if not self.belief_id or not self.calibration_version:
            raise ValueError("belief_id and calibration_version are required（校准标度 L03 §4.3）")
        ensure_typed_confidence(self.confidence, "confidence")
        if self.representation_level != "PERCEIVED":
            raise ValueError("PerceptualBelief level is fixed to PERCEIVED（禁提升/改写，L00 §8）")

    def digest(self) -> str:
        """信念内容摘要（subject_state 台账与重放比对用）。"""
        confidence_repr: object
        if isinstance(self.confidence, Unknown):
            confidence_repr = {"unknown_reason": str(self.confidence.reason.value), "detail": self.confidence.detail}
        else:
            confidence_repr = self.confidence
        return content_digest(
            {
                "belief_id": self.belief_id,
                "kind": self.kind.value,
                "content": {"digest": self.content.digest, "kind": self.content.kind},
                "confidence": confidence_repr,
                "alternatives": [{"ref": a.content_ref.digest, "posterior": a.posterior} for a in self.alternatives],
                "calibration_version": self.calibration_version,
                "cycle_id": self.cycle_id,
            }
        )
