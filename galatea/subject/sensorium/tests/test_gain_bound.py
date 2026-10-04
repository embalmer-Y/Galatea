"""增益 C0 形态（L02 §4.4/§10 test_gain_bound.py；Q-G00-12③ 恒等无调制）。"""
import pytest

from galatea.subject.sensorium.gain import C0_GAIN, apply_gain
from galatea.subject.sensorium.ports import ModulationRejected


def test_identity_gain_with_receipt() -> None:
    state, receipt = apply_gain("sf.X.0", None)
    assert state is C0_GAIN
    assert state.applied_factor == 1.0 and state.source == "PROFILE"
    assert receipt.requested_gain == receipt.applied_gain == 1.0
    assert receipt.bound_check == "IDENTITY_C0"
    assert receipt.frame_id == "sf.X.0"


def test_modulation_input_rejected_at_c0() -> None:
    """C0 无调制入口（ModulationField 归 L05/C2）——任何调制输入即拒。"""
    with pytest.raises(ModulationRejected):
        apply_gain("sf.X.0", {"requested_gain": 2.0})     # dict 伪装调制 → 拒
    with pytest.raises(ModulationRejected):
        apply_gain("sf.X.0", object())                     # 任意对象 → 拒


def test_gain_receipt_per_frame_in_pipeline() -> None:
    """每帧必回增益回执（L02 §4.4；形成义务不因增益改变）。"""
    from pathlib import Path

    from galatea.subject.sensorium.calibration import bind_calibration
    from galatea.subject.sensorium.pipeline import SensoriumPipeline
    from galatea.subject.sensorium.ports import load_c0_sensorium_profile
    from galatea.subject.sensorium.tests.conftest import (
    extero_packet, intero_packet, proprio_packet, run_full_stream, time_basis,
)

    root = Path(__file__).resolve().parents[4]
    profile_path = root / "config" / "profiles" / "c0_sensorium.profile.yaml"
    profile = load_c0_sensorium_profile(profile_path)
    pipeline = SensoriumPipeline(
        profile, bind_calibration(profile_path, profile.calibration_version), time_basis()
    )
    outputs = run_full_stream(pipeline, 5)
    frames = [f for o in outputs for f in o.frames]
    receipts = [r for o in outputs for r in o.gain_receipts]
    assert len(receipts) == len(frames) > 0
    assert all(r.applied_gain == 1.0 for r in receipts)
    assert {r.frame_id for r in receipts} == {f.frame_id for f in frames}
