"""WorkspaceProposal 构造（L03 §2.2 perc→L07 候选/§5 T3/§10 workspace_prop.py）。

L07 workspace 归 C2——C1 只构建提案 schema 与显著性分量（存证，不投递）：
显著性 C1 = 信念置信（无价值估计器；价值面归 L05 C2）。
禁写 WorkspaceFrame（L03 §8：只能提交候选）。
"""
from dataclasses import dataclass

from galatea.kernel.digest import content_digest
from galatea.subject.perception.believe import PerceptualBelief


@dataclass(frozen=True, slots=True)
class WorkspaceProposal:
    """workspace 候选（含显著性分量；L07 消费面，C2 投递）。"""

    proposal_id: str
    belief_ref: str
    significance: float
    cycle_id: int

    def __post_init__(self) -> None:
        if not 0.0 <= self.significance <= 1.0:
            raise ValueError(f"significance out of [0,1]: {self.significance}")

    def digest(self) -> str:
        return content_digest({
            "proposal_id": self.proposal_id,
            "belief_ref": self.belief_ref,
            "significance": self.significance,
            "cycle_id": self.cycle_id,
        })


def build_proposals(
    beliefs: tuple[PerceptualBelief, ...], effective_time: int
) -> tuple[WorkspaceProposal, ...]:
    """为有置信信念构建候选（确定性：belief_id 升序；置信 Unknown 的信念跳过）。"""
    out: list[WorkspaceProposal] = []
    for belief in sorted(beliefs, key=lambda b: b.belief_id):
        if not isinstance(belief.confidence, float):
            continue
        out.append(WorkspaceProposal(
            proposal_id=f"wp.{belief.belief_id}",
            belief_ref=belief.belief_id,
            significance=belief.confidence,
            cycle_id=effective_time,
        ))
    return tuple(out)
