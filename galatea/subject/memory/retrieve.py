"""检索：确定性打分/tie-break/预算/空命中 Unknown（L06 §4.2/§10 retrieve.py）。

- M2 面（`retrieve`，Q-G00-11 冻结语义）：打分 = 衰减后强度——**签名与行为冻结**
  （SC6 正式 runner I1 复算依赖，禁改动）；
- C2 面（`retrieve_c2`，Q-L06-02 裁决 2026-10-06）：五分量等权 1:1:1:1:1
  score = cue_sim + strength + recency + |affective.valence| + reliability；
  recency = max(0, 1 − age/64)（线性窗 = T6 拍，零新常数）；reliability = strength
  （M2 映射维持）；无标注条目 δ 分量 = 0（缺省中性）；tie-break
  (score desc, subsystem, memory_id)；预算 = c2_memory.profile top_k（4）。
mem.retrieve 服务 L03/L04/L07/L08/L09 查询（L06 §5 T4 挂点）。
"""
from dataclasses import dataclass

from galatea.kernel.unknown import Unknown, UnknownReason
from galatea.subject.memory.items import MemoryItem
from galatea.subject.memory.ports import MemorySubsystem, RecalledContent
from galatea.subject.memory.store import M2ContinuityProfile, MemoryStore

__all__ = ["RetrievalQuery", "retrieve", "C2RetrievalQuery", "retrieve_c2"]


@dataclass(frozen=True, slots=True)
class RetrievalQuery:
    """查询（L06 §2.1 mem.retrieve 的 M2 最小形态：子系统 + 时点；cues/预算细化 C2）。"""

    subsystem: MemorySubsystem
    retrieved_at: int


def retrieve(
    store: MemoryStore,
    profile: M2ContinuityProfile,
    query: RetrievalQuery,
) -> tuple[RecalledContent, ...] | Unknown:
    """确定性检索（M2 冻结语义：strength 降序 + id 升序；空命中 Unknown——禁静默空列表冒充命中）。"""
    items = store.list_subsystem(query.subsystem)
    scored = sorted(items, key=lambda i: (-i.strength, i.item_id))
    if not scored:
        return Unknown(
            reason=UnknownReason.INSUFFICIENT_OBSERVATION,
            evidence_refs=(f"query:{query.subsystem.value}",),
            detail=f"no memories in subsystem {query.subsystem.value}",
            detected_by="memory.retrieve",
            virtual_time=query.retrieved_at,
        )
    hits = scored[: profile.retrieval_top_k]
    return tuple(
        RecalledContent(
            memory_ref=item.item_id,
            subsystem=item.subsystem,
            source_type=item.source_type,
            content_ref=item.content_ref,
            reliability=item.strength,   # M2 最小映射：可靠度 = 强度（metamemory = C2/C4）
            retrieved_at=query.retrieved_at,
        )
        for item in hits
    )


@dataclass(frozen=True, slots=True)
class C2RetrievalQuery:
    """C2 查询（Q-L06-02：cues 枚举匹配 + 时点——recency 窗锚）。"""

    subsystem: MemorySubsystem
    retrieved_at: int
    cues: tuple[str, ...] = ()        # 枚举匹配域：content_ref / lineage_refs / 子系统名


def _cue_sim(item: MemoryItem, cues: tuple[str, ...]) -> float:
    """枚举匹配（L06 §4.2 原文：MW0 期 cue_sim = 枚举匹配 0/1——可手算）。"""
    if not cues:
        return 0.0
    fields = {item.content_ref, *item.lineage_refs, item.subsystem.value}
    return 1.0 if any(c in fields for c in cues) else 0.0


def _c2_score(item: MemoryItem, cues: tuple[str, ...], now: int) -> float:
    """五分量等权打分（Q-L06-02②；全部确定性可手算）。"""
    age = max(0, now - item.last_access_cycle)
    recency = max(0.0, 1.0 - age / 64.0)
    valence_abs = 0.0 if item.affective is None else abs(item.affective.valence)
    return (
        _cue_sim(item, cues)
        + item.strength
        + recency
        + valence_abs
        + item.strength        # reliability = strength（M2 映射维持，Q-L06-02②）
    )


def retrieve_c2(
    store: MemoryStore,
    top_k: int,
    query: C2RetrievalQuery,
) -> tuple[RecalledContent, ...] | Unknown:
    """C2 确定性检索（五分量等权 + tie-break (score desc, subsystem, memory_id) + 预算）。"""
    items = store.list_subsystem(query.subsystem)
    scored = sorted(items, key=lambda i: (-_c2_score(i, query.cues, query.retrieved_at),
                                          i.subsystem.value, i.item_id))
    if not scored:
        return Unknown(
            reason=UnknownReason.INSUFFICIENT_OBSERVATION,
            evidence_refs=(f"query:{query.subsystem.value}",),
            detail=f"no memories in subsystem {query.subsystem.value}",
            detected_by="memory.retrieve_c2",
            virtual_time=query.retrieved_at,
        )
    hits = scored[:top_k]
    return tuple(
        RecalledContent(
            memory_ref=item.item_id,
            subsystem=item.subsystem,
            source_type=item.source_type,
            content_ref=item.content_ref,
            reliability=item.strength,
            retrieved_at=query.retrieved_at,
        )
        for item in hits
    )
