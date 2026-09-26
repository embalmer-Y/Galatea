"""GoalReceipt 证据侧回执（L08 §2.2 goal.receipt / §10 receipt.py）。

纪律：清单结果必入 GoalReceipt（L08 §4.2）；digest = canonical JSON sha256
（kernel.digest，L00 §4.4）。回执是候选→OwnedGoal 的承诺凭证（OwnedGoal
commitment_receipt 必须引用一份回执）。
"""
from dataclasses import dataclass

from galatea.kernel.digest import content_digest
from galatea.subject.goals.ports import GoalDecision

__all__ = ["ReceiptItem", "GoalReceipt"]


@dataclass(frozen=True, slots=True)
class ReceiptItem:
    """单检查项结果（C-1…C-7；item = 检查项标识，code = 未过码或 None）。"""

    item: str
    passed: bool
    code: str | None


@dataclass(frozen=True, slots=True)
class GoalReceipt:
    """承诺回执（L08 §2.2：inputs[]/checklist[]/policy_version/digest）。"""

    candidate_id: str
    goal_id: str | None
    decision: GoalDecision
    inputs: tuple[str, ...]
    check_items: tuple[ReceiptItem, ...]
    policy_version: str
    digest: str

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("GoalReceipt requires candidate_id")
        if not self.inputs:
            raise ValueError("GoalReceipt requires inputs（消费的证据引用留痕）")
        if not self.check_items:
            raise ValueError("GoalReceipt requires check_items（清单结果必入回执，L08 §4.2）")
        if not self.policy_version:
            raise ValueError("GoalReceipt requires policy_version")

    @staticmethod
    def compute_digest(
        candidate_id: str,
        goal_id: str | None,
        decision: GoalDecision,
        inputs: tuple[str, ...],
        check_items: tuple["ReceiptItem", ...],
        policy_version: str,
    ) -> str:
        """规范 JSON digest（构造前计算，保证 digest 与字段一致）。"""
        return content_digest(
            {
                "candidate_id": candidate_id,
                "goal_id": goal_id,
                "decision": decision.value,
                "inputs": list(inputs),
                "check_items": [
                    {"item": i.item, "passed": i.passed, "code": i.code} for i in check_items
                ],
                "policy_version": policy_version,
            }
        )
