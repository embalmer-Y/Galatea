"""ModelMismatch 检测（L04 §2.2 model.mismatch/§10 mismatch.py）。

C1 检测面 = 结构性失配（无冻结阈值——量级由消费者策略解释，L08/L09 C3 接入）：
- CAPABILITY_CONTRADICTION（L04 §6 行 7）：观测执行后果与能力估计矛盾；
- PERSISTENCE_VIOLATION：高置信占据信念被直接观测反驳（持续性语义的可检失败面）；
- POSE_BRANCH_DIVERGENCE：位姿候选分叉（Q-L04-09③ 分支事件）。
禁写目标/动作（mismatch 是 L08 动机源输入之一，C3 接线）。
"""
from dataclasses import dataclass
from enum import StrEnum

from galatea.subject.models.body import BodyBelief
from galatea.subject.models.world import WorldStateBelief


class MismatchKind(StrEnum):
    """失配类型（L04 §6 失败模式映射）。"""

    CAPABILITY_CONTRADICTION = "CAPABILITY_CONTRADICTION"
    PERSISTENCE_VIOLATION = "PERSISTENCE_VIOLATION"
    POSE_BRANCH_DIVERGENCE = "POSE_BRANCH_DIVERGENCE"


@dataclass(frozen=True, slots=True)
class ModelMismatch:
    """模型失配记录（kind, magnitude, evidence_refs[]；无阈值判定——量级解释归消费者）。"""

    kind: MismatchKind
    magnitude: float
    evidence_refs: tuple[str, ...]
    cycle_id: int


def detect_mismatches(
    belief: WorldStateBelief, body: BodyBelief | None,
    failed_actions: tuple[str, ...], cycle: int,
) -> tuple[ModelMismatch, ...]:
    """结构失配检测（确定性；无冻结阈值——只报量级与证据）。"""
    out: list[ModelMismatch] = []
    if len(belief.pose_candidates) > 1:
        out.append(ModelMismatch(
            kind=MismatchKind.POSE_BRANCH_DIVERGENCE,
            magnitude=float(len(belief.pose_candidates)),
            evidence_refs=tuple(p.candidate_id for p in belief.pose_candidates),
            cycle_id=cycle,
        ))
    if body is not None and failed_actions:
        out.append(ModelMismatch(
            kind=MismatchKind.CAPABILITY_CONTRADICTION,
            magnitude=float(len(failed_actions)),
            evidence_refs=tuple(failed_actions) + tuple(c.evidence_refs[0] for c in body.capability),
            cycle_id=cycle,
        ))
    return tuple(out)
