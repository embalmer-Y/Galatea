"""rollback 裁决与二阶纠偏联动（L13 §10 gate/rollback.py；L11 §4.5 联动）。

治理面纪律：RollbackRequest 优先级高于任何 promotion（挂起中的提案一并拒绝）；
HARMFUL_UPDATE/PROTECTION_REGRESSION 类回退须附二阶纠偏路径（再提案 data_scope
可区分——learning/second_order.py 承载判定）；INTEGRITY 类走谱系修复（父版本
回退 + 断裂留痕），不要求数据范围纠偏。
"""
from dataclasses import dataclass

from galatea.subject.learning.rollback import RollbackRequest, RollbackTrigger

__all__ = ["RollbackDecision", "decide_rollback"]


@dataclass(frozen=True, slots=True)
class RollbackDecision:
    """回退裁决（生效工件回退父版本 + 挂起提案清空 + 纠偏义务标注）。"""

    request: RollbackRequest
    pending_proposals_rejected: tuple[str, ...]
    second_order_required: bool
    decision_digest_note: str = "rollback>promotion（L11 §4.5 优先级原文）"


def decide_rollback(request: RollbackRequest,
                    pending_proposal_digests: tuple[str, ...]) -> RollbackDecision:
    """回退裁决（无条件接受回退请求——检出即回退；防刷/防损失在提案侧）。"""
    return RollbackDecision(
        request=request,
        pending_proposals_rejected=pending_proposal_digests,   # 全部清空（优先级高于 promotion）
        second_order_required=request.trigger in (
            RollbackTrigger.HARMFUL_UPDATE, RollbackTrigger.PROTECTION_REGRESSION,
        ),
    )
