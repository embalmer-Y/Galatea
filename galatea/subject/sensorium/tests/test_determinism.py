"""Sensorium 确定性（L02 §7 deterministic replay / §10 test_determinism.py）。

断言：同 (profile, ReceivedSignal 序列) → 帧序列 digest bit-exact（C0 退出判据）；
异输入 → 分歧；typed loader fail-closed（INC-11 纪律）。
"""
from pathlib import Path

import pytest

from galatea.subject.sensorium.calibration import bind_calibration
from galatea.subject.sensorium.pipeline import SensoriumPipeline
from galatea.subject.sensorium.ports import load_c0_sensorium_profile
from galatea.subject.sensorium.tests.conftest import extero_packet, intero_packet, proprio_packet

_ROOT = Path(__file__).resolve().parents[4]
_PROFILE_PATH = _ROOT / "config" / "profiles" / "c0_sensorium.profile.yaml"


def _pipeline() -> SensoriumPipeline:
    profile = load_c0_sensorium_profile(_PROFILE_PATH)
    return SensoriumPipeline(profile, bind_calibration(_PROFILE_PATH, profile.calibration_version))


def _run_stream(pipeline: SensoriumPipeline, cycles: int) -> list[str]:
    digests: list[str] = []
    for delivery in range(cycles):
        out = pipeline.process_cycle(delivery, [
            extero_packet(max(0, delivery - 1)),      # extero 延迟 1（Q-G00-08）
            intero_packet(delivery),
            proprio_packet(delivery),
        ])
        digests.extend(frame.content_digest for frame in out.frames)
    return digests


def test_profile_loader_fail_closed(tmp_path: Path) -> None:
    profile = load_c0_sensorium_profile(_PROFILE_PATH)
    assert profile.w_align_cycles == 4                     # Q-L02-03
    assert len(profile.intero_sensations) == 4             # Q-L02-05
    assert profile.calibration_version == "c0-static-v1"   # Q-G00-12②
    assert profile.gain_form == "identity_1.0"             # Q-G00-12③
    bad = tmp_path / "bad.profile.yaml"
    bad.write_text(
        "profile: {id: c0_sensorium, version: v1.0}\nsensorium:\n"
        "  modalities: [{id: EXT_LOCAL_OBS, exteroceptive: true}]\n"
        "  alignment: {w_align_cycles: 4, late_revision_lookback_windows: 1}\n"
        "  calibration: {version_id: c0-static-v1}\n  gain: {c0_form: identity_1.0}\n"
        "  determinism: {rng_operators: none_c0}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="C0 gate requires"):
        load_c0_sensorium_profile(bad)                     # <2 外感受 + <1 内感受 → 拒


def test_frame_stream_bit_exact_replay() -> None:
    a = _run_stream(_pipeline(), cycles=8)
    b = _run_stream(_pipeline(), cycles=8)
    assert a == b                                          # bit-exact（C0 退出判据）
    assert len(a) > 0


def test_different_input_diverges() -> None:
    pipeline = _pipeline()
    base = _run_stream(_pipeline(), cycles=8)
    p2 = _pipeline()
    digests: list[str] = []
    for delivery in range(8):
        window = [[0.9] * 5 for _ in range(5)] if delivery == 3 else None
        out = p2.process_cycle(delivery, [
            extero_packet(max(0, delivery - 1), window),
            intero_packet(delivery),
            proprio_packet(delivery),
        ])
        digests.extend(frame.content_digest for frame in out.frames)
    assert digests != base                                 # 输入分歧 → 帧分歧（非恒等伪装）


def test_energy_rate_derived_diff() -> None:
    """energy_rate = 派生差分（Q-L02-05）；首帧 = typed Unknown（窗关闭滞后 W=4）。"""
    pipeline = _pipeline()
    intero_frames = []
    for delivery in range(8):
        energy = 0.8 if delivery < 3 else 0.6
        out = pipeline.process_cycle(delivery, [intero_packet(delivery, energy=energy)])
        intero_frames.extend(f for f in out.frames if f.modality.value == "INTERO")
    by_time = {f.effective_time: f for f in intero_frames}
    first, later = by_time[0].features, by_time[3].features
    assert first.energy_rate.__class__.__name__ == "Unknown"      # 首帧无前值
    assert abs(later.energy_rate - (-0.2)) < 1e-9                 # 0.6 − 0.8
