"""递归回路、深度上界与去重窗（L07 §4.4/§10 recurse.py）。

Q-L07-04：depth_max=3（超深 Unknown(CAPABILITY_LIMIT) 停止递归——递归是能力
不是无限自我激励）；帧 TTL = 去重 TTL = 4 cycles（= 2×N2）；同 content_digest
在去重窗内重复提案 → DUPLICATE（防递归爆涨）；过期帧引用 = StaleFrameReference。
"""
from galatea.kernel.unknown import Unknown, UnknownReason
from galatea.subject.workspace.frame import WorkspaceFrame
from galatea.subject.workspace.ports import StaleFrameReference

__all__ = ["DedupRegistry", "recursion_gate", "assert_frame_current"]


class DedupRegistry:
    """去重窗状态（content_digest → 到期拍；窗口 = dedup_ttl——pipeline 持有）。"""

    def __init__(self, ttl: int) -> None:
        self.ttl = ttl
        self._seen: dict[str, int] = {}

    def note(self, content_digest: str, cycle: int) -> None:
        """登记/刷新（帧发布或提案入池时）。"""
        self._seen[content_digest] = cycle + self.ttl

    def duplicates(self, digests: tuple[str, ...], cycle: int) -> frozenset[str]:
        """判定重复（窗内已见 → 该 digest 标记重复；顺手清理过期窗项）。"""
        self._seen = {d: exp for d, exp in self._seen.items() if exp > cycle}
        return frozenset(d for d in digests if d in self._seen)


def recursion_depth(child_depth: int, depth_max: int) -> int | Unknown:
    """递归深度门（超深 = Unknown(CAPABILITY_LIMIT) 停止——不影响已发布帧）。"""
    if child_depth > depth_max:
        return Unknown(
            reason=UnknownReason.CAPABILITY_LIMIT,
            evidence_refs=(f"depth:{child_depth}",),
            detail=f"recursion depth {child_depth} > depth_max {depth_max}（Q-L07-04①）",
            detected_by="workspace.recurse", virtual_time=child_depth,
        )
    return child_depth


def assert_frame_current(frame: WorkspaceFrame, cycle: int) -> None:
    """过期帧引用拒绝（TTL 语义——过期帧不得被当作当前内容）。"""
    if frame.expired_at(cycle):
        raise StaleFrameReference(
            f"frame {frame.frame_id} expired at cycle {frame.cycle_id + frame.ttl_cycles}"
            f"（当前 {cycle}——TTL {frame.ttl_cycles}，Q-L07-04②）"
        )


def recursion_gate(parent_depth: int, depth_max: int) -> "int | Unknown":
    """广播后再竞争的深度门（别名——递归路径全入 causal_parent_ids 由 pipeline 承载）。"""
    return recursion_depth(parent_depth + 1, depth_max)
