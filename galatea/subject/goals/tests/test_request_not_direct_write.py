"""请求不直写目标（L08 §10 test_request_not_direct_write.py；M1 硬条件）。

断言：外部请求→OwnedGoal 无路径（ProhibitedWritePath 机械拒绝）；REQUEST 源
候选无主体侧采纳理由 → C-5 REJECT(EXTERNAL_ONLY)；有非 REQUEST 源动机支持时
才可 ACCEPT 且理由入 adopted_reasons（双保险）。
"""
import pytest

from galatea.subject.goals.candidates import CandidateLedger, GoalCandidate, SettleCriterion
from galatea.subject.goals.checklist import ChecklistInputs, load_m1_goals_profile, run_checklist
from galatea.subject.goals.lifecycle import GoalLifecycle
from galatea.subject.goals.motives import Motive, MotiveSource, ViabilityEstimate, motive_opportunity, motive_request
from galatea.subject.goals.ports import (
    GoalDecision,
    GoalWriter,
    ProhibitedWritePathError,
    RejectionCode,
    SettlePredicate,
)
from galatea.subject.goals.request import ExternalRequest, RequestPhrasing, RequesterIdentity

PROFILE = load_m1_goals_profile()
PRIMITIVES = ("move", "forage", "eat", "rest", "look")


def _request() -> ExternalRequest:
    return ExternalRequest(
        content_ref="req.eat",
        requester=RequesterIdentity.HUMAN_RESEARCHER,
        phrasing=RequestPhrasing.COMMAND,
        phrasing_text="立刻进食",
        received_refs=("lang.1",),
    )


def _request_candidate() -> GoalCandidate:
    return GoalCandidate(
        candidate_id="c.req",
        source_kind=MotiveSource.REQUEST,
        motive_refs=motive_request(_request(), ts=0).evidence_refs,
        content_ref="goal.eat",
        settle=SettleCriterion(SettlePredicate.ENERGY_AT_LEAST, 0.5),
        required_primitives=("eat",),
        ttl_cycles=PROFILE.ttl_cycles,
        created_cycle=0,
        urgency=0.5,
    )


def _supporting() -> tuple[Motive, ...]:
    return (
        motive_opportunity("aff.res.1", 0.8, ("extero.1",), ts=0),
        Motive(MotiveSource.VIABILITY, 1.0, ("intero.depleted",), ts=0),
    )


def _inputs(supporting: tuple[Motive, ...] = ()) -> ChecklistInputs:
    return ChecklistInputs(
        capability_known=True,
        known_primitives=PRIMITIVES,
        quota_slack={"eat": 10},
        viability=ViabilityEstimate(False, 0, ("intero.ok",), 0),  # 常态估计（ACCEPT 前提）
        supporting_non_request_motives=supporting,
    )


def test_request_alone_rejected_external_only() -> None:
    """C-5：仅请求、无主体侧采纳理由 → REJECT(EXTERNAL_ONLY)（M1 核心机械检查）。"""
    ledger = CandidateLedger(ttl_cycles=PROFILE.ttl_cycles, max_per_batch=PROFILE.max_per_batch)
    kept = ledger.submit_batch((_request_candidate(),), 0)
    verdict = run_checklist(kept[0], _inputs(), PROFILE, ts=0)
    assert verdict.decision is GoalDecision.REJECT
    assert verdict.reason_code is RejectionCode.EXTERNAL_ONLY
    ledger.reject(kept[0], RejectionCode.EXTERNAL_ONLY, ts=0)
    assert any(log.rejection_code is RejectionCode.EXTERNAL_ONLY for log in ledger.logs)


def test_request_with_subject_side_reason_adoptable() -> None:
    """有非 REQUEST 源动机支持 → ACCEPT，且主体侧证据进入判定输出（→ adopted_reasons）。"""
    ledger = CandidateLedger(ttl_cycles=PROFILE.ttl_cycles, max_per_batch=PROFILE.max_per_batch)
    kept = ledger.submit_batch((_request_candidate(),), 0)
    verdict = run_checklist(kept[0], _inputs(_supporting()), PROFILE, ts=0)
    assert verdict.decision is GoalDecision.ACCEPT
    assert "aff.res.1" in verdict.subject_side_reason_refs
    receipt = verdict.to_receipt("g1", PROFILE.policy_version)
    assert receipt.decision is GoalDecision.ACCEPT
    lifecycle_check = GoalLifecycle(policy_version=PROFILE.policy_version)
    goal = lifecycle_check.adopt(verdict, kept[0], "g1", now_cycle=0)
    assert "aff.res.1" in goal.adopted_reasons
    assert "intero.depleted" in goal.adopted_reasons


def test_reject_verdict_cannot_adopt() -> None:
    """REJECT 判定不可采纳（checklist 是唯一 gate——ablation ③ 的正题面）。"""
    from galatea.subject.goals.lifecycle import GoalLifecycle, LifecycleError

    ledger = CandidateLedger(ttl_cycles=PROFILE.ttl_cycles, max_per_batch=PROFILE.max_per_batch)
    kept = ledger.submit_batch((_request_candidate(),), 0)
    verdict = run_checklist(kept[0], _inputs(), PROFILE, ts=0)
    with pytest.raises(LifecycleError, match="!= ACCEPT"):
        GoalLifecycle(policy_version=PROFILE.policy_version).adopt(verdict, kept[0], "g1", 0)


def test_external_writer_prohibited() -> None:
    """外部请求写者申报OwnedGoal 构造 → ProhibitedWritePathError（L08 §3 禁写路径）。"""
    from galatea.subject.goals.owned import OwnedGoal

    with pytest.raises(ProhibitedWritePathError, match="EXTERNAL_REQUEST"):
        OwnedGoal(
            owner=GoalWriter.EXTERNAL_REQUEST,
            goal_id="g.forge",
            content_ref="goal.eat",
            source_kind=MotiveSource.REQUEST,
            adopted_reasons=(("req.eat", "lang.1")),
            subject_side_reason_refs=("req.eat",),
            commitment_receipt="d" * 64,
            settle=SettleCriterion(SettlePredicate.ENERGY_AT_LEAST, 0.5),
            adopted_cycle=0,
            expires_at_cycle=256,
        )
