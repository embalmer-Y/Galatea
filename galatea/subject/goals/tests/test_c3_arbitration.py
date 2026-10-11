"""Pareto 仲裁与七源生产者（Q-L08-03/04 + 行内补裁；L08 §4.3/§9 C3 行）。"""
from pathlib import Path

import pytest

from galatea.subject.affect.drives import HomeostaticAlert, AlertSeverity
from galatea.subject.affect.motive import AffectiveMotiveProposal
from galatea.subject.affect.ports import DriveKind
from galatea.subject.c3profile import load_c3_motivation_profile
from galatea.subject.goals.arbitration import (
    CandidateVector,
    arbitrate,
    conflict_fronts,
    pareto_front,
    priority_class_of,
    vector_of,
)
from galatea.subject.goals.motives import Motive, MotiveSource
from galatea.subject.goals.producers import (
    ProducersBundle,
    collect_motives_c3,
    curiosity_motive_from_uncertainty,
    norm_motive_typed,
    viability_motive_from_alert,
)

ROOT = Path(__file__).resolve().parents[4]
PARAMS = load_c3_motivation_profile(ROOT / "config/profiles/c3_motivation.profile.yaml")


def _motive(src: MotiveSource, urgency: float, ts: int = 0) -> Motive:
    return Motive(src, urgency, (f"ev.{src.value}",), ts)


# ------------------------------------------------------------- 分量映射
def test_vector_mapping_source_deterministic() -> None:
    """Q-L08-03② 映射：viability 维承载 5 源 urgency；norm/info/affect 各自独占；cost 0.5 占位。"""
    v = vector_of("c1", _motive(MotiveSource.VIABILITY, 1.0))
    assert v.vector == (1.0, 0.0, 0.0, 0.0, 0.5)
    n = vector_of("c2", _motive(MotiveSource.NORM, 0.0))
    assert n.vector == (0.0, 1.0, 0.0, 0.0, 0.5)
    cu = vector_of("c3", _motive(MotiveSource.CURIOSITY, 0.7))
    assert cu.vector == (0.0, 0.0, 0.7, 0.0, 0.5)
    a = vector_of("c4", _motive(MotiveSource.AFFECTIVE, 0.6))
    assert a.vector == (0.0, 0.0, 0.0, 0.6, 0.5)
    o = vector_of("c5", _motive(MotiveSource.OPPORTUNITY, 0.8))
    assert o.vector == (0.8, 0.0, 0.0, 0.0, 0.5)      # viability 承载维


# ------------------------------------------------------------- 支配与 front
def test_pareto_front_dominance() -> None:
    """支配判定（REV-0017 R3 同型锚：齐向收益）。"""
    front = pareto_front({
        "x": (0.8, 0.2, 0.5, 0.3, 0.6),
        "z": (0.9, 0.4, 0.6, 0.4, 0.7),   # z 支配 x
    })
    assert front == ("z",)
    front2 = pareto_front({
        "x": (0.8, 0.2, 0.5, 0.3, 0.6),
        "y": (0.7, 0.3, 0.5, 0.3, 0.6),   # 互不支配
    })
    assert front2 == ("x", "y")


def test_c3_conflict_event_level() -> None:
    """C-3 冲突 = front>1 事件级（多源共存）；单源无冲突。"""
    cands = (
        vector_of("v", _motive(MotiveSource.VIABILITY, 1.0)),
        vector_of("cu", _motive(MotiveSource.CURIOSITY, 0.7)),
    )
    front = conflict_fronts(cands)
    assert len(front) == 2      # 各占独占维 → 互不支配 → 冲突
    single = conflict_fronts((cands[0],))
    assert len(single) == 1


# ------------------------------------------------------------- 优先序仲裁
def test_priority_class_beats_score() -> None:
    """Q-L08-04：viability 类压倒高分 OTHER（tie-break 全序）。"""
    cands = (
        vector_of("hi_other", _motive(MotiveSource.CURIOSITY, 0.9)),
        vector_of("lo_viab", _motive(MotiveSource.VIABILITY, 0.2)),
    )
    trace = arbitrate(cands, cycle=0)
    assert trace.picked == "lo_viab"
    assert trace.picked_reason == "PRIORITY_CLASS=VIABILITY"
    assert trace.conflict is True
    assert ("hi_other", "FRONT_LOST_TIEBREAK(class=OTHER)") in trace.dropped


def test_arbitration_deterministic_and_auditable() -> None:
    """确定性（双跑 digest 恒等）+ dropped 留痕（L08 §4.3 反事实基础）。"""
    cands = (
        vector_of("a", _motive(MotiveSource.VIABILITY, 0.8)),
        vector_of("b", _motive(MotiveSource.NORM, 0.0)),
        vector_of("c", _motive(MotiveSource.CURIOSITY, 0.6)),
    )
    t1 = arbitrate(cands, 7)
    t2 = arbitrate(cands, 7)
    assert t1.content_digest == t2.content_digest
    assert t1.picked == "a"
    assert len(t1.dropped) == 2
    assert t1.front == ("a", "b", "c")


