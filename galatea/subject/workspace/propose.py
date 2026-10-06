"""提案接收/校验（L07 §2.1/§10 propose.py）。

提案合同：sponsor_module 强制（禁匿名，承 L00）；source_level 必填且本档不改写；
salience 五分量 ∈ [0,1]（goal_relevance/affect/novelty/uncertainty/info_value）；
提案不携带写权限（类型面无写路径字段）。
"""
from dataclasses import dataclass

from galatea.kernel.packet import RepresentationLevel
from galatea.subject.workspace.ports import WorkspaceSchemaViolation

__all__ = ["SalienceComponents", "WorkspaceProposal", "validate_proposal"]


@dataclass(frozen=True, slots=True)
class SalienceComponents:
    """显著性五分量（L07 §2.1；全部 [0,1]）。"""

    goal_relevance: float
    affect: float
    novelty: float
    uncertainty: float
    info_value: float

    def __post_init__(self) -> None:
        for name in ("goal_relevance", "affect", "novelty", "uncertainty", "info_value"):
            v = getattr(self, name)
            if not 0.0 <= v <= 1.0:
                raise WorkspaceSchemaViolation(f"salience component {name} out of [0,1]: {v!r}")


@dataclass(frozen=True, slots=True)
class WorkspaceProposal:
    """工作空间提案（L07 §2.1：content_ref + 层级 + 分量 + sponsor + 预期 watch 点）。"""

    proposal_id: str
    content_ref: str
    source_level: RepresentationLevel
    salience: SalienceComponents
    sponsor_module: str
    expected_watch_points: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.proposal_id or not self.content_ref:
            raise WorkspaceSchemaViolation("proposal requires proposal_id and content_ref")
        if not self.sponsor_module:
            raise WorkspaceSchemaViolation("anonymous proposal rejected（禁匿名，承 L00；L07 §6 行 2）")


def validate_proposal(p: WorkspaceProposal) -> WorkspaceProposal:
    """校验（域/匿名/层级必填——冗余于构造面，管线入口二次防线）。"""
    return p
