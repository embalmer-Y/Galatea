"""无自我 promotion（L13 §10 test_no_self_promotion.py——F0 schema 层：决策类型与签发边界）。"""
import dataclasses

import pytest

from galatea.evidence.gate.promotion import PromotionDecision, PromotionOutcome


def test_accepted_requires_sealed_and_protection_evidence() -> None:
    """ACCEPTED 缺 sealed held-out / 保护集引用在 schema 级即拒（L13 §4.4 流程②③，REV-0003 R3）。"""
    with pytest.raises(ValueError):
        PromotionDecision(
            candidate_ref="cand-1", parent_digest="d" * 64, outcome=PromotionOutcome.ACCEPTED,
            held_out_result_ref=None, protection_result_ref=None, sealed_split_id=None,
        )
    ok = PromotionDecision(
        candidate_ref="cand-1", parent_digest="d" * 64, outcome=PromotionOutcome.ACCEPTED,
        held_out_result_ref="ev-sealed-1", protection_result_ref="prot-1", sealed_split_id="split-f0",
    )
    assert ok.outcome is PromotionOutcome.ACCEPTED


def test_deferred_and_rejected_need_no_sealed_evidence() -> None:
    for outcome in (PromotionOutcome.REJECTED, PromotionOutcome.DEFERRED):
        decision = PromotionDecision(
            candidate_ref="cand-1", parent_digest="d" * 64, outcome=outcome,
            held_out_result_ref=None, protection_result_ref=None, sealed_split_id=None, reason="fixture",
        )
        assert decision.outcome is outcome


def test_decision_is_frozen() -> None:
    decision = PromotionDecision(
        candidate_ref="cand-1", parent_digest="d" * 64, outcome=PromotionOutcome.DEFERRED,
        held_out_result_ref=None, protection_result_ref=None, sealed_split_id=None,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.outcome = PromotionOutcome.ACCEPTED  # type: ignore[misc]
