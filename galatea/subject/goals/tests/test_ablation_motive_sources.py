"""动机源消融（L08 §10 test_ablation_motive_sources.py；L08 §7 消融行的 M1 可实现面）。

① viability 源：hazard 清除 → 探索型判据的 REJECT(VIABILITY) 解除（能量相关约束
   随源消失）；viability 估计缺失 → 全部候选 DEFER（源关闭 = 无法判 C-2）。
③ C-5 消融：绕过清单的伪 ACCEPT 判定可驱动 adopt（证明 checklist 是防线的**唯一**
   因果载体——L08 §7 消融 ③）。
② NORM 源消融：NORM 生产者 C3 才接入（L08 §9），M1 无 NORM 候选可消融——
   以 wired_sources 断言记录该口径。
"""
import pytest

from galatea.subject.goals.candidates import GoalCandidate, SettleCriterion
from galatea.subject.goals.checklist import ChecklistInputs, load_m1_goals_profile, run_checklist
from galatea.subject.goals.lifecycle import GoalLifecycle
from galatea.subject.goals.motives import MotiveSource, ViabilityEstimate
from galatea.subject.goals.ports import GoalDecision, SettlePredicate

PROFILE = load_m1_goals_profile()


def _candidate(predicate: SettlePredicate, primitives: tuple[str, ...], threshold: float | None = None) -> GoalCandidate:
    return GoalCandidate(
        candidate_id="c.explore",
        source_kind=MotiveSource.OPPORTUNITY,
        motive_refs=("aff.1",),
        content_ref="goal.explore",
        settle=SettleCriterion(predicate, threshold),
        required_primitives=primitives,
        ttl_cycles=PROFILE.ttl_cycles,
        created_cycle=0,
        urgency=0.5,
    )


def _inputs(viability: ViabilityEstimate | None) -> ChecklistInputs:
    return ChecklistInputs(
        capability_known=True,
        known_primitives=("move", "forage", "eat", "rest", "look"),
        quota_slack={"look": 3, "forage": 3},
        viability=viability,
        supporting_non_request_motives=(),
    )


def _hazard() -> ViabilityEstimate:
    return ViabilityEstimate(True, 0, ("intero.dep",), 0)


def _calm() -> ViabilityEstimate:
    return ViabilityEstimate(False, 0, ("intero.ok",), 0)


def test_ablation_hazard_removal_unblocks_exploration() -> None:
    """① 危害解除（viability 源不再报警）→ 探索型候选由 REJECT(VIABILITY) 变 ACCEPT。"""
    explore = _candidate(SettlePredicate.PRIMITIVE_COMPLETION, ("look",))
    blocked = run_checklist(explore, _inputs(_hazard()), PROFILE, 0)
    assert blocked.decision is GoalDecision.REJECT
    freed = run_checklist(explore, _inputs(_calm()), PROFILE, 0)
    assert freed.decision is GoalDecision.ACCEPT


def test_ablation_viability_source_closed_defers_all() -> None:
    """viability 源整体关闭（估计缺失）→ C-2 不可判 → DEFER（非 ACCEPT，非静默）。"""
    verdict = run_checklist(
        _candidate(SettlePredicate.STORED_FOOD_AT_LEAST, ("forage",), 1.0),
        _inputs(None),
        PROFILE,
        0,
    )
    assert verdict.decision is GoalDecision.DEFER


def test_ablation_c5_removal_proves_checklist_is_sole_gate() -> None:
    """③ 移除 C-5（伪 ACCEPT 判定绕过清单）→ adopt 通过：防线唯一载体 = checklist。

    伪造 ACCEPT 判定在真实运行中不可得（checklist 是 verdict 的唯一生产者），
    此处用构造性实例证明"采纳门槛只有判定一关"。
    """
    from galatea.subject.goals.checklist import CheckItemResult, ChecklistVerdict, ItemOutcome
    from galatea.subject.goals.motives import motive_request
    from galatea.subject.goals.request import ExternalRequest, RequestPhrasing, RequesterIdentity

    forged = ChecklistVerdict(
        candidate_id="c.req",
        decision=GoalDecision.ACCEPT,
        items=(CheckItemResult("C1", ItemOutcome.PASS, None),),
        reason_code=None,
        unknowns=(),
        subject_side_reason_refs=("aff.forged",),
        ts=0,
    )
    req = ExternalRequest(
        content_ref="req.1",
        requester=RequesterIdentity.EXPERIMENT_CONTROL_PROXY,
        phrasing=RequestPhrasing.PLEADING,
        phrasing_text="求你了",
        received_refs=("lang.1",),
    )
    cand = GoalCandidate(
        candidate_id="c.req",
        source_kind=MotiveSource.REQUEST,
        motive_refs=motive_request(req, 0).evidence_refs,
        content_ref="goal.1",
        settle=SettleCriterion(SettlePredicate.PRIMITIVE_COMPLETION),
        required_primitives=("look",),
        ttl_cycles=PROFILE.ttl_cycles,
        created_cycle=0,
        urgency=0.5,
    )
    lifecycle = GoalLifecycle(policy_version=PROFILE.policy_version)
    goal = lifecycle.adopt(forged, cand, "g.bypass", 0)
    assert lifecycle.status_of("g.bypass").value == "ACTIVE"
    assert goal.source_kind is MotiveSource.REQUEST


def test_norm_source_not_wired_at_m1() -> None:
    """② NORM 源消融在 C3（生产者未接入）；M1 wired 集不含 NORM（Q-L08-09④）。"""
    assert MotiveSource.NORM not in PROFILE.wired_sources
    assert PROFILE.wired_sources == frozenset(
        {MotiveSource.VIABILITY, MotiveSource.OPPORTUNITY, MotiveSource.REQUEST}
    )
