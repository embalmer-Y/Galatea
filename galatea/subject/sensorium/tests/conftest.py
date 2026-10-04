"""Sensorium 测试共用装置：真实 schema 的 RECEIVED 包构造（L01 通道载荷同构）。"""
import json
from typing import Any

from galatea.kernel.digest import content_digest
from galatea.kernel.packet import AccessScope, ArtifactRef, CognitivePacket, Provenance, RepresentationLevel
from galatea.subject.sensorium.ingest import (
    CARRIER_EXTERO,
    CARRIER_INTERO,
    CARRIER_PROPRIO,
)


def make_packet(
    carrier: str, cycle: int, payload: dict[str, Any], event_id: str | None = None,
    level: RepresentationLevel = RepresentationLevel.RECEIVED,
) -> tuple[CognitivePacket, str]:
    """构造 (CognitivePacket, payload_text)——载荷 schema 与 env 通道渲染器逐字段同构。"""
    event_id = event_id or f"evt.{carrier}.{cycle}"
    payload_text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    packet = CognitivePacket(
        event_id=event_id, subject_candidate_id="S", run_id="R", branch_id="B",
        activity_window_id="w", cycle_id=cycle, virtual_time=cycle,
        source_module=f"env.channel.{carrier}", content_type=carrier,
        representation_level=level, schema_version="v1",
        payload_ref=ArtifactRef(digest=content_digest(payload_text), kind="payload"),
        confidence=1.0, provenance=Provenance(), causal_parent_ids=(),
        access_scope=AccessScope.MODULE_LOCAL,
        content_digest=content_digest(payload_text),
    )
    return packet, payload_text


def extero_packet(cycle: int, window: list[list[float]] | None = None) -> tuple[CognitivePacket, str]:
    payload = {"kind": "observation_window", "window": window or [[0.1] * 5 for _ in range(5)]}
    return make_packet(CARRIER_EXTERO, cycle, payload)


def intero_packet(
    cycle: int, energy: float = 0.8, integrity: float = 1.0, events: list[str] | None = None,
) -> tuple[CognitivePacket, str]:
    payload = {"kind": "interoceptive_state", "energy": energy, "integrity": integrity,
               "events": events or []}
    return make_packet(CARRIER_INTERO, cycle, payload)


def proprio_packet(cycle: int, orientation: str = "N") -> tuple[CognitivePacket, str]:
    payload = {"kind": "proprioceptive_state", "orientation": orientation}
    return make_packet(CARRIER_PROPRIO, cycle, payload)


def outcome_packet(cycle: int) -> tuple[CognitivePacket, str]:
    """被排除载体（Q-G00-12①：action_outcome 不入 sensorium）。"""
    return make_packet("channel.outcome.received.v1", cycle, {"kind": "action_outcome"})


def run_full_stream(pipeline: Any, cycles: int) -> list[Any]:
    """全载体流（extero 延迟 1，Q-G00-08）：返回逐 cycle CycleOutput 列表。

    W_align=4 → effective_time=t 的帧在 delivery=t+4 发布（窗关闭语义，Q-L02-03）。
    """
    outputs = []
    for delivery in range(cycles):
        outputs.append(pipeline.process_cycle(delivery, [
            extero_packet(max(0, delivery - 1)),
            intero_packet(delivery),
            proprio_packet(delivery),
        ]))
    return outputs
