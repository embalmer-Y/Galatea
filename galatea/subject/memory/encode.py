"""working/episodic 编码、强度初始化、衰减（L06 §4/§10 encode.py——M2 最小切片）。

纪律：来源类型强制（缺省 UNKNOWN 需显式声明——M2 允许 UNKNOWN 编码但该来源
禁用于连续性主张，L06 §2.2）；LANGUAGE_INPUT 禁写 episodic 经历（D-13）；
强度初值与衰减乘子 = m2_continuity.profile 冻结（Q-G00-11）。
"""
from galatea.kernel.packet import RepresentationLevel
from galatea.subject.memory.items import ConsolidationState, MemoryItem
from galatea.subject.memory.ports import MemorySubsystem, SourceType
from galatea.subject.memory.store import M2ContinuityProfile, MemoryStore, MemoryStoreViolation

__all__ = ["encode_working", "encode_episodic", "apply_decay"]


def encode_working(
    store: MemoryStore,
    profile: M2ContinuityProfile,
    item_id: str,
    content_ref: str,
    representation_level: RepresentationLevel,
    source_type: SourceType,
    created_cycle: int,
    lineage_refs: tuple[str, ...] = (),
) -> MemoryItem:
    """工作记忆编码（ttl 有限——容量上界由 store 容量校验承载，C2 换 LRU 策略）。"""
    if store.count(MemorySubsystem.WORKING) >= profile.memory_working_capacity:
        raise MemoryStoreViolation(
            f"working capacity {profile.memory_working_capacity} exceeded（溢出策略 C2 裁决，Q-L06-01）"
        )
    item = MemoryItem(
        item_id=item_id,
        subsystem=MemorySubsystem.WORKING,
        source_type=source_type,
        content_ref=content_ref,
        representation_level=representation_level,
        strength=profile.strength_initial,
        created_cycle=created_cycle,
        last_access_cycle=created_cycle,
        lineage_refs=lineage_refs,
    )
    store.put(item)
    return item


def encode_episodic(
    store: MemoryStore,
    profile: M2ContinuityProfile,
    item_id: str,
    content_ref: str,
    representation_level: RepresentationLevel,
    source_type: SourceType,
    created_cycle: int,
    lineage_refs: tuple[str, ...] = (),
) -> MemoryItem:
    """情景编码（经历切片）：LANGUAGE_INPUT 即拒（D-13：语言不能写 episodic 经历）。"""
    if source_type is SourceType.LANGUAGE_INPUT:
        raise MemoryStoreViolation(
            "LANGUAGE_INPUT cannot encode episodic experience（D-13，L06 §2.2；test_language_to_episodic_blocked）"
        )
    if store.count(MemorySubsystem.EPISODIC) >= profile.memory_episodic_capacity:
        raise MemoryStoreViolation(
            f"episodic capacity {profile.memory_episodic_capacity} exceeded（溢出策略 C2 裁决，Q-L06-01）"
        )
    item = MemoryItem(
        item_id=item_id,
        subsystem=MemorySubsystem.EPISODIC,
        source_type=source_type,
        content_ref=content_ref,
        representation_level=representation_level,
        strength=profile.strength_initial,
        created_cycle=created_cycle,
        last_access_cycle=created_cycle,
        lineage_refs=lineage_refs,
    )
    store.put(item)
    return item


def apply_decay(store: MemoryStore, profile: M2ContinuityProfile, now_t6_tick: int) -> int:
    """每 T6 拍强度衰减（m2_continuity.profile decay_factor_per_t6=0.9；C2 换 τ_sub 谱经 Q-L06-03）。

    衰减作用于 LABILE 条目（PROTECTED/CONSOLIDATED 免疫——M2 期无 PROTECTED 写者，
    保护集记忆侧检查随 C2 protection.py 落地）。返回受影响条目数。
    """
    affected = 0
    for subsystem in (MemorySubsystem.WORKING, MemorySubsystem.EPISODIC):
        for item in store.list_subsystem(subsystem):
            if item.consolidation_state is not ConsolidationState.LABILE:
                continue
            updated = MemoryItem(
                item_id=item.item_id,
                subsystem=item.subsystem,
                source_type=item.source_type,
                content_ref=item.content_ref,
                representation_level=item.representation_level,
                strength=round(item.strength * profile.decay_factor_per_t6, 6),
                created_cycle=item.created_cycle,
                last_access_cycle=item.last_access_cycle,
                consolidation_state=item.consolidation_state,
                lineage_refs=item.lineage_refs,
            )
            store.put(updated)
            affected += 1
    return affected
