"""音频感觉形成算子（Q-L02-08，P2；form_audio.py）。

ReceivedSignal(audio_frame) → SensoryFrame(modality=EXTERO——听觉即外感受，Q-L01-11)。
纯确定性、无 RNG；同一载荷 → 同帧 digest。**忠实变换面**（零新阈值纪律）：
loudness = min(1, rms / audio_ref_rms)——audio_ref_rms 为任意先钉冻结常数
（p1 profile v1.2 audio 节，同 period_ms 体例），不设"什么算声音"的感觉阈。
原始 PCM 永不进帧（只入桥证据侧 log，DeliveryFact 分离）。
音频帧**不入知觉融合**（同 LANGUAGE 帧：perception 管线无音频消费点——结构面）
且**不入 pred_error**（Q-L02-06③ 同位形）。增益面：分类面缩放豁免（恒等增益透传）。
"""
from galatea.subject.sensorium.ingest import CARRIER_AUDIO, IngestedSignal
from galatea.subject.sensorium.ports import (
    AudioFeatures,
    GainState,
    QualityMetrics,
    SensoryFrame,
    SensoryModality,
)

__all__ = ["form_audio"]


def form_audio(
    signal: IngestedSignal, formed_time: int, calibration_version: str, gain: GainState,
    audio_ref_rms: float, *, revision_of: str | None = None,
) -> SensoryFrame:
    """音频帧形成（载荷合同 = Q-L01-11 `physio.audio_frame.v1` 五字段）。"""
    if signal.carrier != CARRIER_AUDIO:
        raise ValueError("form_audio requires audio carrier")
    payload = signal.payload
    rms = float(payload["rms"])
    zcr = float(payload["zcr"])
    peak = int(payload["peak"])
    duration_ms = int(payload["duration_ms"])
    if duration_ms <= 0:
        raise ValueError("audio frame duration_ms must be positive（空帧禁形成）")
    loudness = min(1.0, rms / audio_ref_rms)
    features = AudioFeatures(
        loudness=loudness, rms=rms, zcr=zcr, peak=peak, duration_ms=duration_ms,
    )
    quality = QualityMetrics(completeness=1.0, corruption_flags=())   # 五字段齐全
    return SensoryFrame(
        frame_id=f"sf.EXTERO.audio.{signal.effective_time}.{signal.packet.event_id}",
        modality=SensoryModality.EXT_LOCAL_OBS,      # 听觉归外感受观察面（Q-L01-11；枚举无裸 EXTERO 成员）
        source_received_ids=signal.source_received_ids,
        effective_time=signal.effective_time,
        formed_time=formed_time,
        alignment_offset=formed_time - signal.effective_time,
        alignment_confidence=1.0,
        calibration_version=calibration_version,
        features=features,
        quality=quality,
        gain=gain,
        revision_of=revision_of,
    )
