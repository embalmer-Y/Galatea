"""音频形成面测试（Q-L02-08；含默认关 bit-exact 保持锚）。"""
from pathlib import Path

import pytest

from galatea.env.physio.audio import (
    features_from_pcm,
    features_payload,
    packet_for_audio,
)
from galatea.subject.sensorium.form_audio import form_audio
from galatea.subject.sensorium.ingest import CARRIER_AUDIO, ingest
from galatea.subject.sensorium.pipeline import SensoriumPipeline
from galatea.subject.sensorium.ports import SensoryModality, load_c0_sensorium_profile
from galatea.subject.sensorium.tests.conftest import intero_packet, time_basis

_ROOT = Path(__file__).resolve().parents[4]
_PROFILE_PATH = _ROOT / "config" / "profiles" / "c0_sensorium.profile.yaml"
_REF_RMS = 5000.0


def _pcm_sine(hz: float, ms: int, rate: int = 16000, amplitude: int = 12000) -> bytes:
    import math
    n = int(rate * ms / 1000)
    return b"".join(
        int(amplitude * math.sin(2 * math.pi * hz * i / rate)).to_bytes(2, "little", signed=True)
        for i in range(n)
    )


def _audio_signal(pcm: bytes, cycle: int):
    feats = features_from_pcm(pcm, 16000)
    _payload, text = features_payload(feats)
    packet, text = packet_for_audio(text, cycle, "env.physio.audio_bridge")
    return ingest(packet, text, load_c0_sensorium_profile(_PROFILE_PATH), {CARRIER_AUDIO: 0})


def test_form_audio_faithful_transform_and_determinism() -> None:
    signal = _audio_signal(_pcm_sine(660.0, 100), 5)
    from galatea.subject.sensorium.ports import GainState
    frame1 = form_audio(signal, 5, "cal-v1", GainState(applied_factor=1.0, source="PROFILE"), _REF_RMS)
    frame2 = form_audio(signal, 5, "cal-v1", GainState(applied_factor=1.0, source="PROFILE"), _REF_RMS)
    assert frame1.features.loudness == frame2.features.loudness       # 同载荷同帧（确定性）
    feats = frame1.features
    assert 0.0 < feats.loudness <= 1.0                                # 忠实变换（ref=5000）
    assert feats.duration_ms == 100
    assert frame1.modality is SensoryModality.EXT_LOCAL_OBS           # 听觉归外感受观察面
    assert frame1.alignment_offset == 0                               # delay=0（本机桥）


def test_form_audio_rejects_wrong_carrier() -> None:
    from galatea.kernel.packet import (
        AccessScope, ArtifactRef, CognitivePacket, Provenance, RepresentationLevel,
    )
    from galatea.kernel.digest import content_digest
    from galatea.subject.sensorium.ingest import CARRIER_INTERO
    from galatea.subject.sensorium.ingest import IngestedSignal
    from galatea.subject.sensorium.ports import GainState

    pkt = CognitivePacket(
        event_id="evt.x", subject_candidate_id="S", run_id="R", branch_id="B",
        activity_window_id="w", cycle_id=1, virtual_time=1,
        source_module="x", content_type=CARRIER_INTERO,
        representation_level=RepresentationLevel.RECEIVED, schema_version="v1",
        payload_ref=ArtifactRef(digest=content_digest("{}"), kind="payload"),
        confidence=1.0, provenance=Provenance(), causal_parent_ids=(),
        access_scope=AccessScope.MODULE_LOCAL, content_digest=content_digest("{}"),
    )
    signal = IngestedSignal(packet=pkt, payload={"kind": "x"}, carrier=CARRIER_INTERO,
                            delivery_basis=0)
    with pytest.raises(ValueError, match="audio carrier"):
        form_audio(signal, 1, "cal-v1", GainState(applied_factor=1.0, source="PROFILE"), _REF_RMS)


def test_audio_enabled_off_by_default_bit_exact() -> None:
    """默认关：同一 intero 流在 audio_enabled=False（默认）下与历史行为 bit-exact。"""
    profile = load_c0_sensorium_profile(_PROFILE_PATH)
    p1 = SensoriumPipeline(profile, bind_calibration(), time_basis())
    p2 = SensoriumPipeline(profile, bind_calibration(), time_basis(), audio_enabled=False)
    digests1, digests2 = [], []
    for cycle in range(6):
        pkt, text = intero_packet(cycle)
        out1 = p1.process_cycle(cycle, [(pkt, text)])
        out2 = p2.process_cycle(cycle, [(pkt, text)])
        digests1 += [r.digest for r in out1.formation_receipts]
        digests2 += [r.digest for r in out2.formation_receipts]
    assert digests1 == digests2 and digests1                          # 非空且逐位一致


def test_audio_enabled_requires_ref() -> None:
    profile = load_c0_sensorium_profile(_PROFILE_PATH)
    with pytest.raises(ValueError, match="audio_ref_rms"):
        SensoriumPipeline(profile, bind_calibration(), time_basis(), audio_enabled=True)


def bind_calibration():
    from galatea.subject.sensorium.calibration import bind_calibration as _bind
    return _bind(_PROFILE_PATH, load_c0_sensorium_profile(_PROFILE_PATH).calibration_version)


def test_audio_frame_flows_through_pipeline_when_enabled() -> None:
    """音频包 → ingest → 对齐窗 → 形成面：loudness 感觉出现且饱和（12000/5000 → 1.0）。"""
    profile = load_c0_sensorium_profile(_PROFILE_PATH)
    pipeline = SensoriumPipeline(profile, bind_calibration(), time_basis(),
                                audio_enabled=True, audio_ref_rms=_REF_RMS)
    loud_text = features_payload(features_from_pcm(_pcm_sine(660.0, 100), 16000))[1]
    all_frames = []
    for cycle in range(6):
        pkt, text = packet_for_audio(loud_text, cycle, "env.physio.audio_bridge")
        intero_pkt, intero_text = intero_packet(cycle)
        out = pipeline.process_cycle(cycle, [(pkt, text), (intero_pkt, intero_text)])
        all_frames += [f for f in out.frames
                       if getattr(f.features, "loudness", None) is not None]
    assert all_frames, "audio frames never formed across 6 cycles"
    assert all(f.features.loudness == 1.0 for f in all_frames)     # 饱和（min(1, 12000/5000)）
    assert all(f.modality is SensoryModality.EXT_LOCAL_OBS for f in all_frames)
