"""本体感受形成（L02 §1/§4.2/§10 form_proprio.py；M0 最小集：朝向）。

位置不直接下发（主体由观测窗中心性隐式获得，Q-L01-09⑥）；load ≡ 0 无信号
（Q-L01-09⑥ 简化留痕）——C0 特征面 = orientation。
"""
from galatea.subject.sensorium.ingest import CARRIER_PROPRIO, IngestedSignal
from galatea.subject.sensorium.ports import (
    GainState,
    ProprioFeatures,
    SensoryFrame,
    SensoryModality,
)
from galatea.subject.sensorium.quality import quality_for


def form_proprio(
    signal: IngestedSignal, formed_time: int, calibration_version: str, gain: GainState,
    revision_of: str | None = None, revision_index: int = 0,
) -> SensoryFrame:
    if signal.carrier != CARRIER_PROPRIO:
        raise ValueError("form_proprio requires proprioceptive carrier")
    orientation = str(signal.payload["orientation"])
    quality = quality_for(present_fields=1, expected_fields=1, corruption_flags=())
    return SensoryFrame(
        frame_id=f"sf.PROPRIO.{signal.effective_time}" + (f".r{revision_index}" if revision_index else ""),
        modality=SensoryModality.PROPRIO,
        source_received_ids=signal.source_received_ids,
        effective_time=signal.effective_time,
        formed_time=formed_time,
        alignment_offset=formed_time - signal.effective_time,
        alignment_confidence=1.0,
        calibration_version=calibration_version,
        features=ProprioFeatures(orientation=orientation),
        quality=quality,
        gain=gain,
        revision_of=revision_of,
    )
