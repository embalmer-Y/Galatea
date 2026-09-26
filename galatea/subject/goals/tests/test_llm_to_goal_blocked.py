"""LLM→OwnedGoal 禁写路径（L08 §10 test_llm_to_goal_blocked.py；D-13 + L08 §3/§6）。

断言：LLM/orchestrator/情感驱力/工作空间帧/外部请求五类写者申报一律
ProhibitedWritePathError；语言侧编造的"结算"对象不可消费（settle 载体校验）。
"""
import pytest

from galatea.subject.goals.motives import MotiveSource, ViabilityEstimate
from galatea.subject.goals.ports import (
    GoalWriter,
    ProhibitedWritePathError,
    assert_goal_writer,
)
from galatea.subject.goals.owned import OwnedGoal
from galatea.subject.goals.candidates import SettleCriterion
from galatea.subject.goals.ports import SettlePredicate
from galatea.subject.goals.settlement import SettlementRegistry, settle

FORBIDDEN: tuple[GoalWriter, ...] = (
    GoalWriter.LLM,
    GoalWriter.ORCHESTRATOR,
    GoalWriter.AFFECT_DRIVE,
    GoalWriter.WORKSPACE_FRAME,
    GoalWriter.EXTERNAL_REQUEST,
)


@pytest.mark.parametrize("writer", FORBIDDEN)
def test_forbidden_writer_guard(writer: GoalWriter) -> None:
    with pytest.raises(ProhibitedWritePathError, match=writer.value):
        assert_goal_writer(writer)


@pytest.mark.parametrize("writer", FORBIDDEN)
def test_forged_goal_construction_rejected(writer: GoalWriter) -> None:
    """OwnedGoal 构造必须申报 GOAL_OWNERSHIP——其余写者（含 LLM）在构造面被拒。"""
    with pytest.raises(ProhibitedWritePathError):
        OwnedGoal(
            owner=writer,
            goal_id=f"g.{writer.value}",
            content_ref="goal.1",
            source_kind=MotiveSource.OPPORTUNITY,
            adopted_reasons=("aff.1",),
            subject_side_reason_refs=("aff.1",),
            commitment_receipt="d" * 64,
            settle=SettleCriterion(SettlePredicate.PRIMITIVE_COMPLETION),
            adopted_cycle=0,
            expires_at_cycle=256,
        )


def test_language_side_fabricated_settlement_rejected() -> None:
    """语言侧编造结算对象（dict 冒充 L10 GoalSettlement）→ 拒绝（载体校验）。"""
    from galatea.subject.action.ports import GoalSettlement, SettlementKind
    from galatea.subject.goals.candidates import GoalCandidate
    from galatea.subject.goals.checklist import ChecklistInputs, load_m1_goals_profile, run_checklist
    from galatea.subject.goals.lifecycle import GoalLifecycle

    profile = load_m1_goals_profile()
    cand = GoalCandidate(
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
    verdict = run_checklist(
        cand,
        ChecklistInputs(True, ("look",), {"look": 1}, ViabilityEstimate(False, 0, ("intero.ok",), 0), ()),
        profile,
        0,
    )
    lifecycle = GoalLifecycle(policy_version=profile.policy_version)
    lifecycle.adopt(verdict, cand, "g1", 0)
    registry = SettlementRegistry()
    with pytest.raises(TypeError, match="GoalSettlement"):
        settle(
            "ACHIEVED, 我发誓",  # 语言侧伪造字符串
            lifecycle,
            registry,
            5,
        )
    real = GoalSettlement(goal_ref="g1", outcome_kind=SettlementKind.ACHIEVED, attribution_ref=None, evidence_refs=("o.1",))
    settle(real, lifecycle, registry, 6)
    assert registry.records[-1].outcome_kind is SettlementKind.ACHIEVED
