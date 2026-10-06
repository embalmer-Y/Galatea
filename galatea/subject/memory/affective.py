"""AffectiveValueTag 落盘（L06 §3/§10 affective.py——C2 实现期）。

合同（L05 §3 / c2_memory.profile §affective_write）：**L06 是唯一写者，L05 只提案**。
本模块是情感标注进入主体记忆的唯一入口：
- 目标条目必须已在库（禁凭空标注——memory_ref 不存在即 MemoryStoreViolation）；
- 标注绑定到目标条目（MemoryItem.affective 字段更新）；
- 同时在 AFFECTIVE_VALUE 子系统落一条标注条目（content_ref = memory_ref，
  source_type = SELF_GENERATED——标注源自主体感受态非知觉；lineage 指向目标，
  谱系可溯）；strength = tag.persistence（Q-L06-02 δ 分量消费的承载）。
"""
from galatea.subject.affect.value_tag import AffectiveValueTag
from galatea.subject.memory.items import ConsolidationState, MemoryItem
from galatea.subject.memory.ports import MemorySubsystem, SourceType
from galatea.kernel.packet import RepresentationLevel
from galatea.subject.memory.store import MemoryStore, MemoryStoreViolation

__all__ = ["write_affective_tag"]


def write_affective_tag(store: MemoryStore, tag: AffectiveValueTag) -> MemoryItem:
    """L05 提案 → L06 落盘（唯一写者路径；返回 AFFECTIVE_VALUE 子系统条目）。"""
    target = store.get(tag.memory_ref)
    if target is None:
        raise MemoryStoreViolation(
            f"affective tag target not in store: {tag.memory_ref!r}（禁凭空标注——L06 唯一写者纪律）"
        )
    # 绑定标注到目标条目（不可变重建 + 重写）
    bound = MemoryItem(
        item_id=target.item_id, subsystem=target.subsystem, source_type=target.source_type,
        content_ref=target.content_ref, representation_level=target.representation_level,
        strength=target.strength, created_cycle=target.created_cycle,
        last_access_cycle=target.last_access_cycle,
        consolidation_state=target.consolidation_state,
        lineage_refs=target.lineage_refs, affective=tag, access_count=target.access_count,
    )
    store.put(bound)
    entry = MemoryItem(
        item_id=f"affect.{tag.memory_ref}",
        subsystem=MemorySubsystem.AFFECTIVE_VALUE,
        source_type=SourceType.SELF_GENERATED,
        content_ref=tag.memory_ref,
        representation_level=RepresentationLevel.RECEIVED,
        strength=tag.persistence,
        created_cycle=tag.proposed_at,
        last_access_cycle=tag.proposed_at,
        consolidation_state=ConsolidationState.LABILE,
        lineage_refs=(tag.memory_ref,),
    )
    store.put(entry)
    return entry
