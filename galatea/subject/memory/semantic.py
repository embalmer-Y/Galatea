"""semantic 子系统编码（L06 §4.4 语义抽象的 C2 面 / §9 C2 门槛）。

C2 范围 = 抽象编码接口 + 谱系强制（防伪抽象）：SEMANTIC 条目必须指向真实在库的
EPISODIC 源（parent 谱系可回溯——L06 §4.4"任一语义结论可回溯到源情景"）；
完整巩固流水线（T6 触发条件/聚类粒度）= Q-L06-04（C5）。
"""
from galatea.kernel.packet import RepresentationLevel
from galatea.subject.memory.items import ConsolidationState, LineageBreak, MemoryItem
from galatea.subject.memory.ports import MemorySubsystem, SourceType
from galatea.subject.memory.store import MemoryStore

__all__ = ["encode_semantic"]


def encode_semantic(
    store: MemoryStore,
    item_id: str,
    content_ref: str,
    source_item_ids: tuple[str, ...],
    created_cycle: int,
    strength: float = 0.5,
) -> MemoryItem:
    """语义条目编码（谱系强制：全部源必须在库且为 EPISODIC——否则 LineageBreak）。"""
    if not source_item_ids:
        raise LineageBreak("semantic abstraction requires at least one episodic source（禁无源抽象）")
    for src_id in source_item_ids:
        src = store.get(src_id)
        if src is None or src.subsystem is not MemorySubsystem.EPISODIC:
            raise LineageBreak(
                f"semantic lineage broken: source {src_id!r} not an in-store episodic item（防伪抽象，L06 §4.4）"
            )
    item = MemoryItem(
        item_id=item_id,
        subsystem=MemorySubsystem.SEMANTIC,
        source_type=SourceType.SELF_GENERATED,      # 抽象由主体提炼（源情景谱系承载 PERCEIVED 链）
        content_ref=content_ref,
        representation_level=RepresentationLevel.RECEIVED,
        strength=strength,
        created_cycle=created_cycle,
        last_access_cycle=created_cycle,
        consolidation_state=ConsolidationState.LABILE,
        lineage_refs=source_item_ids,               # parent 谱系 = 源情景 ids（断裂可检出）
    )
    store.put(item)
    return item
