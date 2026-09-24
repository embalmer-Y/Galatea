"""ExecutionFact 对主体不可见（L10 §10 test_execution_fact_invisible.py——F0 schema 层）。"""
import dataclasses

import pytest

from galatea.kernel.packet import AccessScope, ArtifactRef
from galatea.kernel.unknown import Unknown, UnknownReason
from galatea.subject.action.ports import (
    AgencyAttribution,
    AttributionKind,
    AuthorizationDecision,
    EfferenceCopy,
    ExecutionDomain,
    ExecutionFact,
    GatewayDecision,
    GatewayReasonCode,
    GoalSettlement,
    ReceivedExecutionReceipt,
    ReceivedOutcome,
    SettlementKind,
    SubmittedCommand,
)
from galatea.subject.control.intention import ActionIntention


def _command() -> SubmittedCommand:
    return SubmittedCommand(
        command_id="c1", gateway_signature="sig", requested_action="move",
        budget=2, deadline=8, idempotency_key="k1",
    )


def test_chain_nine_types_are_distinct_schemas() -> None:
    """九型互不为同一类型（intention/authz/command/fact/receipt/outcome/efference/attribution/settlement）。"""
    types = (
        ActionIntention, AuthorizationDecision, SubmittedCommand, ExecutionFact,
        ReceivedExecutionReceipt, ReceivedOutcome, EfferenceCopy, AgencyAttribution, GoalSettlement,
    )
    assert len({t.__name__ for t in types}) == 9


def test_execution_fact_frozen_and_evidence_only() -> None:
    fact = ExecutionFact(
        command_id="c1", requested_effect="forage", effective_effect="none",
        domain=ExecutionDomain.SIMULATED, effects=(), independent_source="env",
    )
    assert fact.access_scope is AccessScope.EVIDENCE_ONLY
    with pytest.raises(dataclasses.FrozenInstanceError):
        fact.effective_effect = "forage"  # type: ignore[misc]


def test_authorization_decision_carries_reason_codes() -> None:
    decision = AuthorizationDecision(
        intention_id="i1", decision=GatewayDecision.REJECTED,
        failed_checks=("budget",), reason_code=GatewayReasonCode.BUDGET_EXCEEDED,
        policy_version="v1", freshness_ref=None,
    )
    assert decision.reason_code is GatewayReasonCode.BUDGET_EXCEEDED
    assert len(GatewayReasonCode) == 9  # 冻结 profile 八项校验的九个失败码


def test_attribution_visible_only_enforced() -> None:
    unknown = Unknown(reason=UnknownReason.ATTRIBUTION_UNRESOLVED, evidence_refs=(), detail=None, detected_by="m", virtual_time=1)
    with pytest.raises(ValueError):
        AgencyAttribution(
            action_window=(1, 2), attribution_kind=AttributionKind.SELF_PRODUCED,
            probability=0.9, evidence_refs=("r",), visible_only=False,
        )
    ok = AgencyAttribution(
        action_window=(1, 2), attribution_kind=AttributionKind.UNKNOWN,
        probability=unknown, evidence_refs=(), visible_only=True,
    )
    assert ok.attribution_kind is AttributionKind.UNKNOWN  # UNKNOWN 是合法归属


def test_settlement_unknown_is_legal() -> None:
    settlement = GoalSettlement(goal_ref="g1", outcome_kind=SettlementKind.UNKNOWN, attribution_ref=None, evidence_refs=())
    assert settlement.outcome_kind is SettlementKind.UNKNOWN


def test_receipt_and_outcome_are_received_side() -> None:
    receipt = ReceivedExecutionReceipt(command_ref="c1", receipt_kind="ack", status="ok", ts=4)
    outcome = ReceivedOutcome(outcome_ref=ArtifactRef(digest="2" * 64, kind="outcome"), received_at=5)
    assert receipt.ts == 4 and outcome.received_at == 5
    with pytest.raises(ValueError):
        ReceivedExecutionReceipt(command_ref="", receipt_kind="ack", status="ok", ts=4)
    _ = _command()
    efference = EfferenceCopy(intention_id="i1", motor_command_copy="m1", predicted_consequence_ref=None)
    assert efference.intention_id == "i1"
