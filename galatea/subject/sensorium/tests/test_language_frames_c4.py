"""LANGUAGE 模态帧形成（L02 §9 C4 + L12 §4.3；form_language.py C4 新增面）。

判据：机会型形成（语言缺席 = 正常静默，不产 MISSING_SIGNAL）；level 永不提升；
同一载荷同帧 digest（纯确定性）；默认装配（language_enabled=False）行为与
C0–C3 冻结路径一致（语言信号不入形成面）。
"""
from pathlib import Path

import pytest

from galatea.subject.sensorium.calibration import bind_calibration
from galatea.subject.sensorium.form_language import form_language
from galatea.subject.sensorium.ingest import CARRIER_LANGUAGE, ingest
from galatea.subject.sensorium.pipeline import SensoriumPipeline
from galatea.subject.sensorium.ports import GainState, load_c0_sensorium_profile
from galatea.subject.sensorium.tests.conftest import (
    extero_packet, intero_packet, make_packet, proprio_packet, time_basis,
)

_ROOT = Path(__file__).resolve().parents[4]
_PROFILE_PATH = _ROOT / "config" / "profiles" / "c0_sensorium.profile.yaml"
_IDENTITY_GAIN = GainState(applied_factor=1.0, source="PROFILE")


def _pipeline(*, language_enabled: bool) -> SensoriumPipeline:
    profile = load_c0_sensorium_profile(_PROFILE_PATH)
    return SensoriumPipeline(
        profile, bind_calibration(_PROFILE_PATH, profile.calibration_version), time_basis(),
        language_enabled=language_enabled,
    )


def _language_packet(cycle: int, text: str = "there is food to the north"):
    payload = {"kind": "typed_statement", "text": text, "requester": "experiment_control",
               "level": "EXTERNAL_STATEMENT"}
    return make_packet(CARRIER_LANGUAGE, cycle, payload, event_id=f"evt.lang.{cycle}")


def _run(pipeline: SensoriumPipeline, *, with_language: bool) -> list:
    frames = []
    for delivery in range(6):
        packets = [intero_packet(delivery), proprio_packet(delivery)]
        if delivery >= 1:
            packets.append(extero_packet(delivery))
        if with_language and delivery == 1:
            packets.append(_language_packet(1))
        out = pipeline.process_cycle(delivery, packets)
        frames.extend(out.frames)
    return frames


def test_language_frame_forms_when_enabled() -> None:
    frames = _run(_pipeline(language_enabled=True), with_language=True)
    lang_frames = [f for f in frames if f.modality.value == "LANGUAGE"]
    assert len(lang_frames) == 1
    frame = lang_frames[0]
    assert frame.features.statement_text == "there is food to the north"
    assert frame.features.statement_level == "EXTERNAL_STATEMENT"   # 层级永不提升
    assert frame.features.requester == "experiment_control"


def test_language_absence_is_silence_not_missing_signal() -> None:
    """机会型形成：语言缺席 = 正常静默——不产 MISSING_SIGNAL（稀疏通道语义）。"""
    pipeline = _pipeline(language_enabled=True)
    unknowns = []
    for delivery in range(6):
        packets = [intero_packet(delivery), proprio_packet(delivery)]
        if delivery >= 1:
            packets.append(extero_packet(delivery))
        out = pipeline.process_cycle(delivery, packets)
        unknowns.extend(u for u in out.unknowns if "language" in str(u.evidence_refs).lower())
    assert unknowns == []


def test_language_frame_deterministic() -> None:
    """同一载荷 → 同帧 digest（纯确定性、无 RNG——两次独立装配全链恒等）。"""
    frames_a = _run(_pipeline(language_enabled=True), with_language=True)
    frames_b = _run(_pipeline(language_enabled=True), with_language=True)
    assert [f.content_digest for f in frames_a] == [f.content_digest for f in frames_b]


def test_language_packet_ignored_when_disabled() -> None:
    """默认装配（C0–C3 冻结路径）：语言信号不入形成面（行为不变）。"""
    frames = _run(_pipeline(language_enabled=False), with_language=True)
    assert all(f.modality.value != "LANGUAGE" for f in frames)


def test_language_payload_non_statement_level_rejected() -> None:
    """level 非 EXTERNAL_STATEMENT 即拒（层级永不提升——L12 §4.1）。"""
    profile = load_c0_sensorium_profile(_PROFILE_PATH)
    payload = {"kind": "typed_statement", "text": "x", "requester": "r", "level": "PERCEIVED"}
    packet, text = make_packet(CARRIER_LANGUAGE, 1, payload)
    signal = ingest(packet, text, profile, {**time_basis(), CARRIER_LANGUAGE: 0})
    with pytest.raises(ValueError, match="EXTERNAL_STATEMENT"):
        form_language(signal, 1, "c0-static-v1", _IDENTITY_GAIN)
