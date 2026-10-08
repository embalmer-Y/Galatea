"""ConsolidationLearnReceipt（L11 §4.5 / §10 receipt.py）。

promotion ACCEPTED 后的巩固学习回执（registry 引用切换留证——候选不覆盖，
原工件与谱系完整保留）；digest 双绑定（提案 ↔ 回执）。
"""
import hashlib
import json
from dataclasses import dataclass

__all__ = ["ConsolidationLearnReceipt"]


@dataclass(frozen=True, slots=True)
class ConsolidationLearnReceipt:
    """巩固回执（提案 digest + 生效工件 digest + 父版本 digest 谱系三元组）。"""

    proposal_digest: str
    activated_digest: str
    parent_digest: str
    decision_ref: str           # PromotionDecision digest（gate 侧签发）
    accepted_at_cycle: int

    def __post_init__(self) -> None:
        for name in ("proposal_digest", "activated_digest", "parent_digest", "decision_ref"):
            if len(getattr(self, name)) < 16:
                raise ValueError(f"ConsolidationLearnReceipt.{name} requires digest")

    @property
    def receipt_digest(self) -> str:
        return hashlib.sha256(json.dumps({
            "proposal": self.proposal_digest, "activated": self.activated_digest,
            "parent": self.parent_digest, "decision": self.decision_ref,
            "cycle": self.accepted_at_cycle,
        }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
