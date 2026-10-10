"""Tessera zenoh 桥（P2 单元 E 地面层；Q-L10-16 设备事件：S3 节点经活路由可达）。

映射（语义有据）：
- `*/sys/power`（budget_ma/used_ma/peak_ma）→ **INTERO** 载体：设备电源预算 = 体资源（内感受）
- `*/dbled|dbpwm/telemetry`（执行器状态 dev/value_u）→ **PROPRIO** 载体：自身执行器状态 = 本体感受
- （摄像头帧面预留 EXTERO——D-AV 采集通道待桥接扩展）

载荷 = CBOR（ver/kind/…，实测解码在案）；原始 zenoh 字节只入证据侧 log
（payload digest 承载），主体只见合同包。zenoh 依赖**惰性导入**（Galatea 核心
不要求 zenoh——仅桥连接面需要，WSL/主机侧安装）。

主题空间（Tessera keyspace 实测）：`tessera/<node>/<cube>/<suffix>`。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from galatea.kernel.digest import content_digest
from galatea.kernel.packet import (
    AccessScope,
    ArtifactRef,
    CognitivePacket,
    Provenance,
    RepresentationLevel,
)

CARRIER_AUDIO_CONTENT_TYPE = "channel.audio.received.v1"
CARRIER_INTERO_CONTENT_TYPE = "channel.interoceptive.received.v1"
CARRIER_PROPRIO_CONTENT_TYPE = "channel.proprioceptive.received.v1"
CARRIER_TESSERA_ACT_CONTENT_TYPE = "channel.tessera_act.received.v1"   # Q-L01-12②（P2 专用载体）

_POWER_SCHEMA = "physio.tessera_power.v1"
_ACT_SCHEMA = "physio.tessera_act.v1"


def parse_topic(key: str) -> tuple[str, str, str] | None:
    """`tessera/<node>/<cube>/<suffix>` → (node, cube, suffix)；非 tessera 空间返回 None。"""
    parts = key.split("/")
    if len(parts) < 4 or parts[0] != "tessera":
        return None
    return parts[1], parts[2], "/".join(parts[3:])


def decode_cbor(payload: bytes) -> dict[str, Any]:
    """CBOR 解码（惰性导入 cbor2——桥部署面依赖；Galatea 核心不要求）。"""
    import cbor2  # 部署面惰性依赖（非包依赖；WSL/主机桥安装）

    return dict(cbor2.loads(payload))      # cbor2.loads(dict) 键为 str（实测 CBOR 文本键）


def map_suffix_to_carrier(suffix: str) -> tuple[str, str] | None:
    """suffix → (carrier content_type, schema)；未映射 suffix 返回 None（禁猜）。"""
    if suffix == "sys/power":
        return CARRIER_INTERO_CONTENT_TYPE, _POWER_SCHEMA
    if suffix.endswith("led/telemetry") or suffix.endswith("pwm/telemetry"):
        return CARRIER_TESSERA_ACT_CONTENT_TYPE, _ACT_SCHEMA
    return None


def power_to_intero_payload(cbor_obj: dict[str, Any]) -> dict[str, object]:
    """power → 既有 interoceptive_state 合同（Q-L01-12① 忠实映射）：
    energy = 1 − used/max(budget,1)（电源余量比——设备电源即体能量资源）；
    原始 mA 值只入桥证据侧 log（DeliveryFact 分离）。"""
    budget = max(1.0, float(cbor_obj.get("budget_ma", 0)))
    used = max(0.0, float(cbor_obj.get("used_ma", 0)))
    energy = round(max(0.0, 1.0 - used / budget), 6)
    return {"kind": "interoceptive_state", "energy": energy, "integrity": 1.0, "events": []}


def build_packet(key: str, cbor_obj: dict[str, Any], cycle: int) -> tuple[CognitivePacket, str, str, str]:
    """ zenoh 样本 → (RECEIVED 合同包, carrier, schema, payload_text)。未映射 suffix → ValueError。"""
    parsed = parse_topic(key)
    if parsed is None:
        raise ValueError(f"not a tessera key: {key!r}")
    node, cube, suffix = parsed
    mapped = map_suffix_to_carrier(suffix)
    if mapped is None:
        raise ValueError(f"unmapped suffix: {suffix!r}（禁猜——映射表显式扩展才收）")
    carrier, schema = mapped
    if carrier == CARRIER_INTERO_CONTENT_TYPE:
        payload = power_to_intero_payload(cbor_obj)        # 忠实映射（Q-L01-12①）
    else:
        kind_name = schema.split(".")[-2] + "_state"
        payload = {"kind": kind_name, "node": node, "cube": cube,
                   **{k: v for k, v in cbor_obj.items() if k != "kind"}}
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = content_digest(text)
    packet = CognitivePacket(
        event_id=f"evt.tessera.{node}.{cycle}.{suffix.replace('/', '_')}",
        subject_candidate_id="S", run_id="R", branch_id="B",
        activity_window_id="tessera", cycle_id=cycle, virtual_time=cycle,
        source_module=f"env.tessera_bridge.{node}", content_type=carrier,
        representation_level=RepresentationLevel.RECEIVED, schema_version="v1",
        payload_ref=ArtifactRef(digest=digest, kind="payload"), confidence=1.0,
        provenance=Provenance(), causal_parent_ids=(), access_scope=AccessScope.MODULE_LOCAL,
        content_digest=digest,
    )
    return packet, carrier, schema, text


@dataclass(frozen=True, slots=True)
class BridgeSample:
    key: str
    carrier: str
    schema: str
    payload_text: str
    payload_digest: str
    raw_digest: str               # 原始 zenoh 字节 digest（证据侧绑定）
    packet: CognitivePacket       # RECEIVED 合同包（常驻融合面直接消费）


def sample_from_wire(key: str, raw: bytes, cycle: int) -> BridgeSample:
    """原始 zenoh 样本 → 桥样本（解码 + 映射 + 合同包；异常向上抛——禁静默丢样本）。"""
    obj = decode_cbor(raw)
    packet, carrier, schema, text = build_packet(key, obj, cycle)
    return BridgeSample(
        key=key, carrier=carrier, schema=schema, payload_text=text,
        payload_digest=packet.content_digest, raw_digest=content_digest(raw.hex()),
        packet=packet,
    )
