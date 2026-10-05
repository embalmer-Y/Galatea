"""身体纳入三判据检验（L04 §4.4/§10 ownership.py；Q-L04-03 冻结效应量在 L13 评价）。

C1 运行时义务 = 三个判据量**可计算、可消融、证据引用齐全**；"已纳入"主张本身
是统计判据（Q-L04-03：三判据各 d≥0.4 且联合成立，L13 统计计划）——运行时禁发
"已纳入"布尔（防配置声明冒充证据，HLD §13.1）。判据不可计算 →
BodyOwnershipUnresolved → boundary.confidence 降级。
"""
from dataclasses import dataclass

from galatea.kernel.unknown import Unknown, UnknownReason
from galatea.subject.models.body import BodyBelief
from galatea.subject.sensorium.ports import SensoryFrame


@dataclass(frozen=True, slots=True)
class CriterionStatus:
    """单判据状态（quantity 可复算；evidence_refs 强制；不可计算 → computable=False）。"""

    name: str
    computable: bool
    quantity: "float | Unknown"
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BodyOwnershipUnresolved(ValueError):
    """身体纳入判据不满足（L04 §6：boundary.confidence 降级，禁默认纳入）。"""

    criteria_status: tuple[CriterionStatus, ...]

    def __str__(self) -> str:
        unmet = [c.name for c in self.criteria_status if not c.computable]
        return f"body ownership unresolved: unmet criteria = {unmet}"


def sensory_motor_consistency(
    body_belief: BodyBelief, body_frames: tuple[SensoryFrame, ...],
    predictions_body: tuple[float, float] | None, cycle: int,
) -> CriterionStatus:
    """判据 1 感觉运动一致性：身体预测与形成帧残差（Q-L04-04 身体态维度）。"""
    refs = tuple(f.frame_id for f in body_frames)
    if predictions_body is None or not body_frames:
        return CriterionStatus(
            name="sensory_motor_consistency", computable=False,
            quantity=Unknown(
                reason=UnknownReason.MISSING_SIGNAL,
                evidence_refs=refs,
                detail="no body prediction/frame pair（消融检出面：移除预测源 → 判据不可计算）",
                detected_by="models.ownership",
                virtual_time=cycle,
            ),
            evidence_refs=refs,
        )
    residual = abs(predictions_body[0] - body_belief.energy_belief) + abs(
        predictions_body[1] - body_belief.integrity_belief
    )
    return CriterionStatus(
        name="sensory_motor_consistency", computable=True, quantity=residual,
        evidence_refs=refs,
    )


def cross_modal_consistency(
    center_cell_posterior: float | None, proprio_orientation: str | None, cycle: int,
) -> CriterionStatus:
    """判据 2 跨模态一致性：外感受窗中心（身体所在格）与本体感受信念对应
    （egocentric 化判据 2，Q-L04-08：MW0 = 网格位置 vs BodyTruth 的信念侧）。"""
    refs: tuple[str, ...] = ()
    if center_cell_posterior is None or proprio_orientation is None:
        return CriterionStatus(
            name="cross_modal_consistency", computable=False,
            quantity=Unknown(
                reason=UnknownReason.INSUFFICIENT_OBSERVATION,
                evidence_refs=refs,
                detail="window center / proprio missing（消融检出面）",
                detected_by="models.ownership",
                virtual_time=cycle,
            ),
            evidence_refs=refs,
        )
    agreement = center_cell_posterior if proprio_orientation else 0.0
    return CriterionStatus(
        name="cross_modal_consistency", computable=True, quantity=agreement,
        evidence_refs=refs,
    )


def attribution_evidence(attribution_refs: tuple[str, ...], cycle: int) -> CriterionStatus:
    """判据 3 归属侧证：自发动作预测误差 < 强迫动作（L01 电池提供，L10 归属消费）。"""
    if not attribution_refs:
        return CriterionStatus(
            name="attribution_evidence", computable=False,
            quantity=Unknown(
                reason=UnknownReason.ATTRIBUTION_UNRESOLVED,
                evidence_refs=(),
                detail="no attribution battery evidence refs（L10 归属域输入缺席）",
                detected_by="models.ownership",
                virtual_time=cycle,
            ),
            evidence_refs=(),
        )
    return CriterionStatus(
        name="attribution_evidence", computable=True, quantity=1.0,
        evidence_refs=attribution_refs,
    )


def assess_ownership(
    body_belief: BodyBelief, body_frames: tuple[SensoryFrame, ...],
    predictions_body: tuple[float, float] | None,
    center_cell_posterior: float | None, proprio_orientation: str | None,
    attribution_refs: tuple[str, ...], cycle: int,
) -> tuple[CriterionStatus, ...]:
    """三判据联合检验（任一不可计算 → BodyOwnershipUnresolved 可由调用方抛出）。"""
    status = (
        sensory_motor_consistency(body_belief, body_frames, predictions_body, cycle),
        cross_modal_consistency(center_cell_posterior, proprio_orientation, cycle),
        attribution_evidence(attribution_refs, cycle),
    )
    return status


def ownership_unmet(status: tuple[CriterionStatus, ...]) -> bool:
    """联合成立判定（三判据须全部可计算——主张降级面）。"""
    return any(not c.computable for c in status)
