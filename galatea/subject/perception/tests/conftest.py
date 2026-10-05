"""C1 知觉测试共用装置（真实通道载荷 schema 同构，REV-0012 R2 语义延续）。

窗载荷约定 = 冻结渲染器序：window[r][c] ↔ egocentric (dx=c−2, dy=r−2)，
N=(0,+1)。延迟表 = 冻结 m0_mw0 profile channel_delay_cycles（测试与生产同源）。
"""
import json
from pathlib import Path
from typing import Any, cast

from galatea.kernel.digest import content_digest
from galatea.kernel.packet import AccessScope, ArtifactRef, CognitivePacket, Provenance, RepresentationLevel
from galatea.subject.sensorium.calibration import bind_calibration
from galatea.subject.sensorium.ingest import CARRIER_EXTERO, CARRIER_INTERO, CARRIER_PROPRIO
from galatea.subject.sensorium.pipeline import SensoriumPipeline
from galatea.subject.sensorium.ports import C0SensoriumProfile, load_c0_sensorium_profile

REPO_ROOT = Path(__file__).resolve().parents[4]


def time_basis() -> dict[str, int]:
    """冻结通道延迟表（REV-0012 R2：测试与生产同源，禁自造常量）。"""
    delays = cast_profile()["channels"]["delay_cycles"]
    return {
        CARRIER_EXTERO: int(delays["exteroceptive"]),
        CARRIER_INTERO: int(delays["interoceptive"]),
        CARRIER_PROPRIO: int(delays["proprioceptive"]),
    }


def cast_profile() -> dict[str, Any]:
    import yaml

    return cast(
        dict[str, Any],
        yaml.safe_load((REPO_ROOT / "config" / "profiles" / "m0_mw0.profile.yaml").read_text(encoding="utf-8")),
    )


def make_sensorium() -> SensoriumPipeline:
    profile: C0SensoriumProfile = load_c0_sensorium_profile()
    calibration = bind_calibration(
        REPO_ROOT / "config" / "profiles" / "c0_sensorium.profile.yaml", profile.calibration_version
    )
    return SensoriumPipeline(profile, calibration, time_basis())


def make_packet(
    carrier: str, cycle: int, payload: dict[str, Any], event_id: str | None = None
) -> tuple[CognitivePacket, str]:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    packet = CognitivePacket(
        event_id=event_id or f"evt.{carrier}.{cycle}", subject_candidate_id="S", run_id="R",
        branch_id="B", activity_window_id="w", cycle_id=cycle, virtual_time=cycle,
        source_module=f"env.channel.{carrier}", content_type=carrier,
        representation_level=RepresentationLevel.RECEIVED, schema_version="v1",
        payload_ref=ArtifactRef(digest=content_digest(text), kind="payload"),
        confidence=1.0, provenance=Provenance(), causal_parent_ids=(),
        access_scope=AccessScope.MODULE_LOCAL, content_digest=content_digest(text),
    )
    return packet, text


def window_payload(window: list[list[float]]) -> tuple[CognitivePacket, str]:
    return make_packet(CARRIER_EXTERO, 0, {"kind": "observation_window", "window": window})


def intero_payload(
    cycle: int, energy: float = 0.8, integrity: float = 1.0, events: list[str] | None = None
) -> tuple[CognitivePacket, str]:
    return make_packet(CARRIER_INTERO, cycle, {
        "kind": "interoceptive_state", "energy": energy, "integrity": integrity,
        "events": events or [],
    })


def proprio_payload(cycle: int, orientation: str = "N") -> tuple[CognitivePacket, str]:
    return make_packet(CARRIER_PROPRIO, cycle, {"kind": "proprioceptive_state", "orientation": orientation})


def uniform_window(center_value: float, ring_value: float = 0.0) -> list[list[float]]:
    """5×5 窗：中心 = center_value，其余 = ring_value（含噪声确定性面）。"""
    return [
        [center_value if (r == 2 and c == 2) else ring_value for c in range(5)]
        for r in range(5)
    ]


def frames_at(
    window: list[list[float]], t: int, energy: float = 0.8, events: list[str] | None = None,
    orientation: str = "N",
) -> tuple[Any, ...]:
    """投递 cycles 0..t+4（extero 每拍渲染同窗）→ 取 effective_time=t 的关闭帧组。

    总线忠实语义（REV-0012 R2）：intero/proprio 零延迟（effective = delivery），
    extero 延迟 1（delivery ≥ 1 → effective = delivery − 1）；窗 t 于 delivery
    t+4 关闭原子发布（W_align=4，Q-L02-03）。
    """
    from galatea.subject.sensorium.pipeline import CycleOutput

    sensorium = make_sensorium()
    collected: dict[int, list[Any]] = {}
    for delivery in range(t + 5):
        packets: list[tuple[CognitivePacket, str]] = [
            intero_payload(delivery, energy=energy, events=events),
            proprio_payload(delivery, orientation=orientation),
        ]
        if delivery >= 1:
            packets.append(make_packet(
                CARRIER_EXTERO, delivery, {"kind": "observation_window", "window": window}
            ))
        out: CycleOutput = sensorium.process_cycle(delivery, packets)
        for frame in out.frames:
            collected.setdefault(frame.effective_time, []).append(frame)
    return tuple(collected.get(t, ()))


def frames_for_window(
    sensorium: SensoriumPipeline, window: list[list[float]], delivery: int,
    energy: float = 0.8, events: list[str] | None = None,
) -> dict[int, list[Any]]:
    """单拍投递（低层用法：按 effective_time 收帧，含未关闭窗）。"""
    packets = [
        intero_payload(delivery, energy=energy, events=events),
        proprio_payload(delivery),
        make_packet(CARRIER_EXTERO, delivery, {"kind": "observation_window", "window": window}),
    ]
    out = sensorium.process_cycle(delivery, packets)
    by_t: dict[int, list[Any]] = {}
    for frame in out.frames:
        by_t.setdefault(frame.effective_time, []).append(frame)
    return by_t
