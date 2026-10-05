"""能力估计测试（L04 §7 calibration 行：FEASIBLE 声明与静态合同/证据同源）。"""
import pytest

from galatea.subject.models.body import MW0_PRIMITIVES, capability_for, static_capability


def test_five_primitives_feasible():
    """MW0 五原语 → FEASIBLE（静态合同 Q-L08-09①；evidence = 冻结白名单引用）。"""
    caps = {c.action_class: c for c in static_capability()}
    assert set(caps) == set(MW0_PRIMITIVES)
    for cap in caps.values():
        assert cap.status.value == "FEASIBLE"
        assert cap.evidence_refs == ("f0_action_contract@v1.0.containment_whitelist_mw0",)


def test_unknown_class_infeasible():
    cap = capability_for("fly")
    assert cap.status.value == "INFEASIBLE"
    assert cap.evidence_refs


def test_capability_requires_evidence():
    """禁无证据能力主张（CapabilityEstimate 构造期强制）。"""
    from galatea.subject.models.body import CapabilityEstimate, CapabilityStatus

    with pytest.raises(ValueError, match="evidence_refs"):
        CapabilityEstimate(action_class="move", status=CapabilityStatus.FEASIBLE, evidence_refs=())


def test_body_belief_rejects_non_body_carriers():
    """telemetry 直填 = 禁（L04 §8 禁写路径）：非 INTERO 模态帧构造即拒。"""
    from galatea.subject.models.body import TelemetrySourceRejected, build_body_belief
    from galatea.subject.perception.tests.conftest import frames_at, uniform_window

    frames = frames_at(uniform_window(0.9), 7)
    extero = next(f for f in frames if f.modality.value == "EXT_LOCAL_OBS")
    with pytest.raises(TelemetrySourceRejected):
        build_body_belief(extero, None, "body.R", 7)


def test_body_belief_from_real_frames():
    from galatea.subject.models.body import build_body_belief
    from galatea.subject.perception.tests.conftest import frames_at, uniform_window

    frames = frames_at(uniform_window(0.9), 7, energy=0.62)
    intero = next(f for f in frames if f.modality.value == "INTERO")
    proprio = next(f for f in frames if f.modality.value == "PROPRIO")
    body = build_body_belief(intero, proprio, "body.R", 7)
    assert body.energy_belief == 0.62
    assert body.load_belief == 0.0            # M0 冻结简化（Q-L01-09⑥）
    assert body.orientation == "N"
    assert set(body.sources) == {intero.frame_id, proprio.frame_id}
