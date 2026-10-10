"""音频桥与执行器（P2 单元 A/B；Q-L01-11 / Q-L10-14）。

- AudioBridge：arecord 采集 → 定长帧（100ms @16kHz mono）→ 确定性帧特征
  （rms/zcr/peak）→ 合同 payload（`audio_frame` 五字段）+ RECEIVED 包；
  原始 PCM 只入证据侧 log（digest 承载，样本本体不进主体平面）。
- AudioActuator：L4-limited 有界播放（时长/幅值封套强制——越界即拒，
  containment_allowance 封套的机械承载）；aplay 后端（card 2）。

确定性：features_from_pcm 纯函数（同 PCM → 同特征）；零 RNG 零墙钟决策。
"""
from __future__ import annotations

import json
import math
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

from galatea.env.physio.ports import P1PhysioProfile
from galatea.kernel.digest import content_digest
from galatea.kernel.packet import (
    AccessScope,
    ArtifactRef,
    CognitivePacket,
    Provenance,
    RepresentationLevel,
)

CARRIER_AUDIO_CONTENT_TYPE = "channel.audio.received.v1"   # 与 ingest CARRIER_AUDIO 逐字同源
FRAME_MS = 100


@dataclass(frozen=True, slots=True)
class AudioFrameFeatures:
    """单帧特征（纯函数输出；16-bit signed mono PCM 域）。"""

    rms: float
    zcr: float
    peak: int
    duration_ms: int
    pcm_digest: str          # 原始样本 digest（证据侧绑定；样本本体不进主体平面）


def features_from_pcm(pcm: bytes, rate: int) -> AudioFrameFeatures:
    """确定性帧特征（Q-L01-11：桥侧忠实测量面）。"""
    n = len(pcm) // 2
    if n == 0:
        raise ValueError("empty pcm frame")
    total = 0
    peak = 0
    crossings = 0
    prev = 0
    for i in range(n):
        v = int.from_bytes(pcm[2 * i:2 * i + 2], "little", signed=True)
        total += v * v
        if abs(v) > abs(peak):
            peak = v
        if i > 0 and (v >= 0) != (prev >= 0):
            crossings += 1
        prev = v
    rms = math.sqrt(total / n)
    return AudioFrameFeatures(
        rms=round(rms, 3),
        zcr=round(crossings / max(1, n - 1), 6),
        peak=peak,
        duration_ms=round(n * 1000 / rate),
        pcm_digest=content_digest(pcm.hex()),
    )


def features_payload(features: AudioFrameFeatures) -> tuple[dict[str, object], str]:
    """特征 → 合同 payload（`audio_frame` 五字段 + kind 判别）与 payload_text。"""
    payload: dict[str, object] = {
        "kind": "audio_frame",
        "rms": features.rms,
        "zcr": features.zcr,
        "peak": features.peak,
        "duration_ms": features.duration_ms,
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return payload, text


def packet_for_audio(payload_text: str, cycle: int, source_module: str) -> tuple[CognitivePacket, str]:
    """合同包构造（RECEIVED；与 sensorium 测试装置逐字段同构）。"""
    digest = content_digest(payload_text)
    packet = CognitivePacket(
        event_id=f"evt.physio.audio.{cycle}", subject_candidate_id="S", run_id="R",
        branch_id="B", activity_window_id="physio", cycle_id=cycle, virtual_time=cycle,
        source_module=source_module, content_type=CARRIER_AUDIO_CONTENT_TYPE,
        representation_level=RepresentationLevel.RECEIVED, schema_version="v1",
        payload_ref=ArtifactRef(digest=digest, kind="payload"), confidence=1.0,
        provenance=Provenance(), causal_parent_ids=(), access_scope=AccessScope.MODULE_LOCAL,
        content_digest=digest,
    )
    return packet, payload_text


class AudioBridge:
    """麦克风帧流（arecord 后端；capture 命令面 fail-closed）。"""

    def __init__(self, profile: P1PhysioProfile, device: str = "plughw:2,0",
                 *, capture_seconds: float = 1.0) -> None:
        audio = profile.audio
        self._rate = int(audio["sample_rate"])
        self._frame_samples = int(self._rate * audio["frame_ms"] / 1000)
        self._device = device
        self._capture_seconds = capture_seconds

    def capture_frames(self, seconds: float | None = None) -> list[tuple[AudioFrameFeatures, dict[str, object], str]]:
        """采集 → 整帧切分 → 特征 + 合同 payload。返回 [(features, payload, payload_text)]。"""
        secs = seconds if seconds is not None else self._capture_seconds
        raw = subprocess.run(
            ["arecord", "-D", self._device, "-q", "-f", "S16_LE", "-r", str(self._rate),
             "-c", "1", "-d", str(int(secs)), "-t", "raw"],
            capture_output=True, timeout=int(secs) + 15)
        if raw.returncode != 0:
            raise RuntimeError(f"arecord failed rc={raw.returncode}: {raw.stderr[:200]!r}")
        pcm = raw.stdout
        out: list[tuple[AudioFrameFeatures, dict[str, object], str]] = []
        frame_bytes = self._frame_samples * 2
        for off in range(0, len(pcm) - frame_bytes + 1, frame_bytes):
            feats = features_from_pcm(pcm[off:off + frame_bytes], self._rate)
            payload, text = features_payload(feats)
            out.append((feats, payload, text))
        return out


class AudioActuator:
    """扬声器有界播放（L4-limited；containment 封套机械强制）。"""

    def __init__(self, profile: P1PhysioProfile, device: str = "plughw:2,0",
                 volume_pct: int = 70) -> None:
        audio = profile.audio
        self._rate = int(audio["sample_rate"])
        self._max_seconds = float(audio["play_max_seconds"])
        self._max_amplitude = float(audio["play_max_amplitude"])
        self._device = device
        self._volume_pct = volume_pct

    def play_tone(self, hz: float, seconds: float, *, out_dir: Path) -> Path:
        """有界单频播放：时长/幅值越界即拒（L4 封套；返回 WAV 供回执 digest）。"""
        if seconds <= 0 or seconds > self._max_seconds:
            raise ValueError(f"play duration {seconds}s exceeds L4 bound {self._max_seconds}s")
        amplitude = min(0.6, self._max_amplitude)
        wav_path = out_dir / f"play_{int(hz)}hz_{int(seconds * 1000)}ms.wav"
        frames = bytearray()
        n = int(self._rate * seconds)
        for i in range(n):
            sample = int(amplitude * 32767.0 * math.sin(2.0 * math.pi * hz * i / self._rate))
            frames += int(sample).to_bytes(2, "little", signed=True)
        with wave.open(str(wav_path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self._rate)
            w.writeframes(bytes(frames))
        play = subprocess.run(["aplay", "-D", self._device, "-q", str(wav_path)],
                              capture_output=True, text=True, timeout=int(seconds) + 15)
        if play.returncode != 0:
            raise RuntimeError(f"aplay failed rc={play.returncode}: {play.stderr[:200]!r}")
        return wav_path
