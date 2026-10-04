"""Sensorium 测试共用装置：真实 schema 的 RECEIVED 包构造（L01 通道载荷同构）。"""
import json
from pathlib import Path
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


def time_basis() -> dict[str, int]:
    """冻结通道延迟表（真实总线语义：包 cycle_id = 投递时；REV-0012 R2）。

    来源 = 冻结 m0_mw0.profile channel_delay_cycles（Q-G00-08）——测试与生产同源，
    禁测试自造常量。
    """
    import yaml

    root = Path(__file__).resolve().parents[4]
    m0 = yaml.safe_load(
        (root / "config" / "profiles" / "m0_mw0.profile.yaml").read_text(encoding="utf-8")
    )
    delays = m0["channels"]["delay_cycles"]
    return {
        CARRIER_EXTERO: int(delays["exteroceptive"]),
        CARRIER_INTERO: int(delays["interoceptive"]),
        CARRIER_PROPRIO: int(delays["proprioceptive"]),
    }


def run_full_stream(pipeline: Any, cycles: int) -> list[Any]:
    """全载体流（总线忠实语义，REV-0012 R2）：extero 渲染于 t 在 t+1 投递
    （cycle_id = 投递时）；intero/proprio 零延迟。窗关闭语义 W_align=4（Q-L02-03）。
    """
    outputs = []
    for delivery in range(cycles):
        packets = [intero_packet(delivery), proprio_packet(delivery)]
        if delivery >= 1:
            packets.append(extero_packet(delivery))   # 渲染于 delivery−1，cycle_id=投递时
        outputs.append(pipeline.process_cycle(delivery, packets))
    return outputs