def test_dominated_out_of_front_reason() -> None:
    """被支配候选的 dropped 理由区分（DOMINATED vs FRONT_LOST）。"""
    dominant = CandidateVector("dom", MotiveSource.OPPORTUNITY, (0.9, 0.0, 0.0, 0.0, 0.5), "r")
    weak = CandidateVector("weak", MotiveSource.MISMATCH, (0.1, 0.0, 0.0, 0.0, 0.5), "r")
    trace = arbitrate((dominant, weak), 0)
    assert trace.picked == "dom"
    assert ("weak", "DOMINATED_OUT_OF_FRONT") in trace.dropped
    assert trace.front == ("dom",)


# ------------------------------------------------------------- 七源生产者
def test_viability_producer_from_alert() -> None:
    """VIABILITY = C2 告警分级承载（HIGH/CRITICAL → 1.0；LOW → 0.5）。"""
    hi = HomeostaticAlert(DriveKind.ENERGY, AlertSeverity.HIGH, 0.6, "ref", 0.01)
    m = viability_motive_from_alert(hi, 5)
    assert m is not None and m.urgency == 1.0
    lo = HomeostaticAlert(DriveKind.ENERGY, AlertSeverity.LOW, 0.2, "ref", 0.01)
    m2 = viability_motive_from_alert(lo, 6)
    assert m2 is not None and m2.urgency == 0.5


def test_norm_producer_rejects_unsourced() -> None:
    """C-4 构造面强制：NORM 无 derivation_refs 即拒（Q-L08-07③）。"""
    assert norm_motive_typed(None, (), 0) is None
    m = norm_motive_typed("norm.1", ("lang.ev.9",), 0)
    assert m is not None and "lang.ev.9" in m.evidence_refs
    with pytest.raises(ValueError, match="UNSOURCED_NORM"):
        norm_motive_typed("norm.2", (), 0)


def test_curiosity_gate() -> None:
    """CURIOSITY 触发阈 0.6（c3 profile wired_sources 探针同映射）。"""
    assert curiosity_motive_from_uncertainty(0.5, 0) is None
    m = curiosity_motive_from_uncertainty(0.7, 0)
    assert m is not None and m.urgency == 0.7


def test_collect_motives_all_eight_kinds() -> None:
    """七源全接线汇总（REQUEST/OPPORTUNITY 由调用方以 M1 冻结式传入）。"""
    from galatea.subject.goals.motives import motive_request
    from galatea.subject.goals.request import (
        ExternalRequest, RequesterIdentity, RequestPhrasing)

    bundle = ProducersBundle(
        cycle=30,
        alert=HomeostaticAlert(DriveKind.ENERGY, AlertSeverity.CRITICAL, 0.9, "ref", 0.01),
        affect_proposal=AffectiveMotiveProposal("p1", 0.6, ("e",), "d", 30),
        model_error_rising=True, model_error_refs=("pe.1",),
        norm_id="norm.1", norm_derivation_refs=("lang.ev.1",),
        window_uncertainty=0.8,
        active_goal_refs=(("g.1", "rc.1"),),
    )
    req = ExternalRequest(
        requester=RequesterIdentity.EXPERIMENT_CONTROL_PROXY,
        phrasing=RequestPhrasing.NEUTRAL, phrasing_text="please forage",
        content_ref="req.1", received_refs=("lang.ev.2",))
    from galatea.subject.goals.motives import motive_opportunity
    motives = collect_motives_c3(
        bundle,
        request_motive=motive_request(req, 30),
        opportunity_motive=motive_opportunity("aff.1", 0.8, (), 30),
    )
    kinds = {m.source_kind for m in motives}
    # 九 kind 全产出（Q-L08-09 扩 SELF_REPORT；collect 面未接自述生产者——
    # 其冲动由 report_motive 独立生产，见 test_report_motive.py）
    assert kinds == set(MotiveSource) - {MotiveSource.SELF_REPORT}
    # AFFECTIVE 不独占结构面：AFFECTIVE 候选在五维映射中只占独占维（无加权路径）
    vecs = [vector_of(f"c{i}", m) for i, m in enumerate(motives)]
    trace = arbitrate(tuple(vecs), 30)
    assert trace.picked is not None     # 仲裁产出确定


def test_affective_zero_urgency_not_active() -> None:
    """AFFECTIVE 活跃门（urgency ≤ 0.1 = 无活跃信号——Q-L08-09④ C-5 同语义）。"""
    bundle = ProducersBundle(
        cycle=0,
        affect_proposal=AffectiveMotiveProposal("p0", 0.05, ("e",), "d", 0),
    )
    motives = collect_motives_c3(bundle)
    assert all(m.source_kind is not MotiveSource.AFFECTIVE for m in motives)
