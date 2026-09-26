"""结算消费、TTL-only 自动结算、迟到 revision（L08 §10 test_settlement_revision.py）。

断言：L10 五态映射（ACHIEVED/FAILED→SETTLED、ABANDONED→RELEASED、
SUPERSEDED→SUPERSEDED、UNKNOWN→保持 ACTIVE 合法结算）；伪造结算拒绝
（非 GoalSettlement 载体/无证据引用）；TTL 到期自动 FAILED（Q-L08-09⑧）；
迟到结算 = revision 记录不改历史；pending 视图。
"""
import pytest

from galatea.subject.action.ports import GoalSettlement, SettlementKind
from galatea.subject.goals.candidates import GoalCandidate, SettleCriterion
from galatea.subject.goals.checklist import ChecklistInputs, load_m1_goals_profile, run_checklist
from galatea.subject.goals.lifecycle import GoalLifecycle, GoalStatus, LifecycleError
from galatea.subject.goals.motives import MotiveSource, ViabilityEstimate
from galatea.subject.goals.ports import SettlePredicate
from galatea.subject.goals.settlement import (
    SettlementRegistry,
    SettlementSource,
    expire_unsettled,
    pending,
    settle,
)

PROFILE = load_m1_goals_profile()


def _lifecycle_with_goal(goal_id: str = "g1", ttl: int = 256) -> tuple[GoalLifecycle, GoalCandidate]:
    cand = GoalCandidate(
        candidate_id="c1",
        source_kind=MotiveSource.OPPORTUNITY,
        motive_refs=("aff.1",),
        content_ref="goal.1",
        settle=SettleCriterion(SettlePredicate.PRIMITIVE_COMPLETION),
        required_primitives=("look",),
        ttl_cycles=ttl,
        created_cycle=0,
        urgency=0.5,
    )
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
    lifecycle = GoalLifecycle(policy_version=PROFILE.policy_version)
    lifecycle.adopt(verdict, cand, goal_id, 0)
    return lifecycle, cand


def _settlement(kind: SettlementKind, goal_ref: str = "g1") -> GoalSettlement:
    return GoalSettlement(
        goal_ref=goal_ref,
        outcome_kind=kind,
        attribution_ref="attr.1" if kind is SettlementKind.ACHIEVED else None,
        evidence_refs=(f"ev.{kind.value}",),
    )


def test_achieved_and_failed_settle() -> None:
    lifecycle, _ = _lifecycle_with_goal("g1")
    registry = SettlementRegistry()
    settle(_settlement(SettlementKind.ACHIEVED), lifecycle, registry, 10)
    assert lifecycle.status_of("g1") is GoalStatus.SETTLED
    assert registry.records[-1].source is SettlementSource.L10_SETTLEMENT

    lifecycle2, _ = _lifecycle_with_goal("g2")
    settle(_settlement(SettlementKind.FAILED, "g2"), lifecycle2, SettlementRegistry(), 10)
    assert lifecycle2.status_of("g2") is GoalStatus.SETTLED


def test_unknown_settlement_keeps_goal_active() -> None:
    """UNKNOWN 是合法结算：目标保持 ACTIVE（禁把 unresolved 归为 FAILED，L10 §4.5）。"""
    lifecycle, _ = _lifecycle_with_goal("g1")
    registry = SettlementRegistry()
    record = settle(_settlement(SettlementKind.UNKNOWN), lifecycle, registry, 10)
    assert record.applied_status is None
    assert lifecycle.status_of("g1") is GoalStatus.ACTIVE
    assert pending(lifecycle, registry) == ("g1",)


def test_abandoned_and_superseded_map_to_retired() -> None:
    lifecycle, _ = _lifecycle_with_goal("g1")
    registry = SettlementRegistry()
    settle(_settlement(SettlementKind.ABANDONED), lifecycle, registry, 10)
    assert lifecycle.status_of("g1") is GoalStatus.RELEASED
    assert "g1" in lifecycle.retired_ids

    lifecycle2, _ = _lifecycle_with_goal("g2")
    settle(_settlement(SettlementKind.SUPERSEDED, "g2"), lifecycle2, SettlementRegistry(), 10)
    assert lifecycle2.status_of("g2") is GoalStatus.SUPERSEDED


def test_forged_settlement_rejected() -> None:
    """禁伪造：非 L10 GoalSettlement 载体（如语言侧/编排侧编造的 dict）→ TypeError。"""
    lifecycle, _ = _lifecycle_with_goal("g1")
    with pytest.raises(TypeError, match="GoalSettlement"):
        settle({"goal_ref": "g1", "outcome_kind": "ACHIEVED"}, lifecycle, SettlementRegistry(), 5)  # type: ignore[arg-type]


def test_achieved_without_evidence_rejected() -> None:
    lifecycle, _ = _lifecycle_with_goal("g1")
    bare = GoalSettlement(goal_ref="g1", outcome_kind=SettlementKind.ACHIEVED, attribution_ref=None, evidence_refs=())
    with pytest.raises(ValueError, match="evidence_refs"):
        settle(bare, lifecycle, SettlementRegistry(), 5)
    assert lifecycle.status_of("g1") is GoalStatus.ACTIVE  # 拒绝后目标不受影响


def test_ttl_expiry_auto_failed() -> None:
    """Q-L08-09⑧：TTL 到期未达成 → FAILED/SETTLED（唯一机械可判失败分支）。"""
    lifecycle, _ = _lifecycle_with_goal("g1", ttl=256)
    registry = SettlementRegistry()
    assert expire_unsettled(lifecycle, registry, 255) == ()
    assert lifecycle.status_of("g1") is GoalStatus.ACTIVE
    assert expire_unsettled(lifecycle, registry, 256) == ("g1",)
    assert lifecycle.status_of("g1") is GoalStatus.SETTLED
    record = registry.latest_for("g1")
    assert record is not None and record.source is SettlementSource.TTL_EXPIRY
    assert record.outcome_kind is SettlementKind.FAILED


def test_late_settlement_is_revision_not_rewrite() -> None:
    """迟到结算以 revision 表达：不改状态、不改历史（append-only 留痕，L08 §6）。"""
    lifecycle, _ = _lifecycle_with_goal("g1")
    registry = SettlementRegistry()
    first = settle(_settlement(SettlementKind.ACHIEVED), lifecycle, registry, 10)
    assert lifecycle.status_of("g1") is GoalStatus.SETTLED
    revision = settle(_settlement(SettlementKind.FAILED), lifecycle, registry, 500)
    assert revision.revision_of == first.record_id
    assert revision.applied_status is None                    # 修订不改状态
    assert lifecycle.status_of("g1") is GoalStatus.SETTLED    # 历史不被改写
    assert len(registry.records) == 2


def test_settlement_for_unknown_goal_rejected() -> None:
    lifecycle, _ = _lifecycle_with_goal("g1")
    with pytest.raises(LifecycleError, match="unknown goal_id"):
        settle(_settlement(SettlementKind.ACHIEVED, "g.nobody"), lifecycle, SettlementRegistry(), 10)
