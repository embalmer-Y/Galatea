"""AudioBridge/AudioActuator 特征与封套测试（P04 合规：env 侧测试住 env 包）。"""
import math

import pytest

from galatea.env.physio.audio import features_from_pcm, features_payload
from galatea.env.physio.ports import load_p1_physio_profile

_PROFILE = load_p1_physio_profile()


def _pcm_sine(hz: float, ms: int, rate: int = 16000, amplitude: int = 12000) -> bytes:
    n = int(rate * ms / 1000)
    return b"".join(
        int(amplitude * math.sin(2 * math.pi * hz * i / rate)).to_bytes(2, "little", signed=True)
        for i in range(n)
    )


def test_features_deterministic_and_faithful() -> None:
    pcm = _pcm_sine(440.0, 100)
    f1 = features_from_pcm(pcm, 16000)
    f2 = features_from_pcm(pcm, 16000)
    assert (f1.rms, f1.zcr, f1.peak, f1.duration_ms) == (f2.rms, f2.zcr, f2.peak, f2.duration_ms)
    assert f1.peak <= 12000 and f1.duration_ms == 100
    payload, text = features_payload(f1)
    assert sorted(payload) == ["duration_ms", "kind", "peak", "rms", "zcr"]   # 合同五字段
    assert '"kind":"audio_frame"' in text


def test_empty_pcm_rejected() -> None:
    with pytest.raises(ValueError, match="empty"):
        features_from_pcm(b"", 16000)
