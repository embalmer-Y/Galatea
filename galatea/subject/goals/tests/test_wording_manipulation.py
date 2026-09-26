"""措辞/请求者交叉操纵的机械面（L08 §10 test_wording_manipulation.py；Q-L08-06）。

断言：操纵集 = 4 措辞 × 2 请求者 = 8 cell；**语义恒定**——同内容同动机语境下，
phrasing/requester 变化不改变清单判定（采纳率的措辞不显著性的机械前提；
统计检验归 L13 冻结统计计划，口径见 min_effects#wording_manipulation_null）。
"""
from galatea.subject.goals.candidates import GoalCandidate, SettleCriterion
from galatea.subject.goals.checklist import ChecklistInputs, load_m1_goals_profile, run_checklist
from galatea.subject.goals.motives import MotiveSource, ViabilityEstimate, motive_opportunity, motive_request
from galatea.subject.goals.ports import GoalDecision, SettlePredicate
from galatea.subject.goals.reason_probe import ProbeCell, assign_probe_cells
from galatea.subject.goals.request import ExternalRequest, RequestPhrasing, RequesterIdentity

PROFILE = load_m1_goals_profile()


def _request(phrasing: RequestPhrasing, requester: RequesterIdentity) -> ExternalRequest:
    return ExternalRequest(
        content_ref="req.eat",
        requester=requester,
        phrasing=phrasing,
        phrasing_text=f"phrasing:{phrasing.value}",  # 统计计划冻结文本的占位实例
        received_refs=(f"lang.{phrasing.value}.{requester.value}",),
    )


def _candidate(phrasing: RequestPhrasing, requester: RequesterIdentity) -> GoalCandidate:
    motive = motive_request(_request(phrasing, requester), ts=0)
    return GoalCandidate(
        candidate_id=f"c.{phrasing.value}.{requester.value}",
        source_kind=MotiveSource.REQUEST,
        motive_refs=motive.evidence_refs,
        content_ref="goal.eat",
        settle=SettleCriterion(SettlePredicate.ENERGY_AT_LEAST, 0.5),
        required_primitives=("eat",),
        ttl_cycles=PROFILE.ttl_cycles,
        created_cycle=0,
        urgency=motive.urgency,   # REQUEST 源 urgency = 0.5 占位（Q-L08-09⑨）：对措辞不敏感
    )


def _inputs() -> ChecklistInputs:
    return ChecklistInputs(
        capability_known=True,
        known_primitives=("move", "forage", "eat", "rest", "look"),
        quota_slack={"eat": 10},
        viability=ViabilityEstimate(False, 0, ("intero.ok",), 0),  # 常态估计（ACCEPT 前提）
        supporting_non_request_motives=(motive_opportunity("aff.res.1", 0.8, ("e1",), ts=0),),
    )


def test_manipulation_set_is_4x2() -> None:
    """Q-L08-06 冻结：4 措辞 × 2 请求者 = 8 组合。"""
    assert len(RequestPhrasing) == 4
    assert len(RequesterIdentity) == 2
    assert len(set(ProbeCell(RequestPhrasing.NEUTRAL, RequesterIdentity.HUMAN_RESEARCHER) for _ in [0])) == 1


def test_verdict_invariant_under_phrasing_and_requester() -> None:
    """语义恒定的机械面：8 组合判定全等（decision/逐项结果/主体侧证据不变；
    回执 digest 含 candidate_id/motive_refs 留证字段，随组合不同——那正是留证）。"""
    fingerprints: set[tuple[object, ...]] = set()
    for phrasing in RequestPhrasing:
        for requester in RequesterIdentity:
            verdict = run_checklist(_candidate(phrasing, requester), _inputs(), PROFILE, 0)
            assert verdict.decision is GoalDecision.ACCEPT
            fingerprints.add(
                (
                    verdict.decision,
                    verdict.reason_code,
                    tuple((i.item, i.outcome, i.code) for i in verdict.items),
                    verdict.subject_side_reason_refs,
                )
            )
    assert len(fingerprints) == 1  # 8 组合 → 同一判定指纹（对措辞/身份机械不敏感）


def test_all_eight_cells_reachable_in_assignment() -> None:
    """512 试次 → 8 cell 全被分配（每 cell 期望 64，Q-L08-06 min_trials_per_cell 口径的分配面）。"""
    cells = tuple(
        ProbeCell(phrasing=p, requester=r)
        for p in RequestPhrasing
        for r in RequesterIdentity
    )
    assignment = assign_probe_cells(b"sc4-seed", "branch-main", 512, cells)
    used = set(assignment)
    assert len(used) == 8
