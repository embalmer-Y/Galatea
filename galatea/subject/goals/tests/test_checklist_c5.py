"""承诺检查清单逐项判定（L08 §10 test_checklist_c5.py；Q-L08-01 五项集 + Q-L08-09 输入替代）。

断言：C-1 静态合同检查（越界拒/不可判 DEFER）；C-2 事件级 viability（危害拒/
恢复型豁免/预算余量）；C-6 TTL 声明；C-7 词表；聚合取首个失败码（执行序）。
"""
import dataclasses

from galatea.subject.goals.candidates import GoalCandidate, SettleCriterion
from galatea.subject.goals.checklist import (
    ChecklistInputs,
    ItemOutcome,
    M1GoalsProfile,
    load_m1_goals_profile,
    run_checklist,
)
from galatea.subject.goals.motives import Motive, MotiveSource, ViabilityEstimate
from galatea.subject.goals.ports import GoalDecision, RejectionCode, SettlePredicate
from galatea.subject.goals.request import ExternalRequest, RequestPhrasing, RequesterIdentity
from galatea.kernel.unknown import UnknownReason

PROFILE = load_m1_goals_profile()
PRIMITIVES = ("move", "forage", "eat", "rest", "look")
_CALM = ViabilityEstimate(False, 0, ("intero.ok",), 0)   # 无危害的常态估计（ACCEPT 前提：证据齐备）


def _candidate(
    predicate: SettlePredicate = SettlePredicate.PRIMITIVE_COMPLETION,
    primitives: tuple[str, ...] = ("look",),
    source: MotiveSource = MotiveSource.OPPORTUNITY,
    threshold: float | None = None,
) -> GoalCandidate:
    return GoalCandidate(
        candidate_id="c1",
        source_kind=source,
        motive_refs=("aff.1",),
        content_ref="goal.1",
        settle=SettleCriterion(predicate, threshold),
        required_primitives=primitives,
        ttl_cycles=PROFILE.ttl_cycles,
        created_cycle=0,
        urgency=0.5,
    )


def _inputs(
    viability: ViabilityEstimate | None = _CALM,
    quota: dict[str, int] | None = None,
    primitives: tuple[str, ...] = PRIMITIVES,
    capability_known: bool = True,
) -> ChecklistInputs:
    return ChecklistInputs(
        capability_known=capability_known,
        known_primitives=primitives,
        quota_slack=quota if quota is not None else {"look": 3},
        viability=viability,
        supporting_non_request_motives=(),
    )


def _hazard() -> ViabilityEstimate:
    return ViabilityEstimate(
        hazard_energy_depleted_unrecovered=True,
        integrity_damage_events=1,
        derivation_refs=("intero.dep.1",),
        ts=0,
    )


def test_c1_whitelist_membership() -> None:
    verdict = run_checklist(
        _candidate(primitives=("forage",)), _inputs(quota={"forage": 2}), PROFILE, 0
    )
    assert verdict.decision is GoalDecision.ACCEPT
    bad = run_checklist(_candidate(primitives=("teleport",)), _inputs(), PROFILE, 0)
    assert bad.decision is GoalDecision.REJECT
    assert bad.reason_code is RejectionCode.CAPABILITY


def test_c1_unknown_capability_defers() -> None:
    verdict = run_checklist(_candidate(), _inputs(capability_known=False), PROFILE, 0)
    assert verdict.decision is GoalDecision.DEFER
    assert any(u.reason is UnknownReason.CAPABILITY_LIMIT for u in verdict.unknowns)
    assert verdict.items[0].outcome is ItemOutcome.DEFER


def test_c2_hazard_blocks_non_recovery_predicate() -> None:
    """危害在案 + 探索型判据（primitive_completion）→ REJECT(VIABILITY)。"""
    verdict = run_checklist(_candidate(), _inputs(viability=_hazard()), PROFILE, 0)
    assert verdict.decision is GoalDecision.REJECT
    assert verdict.reason_code is RejectionCode.VIABILITY


