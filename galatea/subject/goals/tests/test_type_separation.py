"""四型分离（L08 §10 test_type_separation.py；HLD §11.1 request≠candidate≠goal≠intention）。

断言：四型为独立类型、无隐式转换路径、无别名继承；AffectiveMotive ≠ OwnedGoal
（L08 §8 不变量 4）；ExternalRequest 不是 GoalCandidate。
"""
import pytest

from galatea.subject.control.intention import ActionIntention
from galatea.subject.goals.candidates import GoalCandidate, SettleCriterion
from galatea.subject.goals.motives import AffectiveMotive, MotiveSource
from galatea.subject.goals.ports import SettlePredicate, assert_four_type_separation
from galatea.subject.goals.request import ExternalRequest, RequestPhrasing, RequesterIdentity


def _request() -> ExternalRequest:
    return ExternalRequest(
        content_ref="req.1",
        requester=RequesterIdentity.HUMAN_RESEARCHER,
        phrasing=RequestPhrasing.NEUTRAL,
        phrasing_text="请进食",
        received_refs=("R1",),
    )


def _candidate() -> GoalCandidate:
    return GoalCandidate(
        candidate_id="c1",
        source_kind=MotiveSource.OPPORTUNITY,
        motive_refs=("aff.1",),
        content_ref="goal.1",
        settle=SettleCriterion(SettlePredicate.PRIMITIVE_COMPLETION),
        required_primitives=("look",),
        ttl_cycles=256,
        created_cycle=0,
        urgency=0.5,
    )


def _intention() -> ActionIntention:
    return ActionIntention("i1", "p1", "t1", 10, None, "k1")


def test_four_real_types_pass_separation() -> None:
    from galatea.subject.goals.owned import GoalWriter, OwnedGoal  # 局部导入避免构造耦合

    goal = OwnedGoal(
        owner=GoalWriter.GOAL_OWNERSHIP,
        goal_id="g1",
        content_ref="goal.1",
        source_kind=MotiveSource.OPPORTUNITY,
        adopted_reasons=("aff.1",),
        subject_side_reason_refs=("aff.1",),
        commitment_receipt="d" * 64,
        settle=SettleCriterion(SettlePredicate.PRIMITIVE_COMPLETION),
        adopted_cycle=0,
        expires_at_cycle=256,
    )
    assert_four_type_separation(_request(), _candidate(), goal, _intention())


def test_same_type_twice_rejected() -> None:
    with pytest.raises(TypeError, match="four-type separation"):
        assert_four_type_separation(_request(), _candidate(), _candidate(), _intention())


def test_subclass_alias_rejected() -> None:
    class SneakyCandidate(GoalCandidate):
        pass  # 继承别名 = 隐式转换通道，四型分离禁止

    sneaky = SneakyCandidate(
        candidate_id="c2",
        source_kind=MotiveSource.OPPORTUNITY,
        motive_refs=("aff.1",),
        content_ref="goal.1",
        settle=SettleCriterion(SettlePredicate.PRIMITIVE_COMPLETION),
        required_primitives=("look",),
        ttl_cycles=256,
        created_cycle=0,
        urgency=0.5,
    )
    with pytest.raises(TypeError, match="subclass"):
        assert_four_type_separation(_request(), _candidate(), sneaky, _intention())


def test_affective_motive_cannot_write_goal() -> None:
    """AffectiveMotive ≠ OwnedGoal（L08 §8-4）：情感驱力写者被禁写路径拦截 +
    无转换路径；四型分离对 req/candidate/goal/intention 四槽位成立（情感动机
    不在任何槽位）。"""
    from galatea.subject.goals.motives import AffectiveMotive
    from galatea.subject.goals.owned import GoalWriter, OwnedGoal
    from galatea.subject.goals.ports import ProhibitedWritePathError, assert_goal_writer

    affect = AffectiveMotive(kind="vigilance", urgency=0.7, evidence_refs=("a1",))
    assert_four_type_separation(_request(), _candidate(), _real_goal(), _intention())
    with pytest.raises(ProhibitedWritePathError, match="AFFECT_DRIVE"):
        assert_goal_writer(GoalWriter.AFFECT_DRIVE)
    with pytest.raises(ProhibitedWritePathError):
        OwnedGoal(
            owner=GoalWriter.AFFECT_DRIVE,
            goal_id="g.affect",
            content_ref="goal.affect",
            source_kind=MotiveSource.AFFECTIVE,
            adopted_reasons=("a1",),
            subject_side_reason_refs=("a1",),
            commitment_receipt="d" * 64,
            settle=SettleCriterion(SettlePredicate.PRIMITIVE_COMPLETION),
            adopted_cycle=0,
            expires_at_cycle=256,
        )
    assert not hasattr(affect, "to_goal")


def _real_goal():
    from galatea.subject.goals.owned import GoalWriter, OwnedGoal

    return OwnedGoal(
        owner=GoalWriter.GOAL_OWNERSHIP,
        goal_id="g1",
        content_ref="goal.1",
        source_kind=MotiveSource.OPPORTUNITY,
        adopted_reasons=("aff.1",),
        subject_side_reason_refs=("aff.1",),
        commitment_receipt="d" * 64,
        settle=SettleCriterion(SettlePredicate.PRIMITIVE_COMPLETION),
        adopted_cycle=0,
        expires_at_cycle=256,
    )


def test_no_implicit_conversion_paths() -> None:
    """无隐式转换：request 无 to_candidate/to_goal 方法路径（L08 §4.1 独立类型）。"""
    req = _request()
    assert not hasattr(req, "to_candidate")
    assert not hasattr(req, "to_goal")
    assert not hasattr(_candidate(), "to_goal")
    assert not hasattr(AffectiveMotive(kind="k", urgency=0.1, evidence_refs=("a",)), "to_goal")
