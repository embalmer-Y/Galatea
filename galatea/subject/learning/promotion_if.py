"""学习面 → 治理面只读接口（L11 §10 promotion_if.py：自批禁止——Decision 只读）。

P04 纪律（主体平面禁读证据/治理平面）：本模块**不 import** gate 侧类型——
决策视图为自包含 dataclass，由装配层（evidence 侧）从 PromotionDecision 构造注入；
学习面只消费快照，禁回写/禁重签。
"""
from dataclasses import dataclass

__all__ = ["ReadOnlyDecisionView"]


@dataclass(frozen=True, slots=True)
class ReadOnlyDecisionView:
    """学习者可见的决策快照（outcome/reason/candidate_ref 三字段——结构面无签发能力）。"""

    outcome: str
    reason: str
    candidate_ref: str

    def __post_init__(self) -> None:
        if not self.candidate_ref:
            raise ValueError("ReadOnlyDecisionView requires an issued decision（自批禁止）")
        if self.outcome not in ("ACCEPTED", "REJECTED", "DEFERRED"):
            raise ValueError(f"unknown outcome: {self.outcome!r}（L13 §4.4 ⑤ 三态）")
