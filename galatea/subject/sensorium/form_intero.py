"""内感受形成（L02 §1/§4.2/§10 form_intero.py；Q-L02-05：C0 四 sensation 零新阈值）。

energy_level/integrity_level（连续 [0,1]）+ damage_event/energy_depleted（离散，
世界侧已离散化——Q-L01-08 Δ≥0.05 / Q-L01-09⑤ 首次触 0 锁存，本档只做事件面转写）；
energy_rate = 派生差分（首帧 = typed Unknown，非独立 sensation）。
"""
from galatea.kernel.unknown import Unknown
from galatea.subject.sensorium.ingest import CARRIER_INTERO, IngestedSignal
from galatea.subject.sensorium.ports import (
    GainState,
    InteroSensations,
    SensoryFrame,
    SensoryModality,
)
from galatea.subject.sensorium.quality import ood_if_out_of_unit, quality_for
from galatea.subject.sensorium.unknowns import insufficient_observation


def form_intero(
    signal: IngestedSignal, formed_time: int, calibration_version: str, gain: GainState,
    prev_energy_level: float | None, revision_of: str | None = None, revision_index: int = 0,
) -> tuple[SensoryFrame, tuple[Unknown, ...], float]:
    """内感受帧：四 sensation + 派生 rate；返回 (帧, 本帧 unknowns, 供下帧差分的 energy_level)。

    prev_energy_level=None（首帧/断档后）→ rate = typed Unknown(INSUFFICIENT_OBSERVATION)。
    """
    if signal.carrier != CARRIER_INTERO:
        raise ValueError("form_intero requires interoceptive carrier")
    energy = float(signal.payload["energy"])
    integrity = float(signal.payload["integrity"])
    events = {str(e) for e in signal.payload["events"]}   # type: ignore[arg-type]
    unknowns: list[Unknown] = []
    unknowns.extend(ood_if_out_of_unit(energy, signal.source_received_ids, formed_time))
    unknowns.extend(ood_if_out_of_unit(integrity, signal.source_received_ids, formed_time))
    if prev_energy_level is None:
        rate: float | Unknown = insufficient_observation(
            signal.source_received_ids,
            "energy_rate unavailable: no prior interoceptive frame（派生差分无前值）",
            formed_time,
        )
    else:
        rate = round(energy - prev_energy_level, 6)
    sensations = InteroSensations(
        energy_level=energy,
        integrity_level=integrity,
        damage_event="integrity_damage_event" in events,
        energy_depleted="energy_depleted" in events,
        energy_rate=rate,
    )
    quality = quality_for(
        present_fields=4, expected_fields=4, corruption_flags=()
    )
    frame = SensoryFrame(
        frame_id=f"sf.INTERO.{signal.effective_time}" + (f".r{revision_index}" if revision_index else ""),
        revision_of=revision_of,
        modality=SensoryModality.INTERO,
        source_received_ids=signal.source_received_ids,
        effective_time=signal.effective_time,
        formed_time=formed_time,
        alignment_offset=formed_time - signal.effective_time,
        alignment_confidence=1.0,
        calibration_version=calibration_version,
        features=sensations,
        quality=quality,
        gain=gain,
        uncertainty=tuple(unknowns),
    )
    return frame, tuple(unknowns), energy
