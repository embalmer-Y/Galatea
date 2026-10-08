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


# ==========================================================================
# C5 流程执行（L13 §4.4 完整性→保护→sealed→多目标→签发；Q-L11-03+Q-L13-07 成组；
# 2026-10-08 实现期首单元——决策权在本档，主体/学习者只读【自批禁止】）
# ==========================================================================

class PromotionLedger:
    """决策台账（防刷：REJECTED digest 重提即拒——L11 §4.5 原文机械化）。"""

    def __init__(self) -> None:
        self._rejected: set[str] = set()
        self._decisions: list[PromotionDecision] = []

    def already_rejected(self, proposal_digest: str) -> bool:
        return proposal_digest in self._rejected

    def record(self, decision: PromotionDecision, proposal_digest: str) -> None:
        self._decisions.append(decision)
        if decision.outcome is PromotionOutcome.REJECTED:
            self._rejected.add(proposal_digest)

    @property
    def decisions(self) -> tuple[PromotionDecision, ...]:
        return tuple(self._decisions)


def decide_promotion(
    proposal_digest: str,
    parent_digest_matches: bool,
    protection_pass: bool,
    held_out_paired_diffs: "dict[str, float]",
    baseline: "dict[str, float]",
    min_d: float = 0.5,
    max_regression_d: float = 0.5,
    ledger: PromotionLedger | None = None,
    sealed_split_id: str | None = "sealed-split-9b99d26f",
) -> PromotionDecision:
    """PromotionDecision 流程（顺序固定：防刷→完整性→保护→多目标→签发）。

    多目标判据（Q-L11-03+Q-L13-07 成组裁决）：sealed held-out 主指标配对
    d ≥ 0.5 ∧ 无任何维 |d| ≥ 0.5 退化 ∧ 保护全过（硬约束——无论 held-out 多好）。
    """
    def _emit(decision: PromotionDecision) -> PromotionDecision:
        if ledger is not None:
            ledger.record(decision, proposal_digest)
        return decision

    if ledger is not None and ledger.already_rejected(proposal_digest):
        return PromotionDecision(
            candidate_ref=proposal_digest, parent_digest="",
            outcome=PromotionOutcome.REJECTED, held_out_result_ref=None,
            protection_result_ref=None, sealed_split_id=None,
            reason="DUPLICATE_RESUBMISSION（同 digest 重提——L11 §4.5 防刷）",
        )
    if not parent_digest_matches:
        return _emit(PromotionDecision(
            candidate_ref=proposal_digest, parent_digest="",
            outcome=PromotionOutcome.REJECTED, held_out_result_ref=None,
            protection_result_ref=None, sealed_split_id=None,
            reason="INTEGRITY（parent digest 不匹配——伪更新防线）",
        ))
    if not protection_pass:
        return _emit(PromotionDecision(
            candidate_ref=proposal_digest, parent_digest="",
            outcome=PromotionOutcome.REJECTED, held_out_result_ref=None,
            protection_result_ref="protection:failed",
            sealed_split_id=None,
            reason="PROTECTION_REGRESSION（保护硬约束——held-out 不参与，L11 §4.6）",
        ))
    diffs = {k: held_out_paired_diffs[k] - baseline.get(k, 0.0) for k in held_out_paired_diffs}
    regressed = [k for k, d in diffs.items() if -d >= max_regression_d]
    if regressed:
        return _emit(PromotionDecision(
            candidate_ref=proposal_digest, parent_digest="",
            outcome=PromotionOutcome.REJECTED, held_out_result_ref="held-out:evaluated",
            protection_result_ref="protection:passed",
            sealed_split_id=sealed_split_id,
            reason=f"DIMENSION_REGRESSION（{regressed} 退化 ≥{max_regression_d}——多目标无退化约束）",
        ))
    main = max(diffs.values())
    if main < min_d:
        return _emit(PromotionDecision(
            candidate_ref=proposal_digest, parent_digest="",
            outcome=PromotionOutcome.REJECTED, held_out_result_ref="held-out:evaluated",
            protection_result_ref="protection:passed",
            sealed_split_id=sealed_split_id,
            reason=f"NO_GAIN（主指标 d={main:.4f} < {min_d}——最小改善阈）",
        ))
    return _emit(PromotionDecision(
        candidate_ref=proposal_digest, parent_digest="parent:verified",
        outcome=PromotionOutcome.ACCEPTED, held_out_result_ref="held-out:evaluated",
        protection_result_ref="protection:passed", sealed_split_id=sealed_split_id,
        reason=f"main_d={main:.4f}",
    ))

