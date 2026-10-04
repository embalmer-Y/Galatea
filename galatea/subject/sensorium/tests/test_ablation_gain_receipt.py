"""消融：移除增益回执可检出（L02 §7 ablation①/§10 test_ablation_gain_receipt.py）。

INC-08 教训：消融必须先证明检出面可见且能失败——本测试注入"回执缺失"与
"回执绑定破坏"两种消融，audit 必须检出。
"""
from pathlib import Path

import pytest

from galatea.subject.sensorium.calibration import bind_calibration
from galatea.subject.sensorium.pipeline import SensoriumPipeline, audit
from galatea.subject.sensorium.ports import load_c0_sensorium_profile
from galatea.subject.sensorium.tests.conftest import extero_packet, intero_packet, proprio_packet

_ROOT = Path(__file__).resolve().parents[4]
_PROFILE_PATH = _ROOT / "config" / "profiles" / "c0_sensorium.profile.yaml"


def _pipeline() -> SensoriumPipeline:
    from galatea.subject.sensorium.tests.conftest import time_basis

    profile = load_c0_sensorium_profile(_PROFILE_PATH)
    return SensoriumPipeline(
        profile, bind_calibration(_PROFILE_PATH, profile.calibration_version), time_basis()
    )


def _healthy_output():
    from galatea.subject.sensorium.tests.conftest import run_full_stream

    pipeline = _pipeline()
    outputs = run_full_stream(pipeline, 5)
    frames = tuple(f for o in outputs for f in o.frames)
    receipts = tuple(r for o in outputs for r in o.formation_receipts)
    gains = tuple(g for o in outputs for g in o.gain_receipts)
    audit(frames, receipts, gains)   # 健全面：审计通过（非空流）
    assert frames
    return frames, receipts, gains


def test_ablation_gain_receipt_removed_detected() -> None:
    """移除一个增益回执 → audit 检出（C2 因果调制证据缺失的可检面）。"""
    frames, receipts, gains = _healthy_output()
    with pytest.raises(AssertionError, match="gain receipt audit failed"):
        audit(frames, receipts, gains[:-1])


def test_ablation_formation_receipt_removed_detected() -> None:
    """移除一个形成回执 → audit 检出（无帧无回执纪律）。"""
    frames, receipts, gains = _healthy_output()
    with pytest.raises(AssertionError, match="formation receipt audit failed"):
        audit(frames, receipts[:-1], gains)


def test_ablation_receipt_frame_mismatch_detected() -> None:
    """回执 digest 伪造 → audit 检出（帧↔回执一一对应；audit 按帧 id 查找，
    重排不可通过——绑定完整性由 digest 核验承载）。"""
    frames, receipts, gains = _healthy_output()
    forged = object.__setattr__(receipts[0], "frame_digest", "f" * 64) or receipts[0]
    with pytest.raises(AssertionError, match="digest mismatch"):
        audit(frames, (forged,) + receipts[1:], gains)
