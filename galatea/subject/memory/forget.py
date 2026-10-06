"""遗忘控制：衰减谱、访问增强、显式遗忘 tombstone、容量溢出降级（L06 §4.3/§4.5/§10 forget.py——C2）。

Q-L06-03：τ_sub 幂梯（working 4 / episodic+affective_value 256 / 其余 1024）；
衰减算子 = strength × (1−1/τ) **每 T6 拍**（consolidation_tick 唯一触发——L06 §2.1）；
访问增强 = 每命中 +0.125 上界 1.0（Q-L04-10 Laplace 等价步长先例）；PROTECTED 豁免。
Q-L06-01：溢出 = 强制降级最旧 LABILE → ARCHIVED（(last_access, item_id) 升序确定性全序；
禁拒写禁删除）；遗忘是**显式状态转移**（FORGOTTEN + tombstone 保留，非删除）——
PROTECTED 条目遗忘尝试 = ProtectionViolation（S2，L06 §6）。
"""
from dataclasses import dataclass, field

from galatea.kernel.digest import content_digest
from galatea.subject.memory.items import ConsolidationState, MemoryItem
from galatea.subject.memory.ports import MemorySubsystem
from galatea.subject.memory.store import MemoryStore
from galatea.subject.c2profile import C2MemoryParams

__all__ = ["ProtectionViolation", "DecayReceipt", "decay_pass", "boost_on_access", "forget_item", "enforce_overflow"]


class ProtectionViolation(RuntimeError):
    """保护集条目被要求遗忘/降级（L06 §4.5/§6：S2 阻断）。"""


@dataclass(frozen=True, slots=True)
class DecayReceipt:
    """T6 衰减拍回执（证据侧；digest = 复算载体）。"""

    tick_cycle: int
    decayed_count: int
    protected_skipped: int
    content_digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "content_digest", content_digest({
            "tick": self.tick_cycle, "decayed": self.decayed_count,
            "protected": self.protected_skipped,
        }))


def decay_pass(store: MemoryStore, params: C2MemoryParams, tick_cycle: int) -> DecayReceipt:
    """T6 衰减拍（全部子系统一遍；PROTECTED 跳过；FORGOTTEN 不再衰减）。"""
    decayed = 0
    protected = 0
    for subsystem in MemorySubsystem:
        for item in store.list_subsystem(subsystem, include_forgotten=True):
            if item.consolidation_state is ConsolidationState.PROTECTED:
                protected += 1
                continue
            if item.consolidation_state is ConsolidationState.FORGOTTEN:
                continue
            factor = 1.0 - 1.0 / params.tau_sub[subsystem]
            store.put(MemoryItem(
                item_id=item.item_id, subsystem=item.subsystem, source_type=item.source_type,
                content_ref=item.content_ref, representation_level=item.representation_level,
                strength=item.strength * factor, created_cycle=item.created_cycle,
                last_access_cycle=item.last_access_cycle,
                consolidation_state=item.consolidation_state,
                lineage_refs=item.lineage_refs, affective=item.affective,
                access_count=item.access_count,
            ))
            decayed += 1
    return DecayReceipt(tick_cycle=tick_cycle, decayed_count=decayed, protected_skipped=protected)


def boost_on_access(store: MemoryStore, params: C2MemoryParams, item_ids: tuple[str, ...],
                    cycle: int) -> tuple[str, ...]:
    """访问增强（检索命中面调用：+0.125 上界 1.0 + last_access/access_count 更新）。"""
    boosted: list[str] = []
    for item_id in item_ids:
        item = store.get(item_id)
        if item is None:
            continue
        store.put(MemoryItem(
            item_id=item.item_id, subsystem=item.subsystem, source_type=item.source_type,
            content_ref=item.content_ref, representation_level=item.representation_level,
            strength=min(1.0, item.strength + params.access_boost),
            created_cycle=item.created_cycle, last_access_cycle=cycle,
            consolidation_state=item.consolidation_state, lineage_refs=item.lineage_refs,
            affective=item.affective, access_count=item.access_count + 1,
        ))
        boosted.append(item_id)
    return tuple(boosted)


def forget_item(store: MemoryStore, item_id: str, reason: str) -> MemoryItem:
    """显式遗忘（tombstone：状态 FORGOTTEN + 原因留痕，行保留可审计——非删除）。"""
    item = store.get(item_id)
    if item is None:
        raise ValueError(f"unknown item: {item_id!r}")
    if item.consolidation_state is ConsolidationState.PROTECTED:
        raise ProtectionViolation(
            f"PROTECTED item cannot be forgotten: {item_id!r}（L06 §4.5 保护集，S2 阻断）"
        )
    if item.consolidation_state is ConsolidationState.FORGOTTEN:
        return item   # 幂等（tombstone 已在）
    forgotten = MemoryItem(
        item_id=item.item_id, subsystem=item.subsystem, source_type=item.source_type,
        content_ref=item.content_ref, representation_level=item.representation_level,
        strength=item.strength, created_cycle=item.created_cycle,
        last_access_cycle=item.last_access_cycle,
        consolidation_state=ConsolidationState.FORGOTTEN,
        lineage_refs=item.lineage_refs + (f"tombstone:{reason}",),
        affective=item.affective, access_count=item.access_count,
    )
    store.put(forgotten)
    return forgotten


def enforce_overflow(store: MemoryStore, params: C2MemoryParams) -> tuple[str, ...]:
    """容量溢出降级（Q-L06-01②③：最旧 LABILE → ARCHIVED，确定性全序，留痕可审计）。"""
    demoted: list[str] = []
    for subsystem, cap in params.capacities.items():
        items = [i for i in store.list_subsystem(subsystem, include_forgotten=True)
                 if i.consolidation_state is not ConsolidationState.FORGOTTEN]
        overflow = len(items) - cap
        if overflow <= 0:
            continue
        # (last_access 升序, item_id 升序) —— 最旧先降；PROTECTED 跳过（保护集不可降级）
        candidates = sorted(
            (i for i in items if i.consolidation_state is not ConsolidationState.PROTECTED),
            key=lambda i: (i.last_access_cycle, i.item_id),
        )
        if len(candidates) < overflow:
            raise ProtectionViolation(
                f"overflow in {subsystem.value} cannot be resolved without demoting PROTECTED items（L06 §4.5）"
            )
        for item in candidates[:overflow]:
            store.put(MemoryItem(
                item_id=item.item_id, subsystem=item.subsystem, source_type=item.source_type,
                content_ref=item.content_ref, representation_level=item.representation_level,
                strength=item.strength, created_cycle=item.created_cycle,
                last_access_cycle=item.last_access_cycle,
                consolidation_state=ConsolidationState.ARCHIVED,
                lineage_refs=item.lineage_refs + ("demote:overflow",),
                affective=item.affective, access_count=item.access_count,
            ))
            demoted.append(item.item_id)
    return tuple(demoted)
