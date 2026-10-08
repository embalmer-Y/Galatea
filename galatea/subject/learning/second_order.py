"""二阶纠偏：回退 + data_scope 修正 + 再提案可区分性（L11 §4.5 / §10 second_order.py）。

M2 退出"有害更新可再次纠正"义务的机制承载：不仅回退，还要求纠错闭环——
再提案必须与首次提案在 data_scope 上可区分（排除致害数据/修正规则），
并最终证明"纠正后的更新可再次通过"（再通过性由 gate 侧 Decision 承载）。
"""
from dataclasses import dataclass

from galatea.subject.learning.proposal import DataScope, LearningProposal
from galatea.subject.learning.rollback import RollbackRequest

__all__ = ["SecondOrderCorrection", "scopes_distinguishable", "build_correction"]


def scopes_distinguishable(first: DataScope, corrected: DataScope) -> bool:
    """可区分性 = run 集/窗/排除集任一实质不同（item_count 变化不足以区分——
    同数据更多条不是纠正；禁"原样重提"。L11 §4.5 原文"data_scope 上可区分"）。"""
    return (
        first.run_ids != corrected.run_ids
        or first.window != corrected.window
        or first.exclusions != corrected.exclusions
    )


@dataclass(frozen=True, slots=True)
class SecondOrderCorrection:
    """纠偏记录（回退请求 + 纠正提案 + 可区分性判定结果）。"""

    rollback: RollbackRequest
    corrected_proposal: LearningProposal
    distinguished: bool

    def __post_init__(self) -> None:
        if self.rollback.trigger.value != "HARMFUL_UPDATE" and self.rollback.trigger.value != "PROTECTION_REGRESSION":
            raise ValueError(
                "second-order correction rides HARMFUL_UPDATE/PROTECTION_REGRESSION"
                "（INTEGRITY 走谱系修复面，非数据范围纠偏）"
            )


def build_correction(rollback: RollbackRequest, first_scope: DataScope,
                     corrected_proposal: LearningProposal) -> SecondOrderCorrection:
    """纠偏构造（可区分性判定内联——不可区分即拒，禁原样重提）。"""
    ok = scopes_distinguishable(first_scope, corrected_proposal.data_scope)
    correction = SecondOrderCorrection(rollback=rollback,
                                       corrected_proposal=corrected_proposal,
                                       distinguished=ok)
    if not ok:
        raise ValueError(
            "corrected proposal data_scope indistinguishable from first"
            "（原样重提 = 纠偏失败，L11 §4.5 二阶纠偏原文）"
        )
    return correction
