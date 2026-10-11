"""brain 测试装置（subject 平面内自足——手构形成帧，零 env/证据平面依赖）。"""
from __future__ import annotations

from typing import Any

from galatea.subject.sensorium.ports import (
    ExtEventFeatures,
    ExtLocalObsFeatures,
    GainState,
    InteroSensations,
    ProprioFeatures,
    QualityMetrics,
    SensoryFrame,
    SensoryModality,
)


def uniform_window(center_value: float) -> tuple[tuple[float, ...], ...]:
    """5×5 窗，中心格取值（行优先展平第 12 位 = 中心）。"""
    return tuple(
        tuple(center_value if (r == 2 and c == 2) else 0.0 for c in range(5))
        for r in range(5)
    )


def make_frame(modality: SensoryModality, features: Any, effective_time: int) -> SensoryFrame:
    """最小合法感觉帧（digest 构造期自算；层级恒 SENSORY_FORMED）。"""
    return SensoryFrame(
        frame_id=f"test-{modality.value}-{effective_time}",
        modality=modality,
        source_received_ids=("test-received-1",),
        effective_time=effective_time,
        formed_time=effective_time,
        alignment_offset=0,
        alignment_confidence=1.0,
        calibration_version="c0-static-v1",
        features=features,
        quality=QualityMetrics(completeness=1.0, corruption_flags=()),
        gain=GainState(applied_factor=1.0, source="PROFILE"),
        uncertainty=(),
    )


def window_frame(t: int, center_value: float = 0.5) -> SensoryFrame:
    return make_frame(SensoryModality.EXT_LOCAL_OBS,
                      ExtLocalObsFeatures(window=uniform_window(center_value)), t)


def event_frame(t: int, events: tuple[str, ...]) -> SensoryFrame:
    return make_frame(SensoryModality.EXT_EVENT, ExtEventFeatures(events=events), t)


def intero_frame(t: int, energy: float = 0.8) -> SensoryFrame:
    return make_frame(SensoryModality.INTERO,
                      InteroSensations(energy_level=energy, integrity_level=1.0,
                                       damage_event=False, energy_depleted=False,
                                       energy_rate=0.0), t)


def proprio_frame(t: int, orientation: str = "N") -> SensoryFrame:
    return make_frame(SensoryModality.PROPRIO, ProprioFeatures(orientation=orientation), t)


def base_frames(t: int, energy: float = 0.8, center: float = 0.5,
                orientation: str = "N") -> list[SensoryFrame]:
    """基三模态帧组（window/intero/proprio——误差流必配）。"""
    return [window_frame(t, center), intero_frame(t, energy), proprio_frame(t, orientation)]
