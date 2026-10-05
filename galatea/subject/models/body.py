"""身体模型（L04 §4.1 BodyBelief/§10 body.py；telemetry 直填 = 禁）。

信念唯一来源 = L02 INTERO/PROPRIO 帧（sources 必须为该二模态帧 id，构造期强制）；
能力估计 = 静态合同语义（Q-L08-09①：MW0 五原语白名单 → FEASIBLE；越界 →
INFEASIBLE；不可静态判定 → Unknown(CAPABILITY_LIMIT)）——C1 起 L08 C-1 接管落点。
load_belief = 0.0（M0 冻结简化 Q-L01-09⑥，schema 占位语义、非估计值）。
"""
from dataclasses import dataclass, field
from enum import StrEnum

from galatea.kernel.digest import content_digest
from galatea.subject.sensorium.ports import (
    InteroSensations,
    ProprioFeatures,
    SensoryFrame,
    SensoryModality,
)

#: MW0 五原语（m0_mw0.profile action_primitives 冻结；f0_action_contract 白名单同源）
MW0_PRIMITIVES: tuple[str, ...] = ("move", "forage", "eat", "rest", "look")


class CapabilityStatus(StrEnum):
    """能力估计状态（L04 §4.1）。"""

    FEASIBLE = "FEASIBLE"
    DEGRADED = "DEGRADED"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class CapabilityEstimate:
    """能力估计（证据引用强制；C1 = 静态合同 + 观测后果面）。"""

    action_class: str
    status: CapabilityStatus
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.evidence_refs:
            raise ValueError("CapabilityEstimate requires evidence_refs（禁无证据能力主张）")


@dataclass(frozen=True, slots=True)
class InterfaceBoundary:
    """身体接口边界（L04 §4.1：included/excluded/confidence）。"""

    included: tuple[str, ...]
    excluded: tuple[str, ...]
    confidence: "float | str"      # C1 = "unresolved_pending_evaluation"（Q-L04-03 统计判据在 L13）


@dataclass(frozen=True, slots=True)
class BodyBelief:
    """身体信念（L04 §4.1；sources 必须是 INTERO/PROPRIO 帧）。"""

    body_id: str
    energy_belief: float
    integrity_belief: float
    load_belief: float
    orientation: str | None
    boundary: InterfaceBoundary
    capability: tuple[CapabilityEstimate, ...]
    sources: tuple[str, ...]
    cycle_id: int
    content_digest: str = field(default="")

    def __post_init__(self) -> None:
        if not self.sources:
            raise ValueError("BodyBelief 禁匿名（sources required，L04 §2.1 model.sensory_in）")
        if self.load_belief != 0.0:
            raise ValueError("load_belief must be 0.0 at M0（Q-L01-09⑥ schema 占位）")
        computed = content_digest({
            "body_id": self.body_id,
            "energy_belief": self.energy_belief,
            "integrity_belief": self.integrity_belief,
            "orientation": self.orientation,
            "sources": list(self.sources),
            "cycle_id": self.cycle_id,
        })
        if self.content_digest and self.content_digest != computed:
            raise ValueError(f"BodyBelief digest mismatch（改写检出，{self.body_id}）")
        object.__setattr__(self, "content_digest", computed)


class TelemetrySourceRejected(ValueError):
    """telemetry 来源试图进入 BodyBelief（L04 §8 禁写路径：telemetry → BodyBelief）。"""


def static_capability(primitives: tuple[str, ...] = MW0_PRIMITIVES) -> tuple[CapabilityEstimate, ...]:
    """静态合同能力集（Q-L08-09①：白名单内 FEASIBLE；evidence = 冻结合同引用）。"""
    return tuple(
        CapabilityEstimate(
            action_class=p, status=CapabilityStatus.FEASIBLE,
            evidence_refs=("f0_action_contract@v1.0.containment_whitelist_mw0",),
        )
        for p in sorted(primitives)
    )


def capability_for(action_class: str) -> CapabilityEstimate:
    """单动作类静态判定（越界 INFEASIBLE；不可判定 → Unknown 面）。"""
    if action_class in MW0_PRIMITIVES:
        return CapabilityEstimate(
            action_class=action_class, status=CapabilityStatus.FEASIBLE,
            evidence_refs=("f0_action_contract@v1.0.containment_whitelist_mw0",),
        )
    return CapabilityEstimate(
        action_class=action_class, status=CapabilityStatus.INFEASIBLE,
        evidence_refs=("f0_action_contract@v1.0.containment_whitelist_mw0",),
    )


def build_body_belief(
    intero_frame: SensoryFrame | None, proprio_frame: SensoryFrame | None,
    body_id: str, cycle_id: int,
) -> BodyBelief:
    """从内感受/本体感受帧构建身体信念（禁 telemetry：来源按模态白名单强制）。"""
    sources: list[str] = []
    energy = 0.0
    integrity = 0.0
    orientation: str | None = None
    if intero_frame is not None:
        if intero_frame.modality is not SensoryModality.INTERO:
            raise TelemetrySourceRejected(
                f"{intero_frame.frame_id}: BodyBelief sources must be INTERO（telemetry 直填 = 禁）"
            )
        features = intero_frame.features
        if not isinstance(features, InteroSensations):
            raise TelemetrySourceRejected(f"{intero_frame.frame_id}: non-intero features")
        energy = features.energy_level
        integrity = features.integrity_level
        sources.append(intero_frame.frame_id)
    if proprio_frame is not None:
        if proprio_frame.modality is not SensoryModality.PROPRIO:
            raise TelemetrySourceRejected(
                f"{proprio_frame.frame_id}: BodyBelief sources must be PROPRIO"
            )
        features = proprio_frame.features
        if not isinstance(features, ProprioFeatures):
            raise TelemetrySourceRejected(f"{proprio_frame.frame_id}: non-proprio features")
        orientation = features.orientation
        sources.append(proprio_frame.frame_id)
    if not sources:
        raise ValueError("body belief requires at least one body frame（观测缺失 → 调用方 typed Unknown）")
    return BodyBelief(
        body_id=body_id,
        energy_belief=energy,
        integrity_belief=integrity,
        load_belief=0.0,
        orientation=orientation,
        boundary=InterfaceBoundary(
            included=("INTERO", "PROPRIO"),
            excluded=("telemetry", "EXT carriers", "truth_ref"),
            confidence="unresolved_pending_evaluation",
        ),
        capability=static_capability(),
        sources=tuple(sources),
        cycle_id=cycle_id,
    )
