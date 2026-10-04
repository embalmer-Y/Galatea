"""外感受形成算子（L02 §4.2/§10 form_extero.py；MW0：局部观测窗 + 事件观测面）。

纯确定性、无 RNG（Q-G00-12④）；同一 (profile, 载荷) → 同帧 digest。
EXT_LOCAL_OBS ← observation_window；EXT_EVENT ← interoceptive_state 载荷的
events 观测面（同载体两形成面，Q-G00-12①——仅在有事件时产帧，空事件无信号）。
"""
from galatea.kernel.unknown import Unknown
from galatea.subject.sensorium.ingest import CARRIER_EXTERO, CARRIER_INTERO, IngestedSignal
from galatea.subject.sensorium.ports import (
    ExtEventFeatures,
    ExtLocalObsFeatures,
    GainState,
    QualityMetrics,
    SensoryFrame,
    SensoryModality,
)
from galatea.subject.sensorium.quality import quality_for
from galatea.subject.sensorium.unknowns import calibration_uncertain


def _frame(
    frame_id: str, modality: SensoryModality, signal: IngestedSignal, formed_time: int,
    features: ExtLocalObsFeatures | ExtEventFeatures, quality: QualityMetrics, gain: GainState,
    calibration_version: str, revision_of: str | None,
) -> SensoryFrame:
    offset = formed_time - signal.effective_time
    confidence: float | Unknown = 1.0
    if offset >= 4:   # 迟到 revision：窗龄超 W_align → 置信降级 = typed Unknown（零新参数，Q-L02-03）
        confidence = calibration_uncertain(
            signal.source_received_ids,
            f"late revision frame: delivery−effective = {offset}（窗龄超 W_align）",
            signal.effective_time,
        )
    return SensoryFrame(
        frame_id=frame_id,
        modality=modality,
        source_received_ids=signal.source_received_ids,
        effective_time=signal.effective_time,
        formed_time=formed_time,
        alignment_offset=offset,
        alignment_confidence=confidence,
        calibration_version=calibration_version,
        features=features,
        quality=quality,
        gain=gain,
        revision_of=revision_of,
    )


def _frame_id(modality: SensoryModality, effective_time: int, revision_index: int) -> str:
    """确定性帧 id（revision 索引由 pipeline 按槽内已发布帧数派生，禁进程随机化）。"""
    base = f"sf.{modality.value}.{effective_time}"
    return base if revision_index == 0 else f"{base}.r{revision_index}"


def form_ext_local_obs(
    signal: IngestedSignal, formed_time: int, calibration_version: str, gain: GainState,
    revision_of: str | None = None, revision_index: int = 0,
) -> SensoryFrame:
    """局部观测窗形成：5×5 窗原值特征化（归一化恒等——渲染已带界，特征不推断）。"""
    if signal.carrier != CARRIER_EXTERO:
        raise ValueError("form_ext_local_obs requires exteroceptive carrier")
    window = tuple(
        tuple(float(v) for v in row) for row in signal.payload["window"]   # type: ignore[arg-type]
    )
    quality = quality_for(present_fields=len(window) * len(window[0]), expected_fields=25,
                          corruption_flags=())
    return _frame(
        _frame_id(SensoryModality.EXT_LOCAL_OBS, signal.effective_time, revision_index),
        SensoryModality.EXT_LOCAL_OBS, signal, formed_time,
        ExtLocalObsFeatures(window=window), quality, gain, calibration_version, revision_of,
    )


def form_ext_event(
    signal: IngestedSignal, formed_time: int, calibration_version: str, gain: GainState,
    revision_of: str | None = None, revision_index: int = 0,
) -> SensoryFrame | None:
    """事件观测面形成：事件种类清单（sorted 确定性）；空事件 = 无信号 → 不产帧（非丢弃）。"""
    if signal.carrier != CARRIER_INTERO:
        raise ValueError("form_ext_event requires interoceptive carrier")
    events = tuple(sorted(str(e) for e in signal.payload["events"]))   # type: ignore[arg-type]
    if not events:
        return None
    quality = quality_for(present_fields=len(events), expected_fields=len(events), corruption_flags=())
    return _frame(
        _frame_id(SensoryModality.EXT_EVENT, signal.effective_time, revision_index),
        SensoryModality.EXT_EVENT, signal, formed_time,
        ExtEventFeatures(events=events), quality, gain, calibration_version, revision_of,
    )
