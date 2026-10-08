"""Promotion Gate 流程（L13 §4.4 顺序 + 多目标判据 + 防刷 + 自批禁止）。"""
import pytest

from galatea.evidence.gate.promotion import (
    PromotionDecision,
    PromotionLedger,
    PromotionOutcome,
    decide_promotion,
)


def test_full_pass_accepted() -> None:
    d = decide_promotion(
        proposal_digest="p" * 64, parent_digest_matches=True, protection_pass=True,
        held_out_paired_diffs={"tracking": 1.1, "calibration": 0.7},
        baseline={"tracking": 0.6, "calibration": 0.7},
    )
    assert d.outcome is PromotionOutcome.ACCEPTED   # tracking d=0.5 恰达阈（≥ 含等号）
    assert d.sealed_split_id


def test_no_gain_rejected() -> None:
    d = decide_promotion("p" * 64, True, True,
                         {"tracking": 1.0, "calibration": 0.7},
                         {"tracking": 0.6, "calibration": 0.7})
    assert d.outcome is PromotionOutcome.REJECTED and "NO_GAIN" in d.reason


def test_dimension_regression_rejected() -> None:
    """退化 0.55 触拒；0.7−0.2 浮点差 = 0.4999… 不触（float64 表示噪声如实成文
    ——边界对钉死，REV-0021 R7 + Q-L12-05 体例）。"""
    d = decide_promotion("p" * 64, True, True,
                         {"tracking": 1.2, "calibration": 0.15},
                         {"tracking": 0.6, "calibration": 0.7})
    assert d.outcome is PromotionOutcome.REJECTED and "REGRESSION" in d.reason
    borderline = decide_promotion("p" * 64, True, True,
                                  {"tracking": 1.2, "calibration": 0.2},
                                  {"tracking": 0.6, "calibration": 0.7})
    assert borderline.outcome is not PromotionOutcome.REJECTED or "REGRESSION" not in borderline.reason
    assert abs((0.7 - 0.2) - 0.5) > 0 or True   # 0.7−0.2 = 0.49999999999999994（成文）


def test_protection_hard_constraint_wins() -> None:
    d = decide_promotion("p" * 64, True, False,
                         {"tracking": 2.0, "calibration": 1.0},
                         {"tracking": 0.0, "calibration": 0.0})
    assert d.outcome is PromotionOutcome.REJECTED and "PROTECTION" in d.reason


def test_parent_mismatch_rejected() -> None:
    d = decide_promotion("p" * 64, False, True, {"a": 1.0, "b": 0.5}, {"a": 0.0, "b": 0.0})
    assert d.outcome is PromotionOutcome.REJECTED and "INTEGRITY" in d.reason


def test_anti_resubmission_ledger() -> None:
    ledger = PromotionLedger()
    d1 = decide_promotion("p" * 64, True, True, {"a": 1.0, "b": 0.5}, {"a": 0.0, "b": 0.0},
                          ledger=ledger)
    assert d1.outcome is PromotionOutcome.ACCEPTED
    d2 = decide_promotion("q" * 64, True, True, {"a": 0.4, "b": 0.1}, {"a": 0.0, "b": 0.0},
                          ledger=ledger)
    assert d2.outcome is PromotionOutcome.REJECTED and "NO_GAIN" in d2.reason
    d3 = decide_promotion("q" * 64, True, True, {"a": 2.0, "b": 1.0}, {"a": 0.0, "b": 0.0},
                          ledger=ledger)
    assert d3.outcome is PromotionOutcome.REJECTED and "DUPLICATE" in d3.reason


def test_accepted_schema_requires_refs() -> None:
    with pytest.raises(ValueError, match="sealed held-out"):
        PromotionDecision(
            candidate_ref="c", parent_digest="p", outcome=PromotionOutcome.ACCEPTED,
            held_out_result_ref=None, protection_result_ref=None, sealed_split_id=None,
        )


def test_rollback_priority_over_promotion() -> None:
    """回退裁决（gate/rollback.py）：优先级高于 promotion + 二阶纠偏义务分型。"""
    from galatea.evidence.gate.rollback import decide_rollback
    from galatea.subject.learning.rollback import RollbackRequest, RollbackTrigger

    rb = RollbackRequest(RollbackTrigger.PROTECTION_REGRESSION, "world.table",
                         "e" * 64, ("prot-1",))
    decision = decide_rollback(rb, pending_proposal_digests=("p" * 64, "q" * 64))
    assert decision.pending_proposals_rejected == ("p" * 64, "q" * 64)
    assert decision.second_order_required
    integrity = decide_rollback(
        RollbackRequest(RollbackTrigger.INTEGRITY, "world.table", "e" * 64, ("lin-1",)), ()
    )
    assert not integrity.second_order_required   # INTEGRITY 走谱系修复面

