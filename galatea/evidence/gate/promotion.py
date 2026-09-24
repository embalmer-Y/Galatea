"""PromotionDecision schema（L13 §2.2 evd.promotion_decision / §10 gate/promotion.py）。

纪律：决策权在本档/外部治理（Promotion Gate），主体不可自批（L11/L13 双向断言）；
ACCEPTED 必须携带 sealed held-out 评价与保护集结果引用（L13 §4.4 流程③②——
缺 sealed 证据的接受在 schema 级即拒）。F0 范围 = schema 合同（REV-0003 R3 补交付）；
流程执行逻辑归 C5。
"""
from dataclasses import dataclass
from enum import StrEnum


class PromotionOutcome(StrEnum):
    """晋升判定三态（L13 §4.4 ⑤）。"""

    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    """晋升决策（签发者 = Promotion Gate；主体/学习者只读）。"""

    candidate_ref: str
    parent_digest: str
    outcome: PromotionOutcome
    held_out_result_ref: str | None
    protection_result_ref: str | None
    sealed_split_id: str | None
    reason: str = ""

    def __post_init__(self) -> None:
        if self.outcome is PromotionOutcome.ACCEPTED:
            if not self.held_out_result_ref or not self.protection_result_ref:
                raise ValueError(
                    "ACCEPTED requires sealed held-out result and protection result refs（L13 §4.4 流程②③）"
                )
            if not self.sealed_split_id:
                raise ValueError("ACCEPTED requires sealed_split_id（Q-L13-02：不回流判据绑定分割身份）")
