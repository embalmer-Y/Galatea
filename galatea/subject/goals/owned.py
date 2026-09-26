"""OwnedGoal 冻结构造、rev 谱系、adopted_reasons 强制（L08 §2.2/§4.1/§10 owned.py）。

纪律：OwnedGoal 唯一写者 = Goal Ownership（L08 §3）——构造必须显式申报写者身份，
非 GOAL_OWNERSHIP 一律 ProhibitedWritePathError（机械拒绝，强度与 kernel/state.py
`_OWNERSHIP` 表同级：写者身份显式申报 + 拒绝非法者；伪造申报属 greppable 违例）；
必须携带可溯 adopted_reasons[] 与非空 subject_side_reason_refs（C-5 载体：非
REQUEST 源证据，由 checklist 判定供给，L08 §8 不变量 3）与 commitment_receipt
（GoalReceipt digest）；修订以 rev+1 表达、禁原地改写历史（L08 §4.1）；已解除
goal_id 禁复活（lifecycle 侧强制，GoalRevivalError）。
"""
from dataclasses import dataclass, replace
from typing import Any

from galatea.subject.goals.candidates import SettleCriterion
from galatea.subject.goals.motives import MotiveSource
from galatea.subject.goals.ports import GoalWriter, ProhibitedWritePathError

__all__ = ["OwnedGoal", "GoalRevivalError"]


@dataclass(frozen=True, slots=True)
class OwnedGoal:
    """被拥有的目标（L08 §2.2 goal.owned 全字段）。"""

    owner: GoalWriter                       # 写者身份申报（唯一合法值 = GOAL_OWNERSHIP）
    goal_id: str
    content_ref: str
    source_kind: MotiveSource
    adopted_reasons: tuple[str, ...]        # 可溯采纳理由（L08 §8 不变量 3）
    subject_side_reason_refs: tuple[str, ...]  # C-5 载体：非 REQUEST 源证据（checklist 供给）
    commitment_receipt: str                 # GoalReceipt digest（L08 §4.2）
    settle: SettleCriterion
    adopted_cycle: int
    expires_at_cycle: int                   # adopted_cycle + 候选 ttl（Q-L08-09⑧ TTL-only 判据）
    rejected_alternatives: tuple[str, ...] = ()
    normative_refs: tuple[str, ...] = ()
    valid_scope: str = "mw0"
    rev: int = 1
    prior_rev_ref: str | None = None        # 修订谱系："{goal_id}#rev{n}"

    def __post_init__(self) -> None:
        if self.owner is not GoalWriter.GOAL_OWNERSHIP:
            raise ProhibitedWritePathError(
                self.owner, "OwnedGoal construction requires the Goal Ownership writer（L08 §3）"
            )
        if not self.goal_id or not self.content_ref:
            raise ValueError("OwnedGoal requires goal_id and content_ref")
        if not self.adopted_reasons:
            raise ValueError("OwnedGoal requires adopted_reasons（L08 §8 不变量 3）")
        if not self.subject_side_reason_refs:
            raise ValueError(
                "OwnedGoal requires subject_side_reason_refs（≥1 非 REQUEST 源证据，L08 §4.2 C-5）"
            )
        if not set(self.subject_side_reason_refs) <= set(self.adopted_reasons):
            raise ValueError("subject_side_reason_refs must be a subset of adopted_reasons")
        if not self.commitment_receipt:
            raise ValueError("OwnedGoal requires commitment_receipt（GoalReceipt digest，L08 §4.2）")
        if self.rev < 1:
            raise ValueError("OwnedGoal.rev must be >= 1")
        if self.expires_at_cycle <= self.adopted_cycle:
            raise ValueError("OwnedGoal.expires_at_cycle must exceed adopted_cycle")

    def revise(self, **changes: Any) -> "OwnedGoal":
        """修订 = rev+1 新实例引用旧 rev（禁原地改写；goal_id/rev/谱系字段受管）。"""
        forbidden = {"rev", "prior_rev_ref", "goal_id", "owner"} & set(changes)
        if forbidden:
            raise ValueError(f"revise() cannot rewrite managed fields: {sorted(forbidden)}")
        prior = f"{self.goal_id}#rev{self.rev}"
        return replace(self, rev=self.rev + 1, prior_rev_ref=prior, **changes)


class GoalRevivalError(ValueError):
    """已解除/已废止 goal_id 复活企图（L08 §4.5：解除后不得复活旧 goal_id，防伪更新）。"""