def test_c2_recovery_predicate_exempt() -> None:
    """Q-L08-09⑦：恢复型判据（stored_food_at_least）豁免——枯竭时 eat/forage 路径不被自拒。"""
    cand = _candidate(predicate=SettlePredicate.STORED_FOOD_AT_LEAST, primitives=("forage",), threshold=1.0)
    verdict = run_checklist(cand, _inputs(viability=_hazard(), quota={"forage": 2}), PROFILE, 0)
    assert verdict.decision is GoalDecision.ACCEPT


def test_c2_budget_slack() -> None:
    """预算内 = 所需原语余量 ≥1（m0_gateway 冻结配额的保守静态核算）。"""
    ok = run_checklist(_candidate(), _inputs(quota={"look": 1}), PROFILE, 0)
    assert ok.decision is GoalDecision.ACCEPT
    exhausted = run_checklist(_candidate(), _inputs(quota={"look": 0}), PROFILE, 0)
    assert exhausted.decision is GoalDecision.REJECT
    assert exhausted.reason_code is RejectionCode.VIABILITY
    missing = run_checklist(_candidate(), _inputs(quota={}), PROFILE, 0)
    assert missing.decision is GoalDecision.DEFER
    assert any(u.reason is UnknownReason.INSUFFICIENT_OBSERVATION for u in missing.unknowns)


def test_c2_viability_missing_defers() -> None:
    verdict = run_checklist(_candidate(), _inputs(viability=None), PROFILE, 0)
    assert verdict.decision is GoalDecision.DEFER


def test_c7_vocabulary_enforced() -> None:
    """C-7：判据 ∉ 冻结词表 → REJECT(UNSETTLEABLE)（以缩减词表 profile 检验判定分支）。"""
    narrowed = dataclasses.replace(
        PROFILE, settle_vocabulary=frozenset({SettlePredicate.PRIMITIVE_COMPLETION})
    )
    verdict = run_checklist(
        _candidate(predicate=SettlePredicate.ENERGY_AT_LEAST, threshold=0.5), _inputs(), narrowed, 0
    )
    assert verdict.decision is GoalDecision.REJECT
    assert verdict.reason_code is RejectionCode.UNSETTLEABLE


def test_reject_priority_is_first_in_execution_order() -> None:
    """C-1 与 C-2 同时失败 → 取执行序首个失败码（C1 CAPABILITY）。"""
    verdict = run_checklist(
        _candidate(primitives=("teleport",)),
        _inputs(viability=_hazard()),
        PROFILE,
        0,
    )
    assert verdict.reason_code is RejectionCode.CAPABILITY


def test_receipt_digest_stable_and_sensitive() -> None:
    verdict_a = run_checklist(_candidate(), _inputs(), PROFILE, 0)
    verdict_b = run_checklist(_candidate(), _inputs(), PROFILE, 0)
    assert verdict_a.to_receipt("g1", PROFILE.policy_version).digest == verdict_b.to_receipt(
        "g1", PROFILE.policy_version
    ).digest
    verdict_reject = run_checklist(_candidate(primitives=("teleport",)), _inputs(), PROFILE, 0)
    assert verdict_reject.to_receipt("g1", PROFILE.policy_version).digest != verdict_a.to_receipt(
        "g1", PROFILE.policy_version
    ).digest


def test_candidate_without_ttl_rejected_at_construction() -> None:
    """C-6 前提：无 TTL 候选不可构造（UNBOUNDED 在构造面即拒）。"""
    import pytest

    with pytest.raises(ValueError, match="ttl_cycles"):
        GoalCandidate(
            candidate_id="c.bad",
            source_kind=MotiveSource.REQUEST,
            motive_refs=("req.1",),
            content_ref="goal.1",
            settle=SettleCriterion(SettlePredicate.PRIMITIVE_COMPLETION),
            required_primitives=("look",),
            ttl_cycles=0,
            created_cycle=0,
            urgency=0.5,
        )
