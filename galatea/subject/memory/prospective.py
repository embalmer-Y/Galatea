"""prospective 子系统编码（L06 §2.1 mem.goal_in / §9 C2 门槛）。

合同：prospective **唯一合法来源 = L08 OwnedGoal / GoalSettlement**（L06 §1
八子系统定义）——goal_ref + origin_receipt 双强制（缺一即拒）；L08 完整接线 = C3
（承诺/结算消费），C2 = 子系统可用 + 来源限制合同在位。
"""
from galatea.kernel.packet import RepresentationLevel
from galatea.subject.memory.items import ConsolidationState, MemoryItem
from galatea.subject.memory.ports import MemorySubsystem, SourceType
from galatea.subject.memory.store import MemoryStore, MemoryStoreViolation

__all__ = ["encode_prospective", "ProspectiveReminder"]

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProspectiveReminder:
    """前瞻提醒（L06 §2.2 mem.prospective_due：goal_ref + due 条件 + 来源回执）。"""

    memory_ref: str
    goal_ref: str
    due_condition: str
    origin_receipt: str


def encode_prospective(
    store: MemoryStore,
    item_id: str,
    goal_ref: str,
    due_condition: str,
    origin_receipt: str,
    created_cycle: int,
    source_type: SourceType = SourceType.SELF_GENERATED,
) -> MemoryItem:
    """前瞻条目编码（源限 L08：goal_ref/origin_receipt 强制；语言源拒绝——D-13 同族纪律）。"""
    if not goal_ref or not origin_receipt:
        raise MemoryStoreViolation(
            "prospective requires goal_ref + origin_receipt（唯一合法来源 = L08 OwnedGoal，L06 §2.1）"
        )
    if source_type is SourceType.LANGUAGE_INPUT:
        raise MemoryStoreViolation(
            "LANGUAGE_INPUT cannot ground prospective reminders（语言非承诺来源，D-13 纪律族）"
        )
    item = MemoryItem(
        item_id=item_id,
        subsystem=MemorySubsystem.PROSPECTIVE,
        source_type=source_type,
        content_ref=goal_ref,
        representation_level=RepresentationLevel.RECEIVED,
        strength=0.5,
        created_cycle=created_cycle,
        last_access_cycle=created_cycle,
        consolidation_state=ConsolidationState.LABILE,
        lineage_refs=(origin_receipt,),
    )
    store.put(item)
    return item
