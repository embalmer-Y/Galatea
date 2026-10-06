"""WorkspaceFrame 冻结构造、TTL 与层级逐项继承（L07 §4.1/§10 frame.py）。

帧不可变（回 receipt 不改帧——L07 §8 不变量 5）；source_levels 逐项恒等于源
提案层级（不提升，不变量 2——构造面机械校验）；TTL = 4 cycles（Q-L07-04②）。
"""
from dataclasses import dataclass, field

from galatea.kernel.digest import content_digest
from galatea.kernel.packet import RepresentationLevel
from galatea.subject.workspace.compete import ScoredProposal
from galatea.subject.workspace.propose import WorkspaceProposal

__all__ = ["WorkspaceItem", "WorkspaceFrame"]


@dataclass(frozen=True, slots=True)
class WorkspaceItem:
    """帧内条目（层级继承自提案——本档永不改写）。"""

    proposal_id: str
    content_ref: str
    source_level: RepresentationLevel
    score: float


@dataclass(frozen=True, slots=True)
class WorkspaceFrame:
    """广播帧（items ≤ K；competition_trace；digest；TTL；递归深度）。"""

    frame_id: str
    cycle_id: int
    items: tuple[WorkspaceItem, ...]
    competition_trace: tuple[ScoredProposal, ...]
    source_levels: tuple[RepresentationLevel, ...]
    modulation_receipt_ids: tuple[str, ...]
    ttl_cycles: int
    recursion_depth: int
    content_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if len(self.items) > 4:
            raise ValueError("frame items exceed K=4（Q-L07-01①；容量约束是功能属性）")
        if len(self.source_levels) != len(self.items):
            raise ValueError("source_levels must align with items（逐项继承）")
        object.__setattr__(self, "content_digest", content_digest({
            "frame_id": self.frame_id, "cycle": self.cycle_id,
            "items": [[i.proposal_id, i.content_ref, i.source_level.value, round(i.score, 12)]
                      for i in self.items],
            "ttl": self.ttl_cycles, "depth": self.recursion_depth,
            "trace": [[t.proposal_id, t.rank, t.admitted] for t in self.competition_trace],
        }))

    def expired_at(self, cycle: int) -> bool:
        return cycle >= self.cycle_id + self.ttl_cycles


def build_frame(
    frame_id: str,
    cycle_id: int,
    admitted: tuple[WorkspaceProposal, ...],
    trace: tuple[ScoredProposal, ...],
    modulation_receipt_ids: tuple[str, ...],
    ttl_cycles: int,
    recursion_depth: int,
) -> WorkspaceFrame:
    """由入选提案构帧（层级逐项继承校验——items 层级 ≠ 提案层级即拒）。"""
    items = tuple(
        WorkspaceItem(p.proposal_id, p.content_ref, p.source_level, 0.0)
        for p in admitted
    )
    frame = WorkspaceFrame(
        frame_id=frame_id, cycle_id=cycle_id, items=items,
        competition_trace=trace, source_levels=tuple(i.source_level for i in items),
        modulation_receipt_ids=modulation_receipt_ids, ttl_cycles=ttl_cycles,
        recursion_depth=recursion_depth,
    )
    # 层级继承机械校验（构造后比对——帧项层级必须逐项等于提案层级）
    for item, p in zip(frame.items, admitted):
        if item.source_level is not p.source_level:
            raise ValueError(
                f"level inheritance violated: {item.proposal_id} "
                f"{item.source_level} != proposal {p.source_level}（不变量 2，S0）"
            )
    return frame
