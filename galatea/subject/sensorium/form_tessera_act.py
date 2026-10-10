"""Tessera 执行器状态形成算子（Q-L01-12②，P2；form_tessera_act.py）。

ReceivedSignal(tessera_act_state) → SensoryFrame(modality=PROPRIO——自身执行器状态
= 本体感受，Q-L01-12②)。纯确定性、无 RNG；同一载荷 → 同帧 digest。**忠实变换面**
（dev/value_u 原样承载——板侧标度不做主体侧换算，零新阈值）。原始遥测只入桥证据侧
log。不入 pred_error/知觉融合（audio/language 同位形）。增益：分类面缩放豁免。
"""
from galatea.subject.sensorium.ingest import CARRIER_TESSERA_ACT, IngestedSignal
from galatea.subject.sensorium.ports import (
    GainState,
    QualityMetrics,
    SensoryFrame,
    SensoryModality,
    TesseraActFeatures,
)

__all__ = ["form_tessera_act"]


def form_tessera_act(
    signal: IngestedSignal, formed_time: int, calibration_version: str, gain: GainState,
    *, revision_of: str | None = None,
) -> SensoryFrame:
    """执行器状态帧形成（载荷合同 = Q-L01-12② dev/value_u）。"""
    if signal.carrier != CARRIER_TESSERA_ACT:
        raise ValueError("form_tessera_act requires tessera act carrier")
    payload = signal.payload
    dev = int(payload["dev"])
    value_u = int(payload["value_u"])
    features = TesseraActFeatures(dev=dev, value_u=value_u)
    quality = QualityMetrics(completeness=1.0, corruption_flags=())   # 全字段齐备
    return SensoryFrame(
        frame_id=f"sf.PROPRIO.tact.{signal.effective_time}.{signal.packet.event_id}",
        modality=SensoryModality.PROPRIO,            # 自身执行器状态 = 本体感受
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
