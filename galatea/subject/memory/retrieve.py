"""检索：确定性打分/tie-break/预算/空命中 Unknown（L06 §4.2/§10 retrieve.py——M2 最小切片）。

M2 打分 = 衰减后强度（完整权重 α/β/γ/δ/ε = C2 裁决，Q-L06-02）；tie-break =
(strength desc, item_id asc)——禁容器序依赖（L00 §8）；预算 = retrieval_top_k
（m2_continuity.profile，Q-G00-11）。mem.retrieve 服务 L03/L04/L07/L08/L09 查询
（L06 §5 T4 挂点）——M2 期 L08 目标查询经本端口（SC6 carryover 的合法通路）。
"""
from dataclasses import dataclass

from galatea.kernel.unknown import Unknown, UnknownReason
from galatea.subject.memory.ports import MemorySubsystem, RecalledContent
from galatea.subject.memory.store import M2ContinuityProfile, MemoryStore

__all__ = ["RetrievalQuery", "retrieve"]


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
    """确定性检索（同库同 query 同结果；L06 §10"空命中 Unknown"——禁静默空列表冒充命中）。"""
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
