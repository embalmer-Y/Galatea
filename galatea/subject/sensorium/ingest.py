"""RECEIVED 包校验（L02 §4.2 ingest 面 / §10 ingest.py）。

唯一合法入口：只接受 representation_level=RECEIVED 的 CognitivePacket + 已解码 payload；
content_type 必须是 C0 模态的声明载体（Q-G00-12①：excluded_carriers 拒绝——
action_outcome 归 L10 归属域）；缺字段/层级不符/匿名来源 → SchemaViolation（禁空帧）。

模态归属帧不归属信号：interoceptive 载体同时承载水平面（INTERO）与事件观测面
（EXT_EVENT，Q-G00-12①）——同一包可喂两个形成面（分派在 pipeline）。
"""
import json
from dataclasses import dataclass
from typing import Any, cast

from galatea.kernel.packet import CognitivePacket, RepresentationLevel
from galatea.subject.sensorium.ports import C0SensoriumProfile, SchemaViolation

CARRIER_EXTERO = "channel.exteroceptive.received.v1"
CARRIER_INTERO = "channel.interoceptive.received.v1"
CARRIER_PROPRIO = "channel.proprioceptive.received.v1"
CARRIER_LANGUAGE = "channel.language.received.v1"   # C4 扩展（c4_action_social sensorium_c4）

_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    CARRIER_EXTERO: ("kind", "window"),
    CARRIER_INTERO: ("kind", "energy", "integrity", "events"),
    CARRIER_PROPRIO: ("kind", "orientation"),
    CARRIER_LANGUAGE: ("kind", "text", "requester", "level"),
}

_REQUIRED_KIND: dict[str, str] = {
    CARRIER_EXTERO: "observation_window",
    CARRIER_INTERO: "interoceptive_state",
    CARRIER_PROPRIO: "proprioceptive_state",
    CARRIER_LANGUAGE: "typed_statement",
}


@dataclass(frozen=True, slots=True)
class IngestedSignal:
    """校验后的接收信号视图（只读；形成算子的唯一输入形态，模态归属形成面）。"""

    packet: CognitivePacket
    payload: dict[str, Any]
    carrier: str
    delivery_basis: int   # 冻结通道延迟（REV-0012 R2：cycle_id = 投递时；世界时 = 投递时 − 延迟）

    @property
    def effective_time(self) -> int:
        """世界时（L01 §4.5：世界时/接收时严格分离）= cycle_id − 冻结通道延迟。

        真实总线语义：包 cycle_id = 投递时（deliver_at）——extero 渲染于 t 被标记 t+1。
        延迟补偿用冻结 m0_mw0 channel_delay_cycles（Q-G00-08），由装配层传入。
        """
        return self.packet.cycle_id - self.delivery_basis

    @property
    def source_received_ids(self) -> tuple[str, ...]:
        return (self.packet.event_id,)


def ingest(
    packet: CognitivePacket, payload_text: str, profile: C0SensoriumProfile,
    time_basis: dict[str, int],
) -> IngestedSignal:
    """入口校验：层级/载体/字段逐项 fail-closed；返回只读信号视图。"""
    if packet.representation_level is not RepresentationLevel.RECEIVED:
        raise SchemaViolation(
            f"packet {packet.event_id}: representation_level must be RECEIVED,"
            f" got {packet.representation_level}（L02 §2.1 唯一合法入口）"
        )
    if not packet.event_id:
        raise SchemaViolation("anonymous packet rejected（禁匿名来源）")
    try:
        payload = cast(dict[str, Any], json.loads(payload_text))
    except json.JSONDecodeError as exc:
        raise SchemaViolation(f"packet {packet.event_id}: payload not decodable（损坏包不形成）") from exc
    carrier = packet.content_type
    # 排除面（Q-G00-12①）：载体串或载荷 kind 命中 excluded_carriers → 拒（action_outcome 归 L10）
    kind = str(payload.get("kind", ""))
    if any(c == carrier or c == kind for c in profile.excluded_carriers):
        raise SchemaViolation(
            f"carrier {carrier!r} (kind={kind!r}) excluded at C0"
            f"（Q-G00-12①：excluded_carriers={profile.excluded_carriers}）"
        )
    if carrier not in _REQUIRED_FIELDS:
        raise SchemaViolation(f"unknown carrier: {carrier!r}（C0 模态集外，Q-G00-12①）")
    if kind != _REQUIRED_KIND[carrier]:
        raise SchemaViolation(
            f"packet {packet.event_id}: payload kind {kind!r} does not match carrier {carrier!r}"
            "（schema 面：telemetry/异构载荷禁注入）"
        )
    missing = [f for f in _REQUIRED_FIELDS[carrier] if f not in payload]
    if missing:
        raise SchemaViolation(f"packet {packet.event_id}: payload missing fields {missing}")
    return IngestedSignal(
        packet=packet, payload=payload, carrier=carrier,
        delivery_basis=time_basis.get(carrier, 0),
    )
