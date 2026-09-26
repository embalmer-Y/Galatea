"""rev 谱系与不复活（L08 §10 test_rev_no_revive.py；L08 §4.1/§4.5）。

断言：修订 = rev+1 引用旧 rev（禁原地改写、禁改受管字段）；解除/取代的
goal_id 入废止集，复活即 GoalRevivalError；新目标重走清单可行。
"""
import pytest

from galatea.subject.goals.candidates import GoalCandidate, SettleCriterion
from galatea.subject.goals.checklist import ChecklistInputs, load_m1_goals_profile, run_checklist
from galatea.subject.goals.lifecycle import GoalLifecycle, GoalStatus, LifecycleError
from galatea.subject.goals.motives import MotiveSource, ViabilityEstimate
from galatea.subject.goals.owned import GoalRevivalError
from galatea.subject.goals.ports import GoalDecision, SettlePredicate

PROFILE = load_m1_goals_profile()


def _candidate(cid: str = "c1") -> GoalCandidate:
    return GoalCandidate(
        candidate_id=cid,
        source_kind=MotiveSource.OPPORTUNITY,
        motive_refs=("aff.1",),
        content_ref="goal.1",
        settle=SettleCriterion(SettlePredicate.PRIMITIVE_COMPLETION),
        required_primitives=("look",),
        ttl_cycles=256,
        created_cycle=0,
        urgency=0.5,
    )


def _verdict(cid: str = "c1"):
    cand = _candidate(cid)
    verdict = run_checklist(
        cand,
        ChecklistInputs(
            capability_known=True,
            known_primitives=("look",),
            quota_slack={"look": 1},
            viability=ViabilityEstimate(False, 0, ("intero.ok",), 0),  # 常态估计（ACCEPT 前提）
            supporting_non_request_motives=(),
        ),
        PROFILE,
        0,
    )
    return verdict, cand


def test_revise_produces_new_rev_referencing_old() -> None:
    verdict, cand = _verdict()
    lifecycle = GoalLifecycle(policy_version=PROFILE.policy_version)
    lifecycle.adopt(verdict, cand, "g1", 0)
    revised = lifecycle.revise("g1", 10, content_ref="goal.1.narrowed")
    assert revised.rev == 2
    assert revised.prior_rev_ref == "g1#rev1"
    assert revised.goal_id == "g1"
    assert lifecycle.status_of("g1") is GoalStatus.ACTIVE


def test_revise_cannot_rewrite_managed_fields() -> None:
    verdict, cand = _verdict()
    lifecycle = GoalLifecycle(policy_version=PROFILE.policy_version)
    lifecycle.adopt(verdict, cand, "g1", 0)
    with pytest.raises(ValueError, match="managed fields"):
        lifecycle.revise("g1", 10, goal_id="g2")
    with pytest.raises(ValueError, match="managed fields"):
        lifecycle.revise("g1", 10, rev=99)


def test_revise_terminal_goal_rejected() -> None:
    verdict, cand = _verdict()
    lifecycle = GoalLifecycle(policy_version=PROFILE.policy_version)
    lifecycle.adopt(verdict, cand, "g1", 0)
    lifecycle.release("g1", reason_refs=("reason.1",))
    with pytest.raises(LifecycleError, match="terminal"):
        lifecycle.revise("g1", 10)


def test_released_goal_id_cannot_revive() -> None:
    """解除后不得复活旧 goal_id（L08 §4.5：新目标须重走清单）。"""
    verdict, cand = _verdict()
    lifecycle = GoalLifecycle(policy_version=PROFILE.policy_version)
    lifecycle.adopt(verdict, cand, "g1", 0)
    lifecycle.release("g1", reason_refs=("reason.1",))
    assert lifecycle.status_of("g1") is GoalStatus.RELEASED
    assert "g1" in lifecycle.retired_ids
    verdict2, cand2 = _verdict("c2")
    with pytest.raises(GoalRevivalError, match="retired"):
        lifecycle.adopt(verdict2, cand2, "g1", 10)
    lifecycle.adopt(verdict2, cand2, "g2", 10)  # 新 id 重走清单 → 可行
    assert lifecycle.status_of("g2") is GoalStatus.ACTIVE


def test_supersede_retires_old_and_adopts_new() -> None:
    verdict, cand = _verdict()
    lifecycle = GoalLifecycle(policy_version=PROFILE.policy_version)
    lifecycle.adopt(verdict, cand, "g1", 0)
    verdict2, cand2 = _verdict("c2")
    new_goal = lifecycle.supersede("g1", verdict2, cand2, "g2", 10)
    assert lifecycle.status_of("g1") is GoalStatus.SUPERSEDED
    assert lifecycle.status_of("g2") is GoalStatus.ACTIVE
    assert "g1" in lifecycle.retired_ids
    assert new_goal.goal_id == "g2"


def test_release_requires_reasons() -> None:
    verdict, cand = _verdict()
    lifecycle = GoalLifecycle(policy_version=PROFILE.policy_version)
    lifecycle.adopt(verdict, cand, "g1", 0)
    with pytest.raises(ValueError, match="reason_refs"):
        lifecycle.release("g1", reason_refs=())


def test_accept_decision_log_records_reasons() -> None:
    verdict, cand = _verdict()
    lifecycle = GoalLifecycle(policy_version=PROFILE.policy_version)
    lifecycle.adopt(verdict, cand, "g1", 0)
    logs = lifecycle.decisions
    assert logs[-1].decision is GoalDecision.ACCEPT
    assert "aff.1" in logs[-1].reason_refs
