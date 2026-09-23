"""CognitivePacket envelope（L00 §2.3；schema L00.packet.v1；Q-T03 CONFIRMED：frozen slots dataclass）。

纪律：envelope 提交后不可变（frozen）；修正以新事件引用旧事件（revision）；
匿名来源拒绝；confidence 必须有界 float 或 typed Unknown；content_digest 在
构造时对除自身外全部字段计算，verify_integrity 可复核。
"""
import enum
from collections.abc import Callable
from dataclasses import dataclass, fields
from typing import Any, cast

from galatea.kernel.digest import UnknownTag, content_digest
from galatea.kernel.rng import CounterStream
from galatea.kernel.unknown import Unknown, ensure_typed_confidence

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # Crockford base32（ULID）


class RepresentationLevel(enum.StrEnum):
    """认识链表示层级（L00 §2.3）：任何路径不得提升。"""

    RECEIVED = "RECEIVED"
    SENSORY_FORMED = "SENSORY_FORMED"
    PERCEIVED = "PERCEIVED"
    PREDICTED = "PREDICTED"
    IMAGINED = "IMAGINED"
    RECALLED = "RECALLED"
    EXTERNAL_STATEMENT = "EXTERNAL_STATEMENT"


class AccessScope(enum.StrEnum):
    """访问域（L00 §2.3 冻结三项；扩展 = schema 版本升级）。"""

    PUBLIC_BROADCAST = "PUBLIC_BROADCAST"
    MODULE_LOCAL = "MODULE_LOCAL"
    EVIDENCE_ONLY = "EVIDENCE_ONLY"


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """registry 内容寻址引用（digest 即身份）。"""

    digest: str
    kind: str


@dataclass(frozen=True, slots=True)
class Provenance:
    """来源链：源事件、通道、校准版本、增益回执。"""

    source_events: tuple[str, ...] = ()
    channel_ref: str | None = None
    calibration_version: str | None = None
    gain_receipt: str | None = None


@dataclass(frozen=True, slots=True)
class CognitivePacket:
    event_id: str
    subject_candidate_id: str
    run_id: str
    branch_id: str
    activity_window_id: str
    cycle_id: int
    virtual_time: int
    source_module: str
    content_type: str
    representation_level: RepresentationLevel
    schema_version: str
    payload_ref: ArtifactRef
    confidence: "float | Unknown"
    provenance: Provenance
    causal_parent_ids: tuple[str, ...]
    access_scope: AccessScope
    content_digest: str


class EnvelopeViolation(ValueError):
    """envelope 合同违规（匿名来源/未类型化置信/字段缺失）。"""


def _require_non_empty_str(name: str, value: object) -> None:
    if not isinstance(value, str) or not value:
        raise EnvelopeViolation(f"{name}: non-empty str required, got {value!r}")


def _serialize_confidence(value: "float | Unknown") -> Any:
    if isinstance(value, Unknown):
        return {
            UnknownTag: {
                "reason": str(value.reason.value),
                "evidence_refs": list(value.evidence_refs),
                "detail": value.detail,
                "detected_by": value.detected_by,
                "virtual_time": value.virtual_time,
            }
        }
    return value


def packet_fields(packet: CognitivePacket) -> dict[str, Any]:
    """envelope 的 canonical 字典（不含 content_digest；digest 计算与复核共用）。"""
    out: dict[str, Any] = {}
    for f in fields(packet):
        name = f.name
        if name == "content_digest":
            continue
        raw: Any = getattr(packet, name)
        value: Any
        if isinstance(raw, enum.StrEnum):
            value = raw.value
        elif isinstance(raw, Unknown):
            value = _serialize_confidence(raw)
        elif isinstance(raw, Provenance):
            value = {
                "source_events": list(raw.source_events),
                "channel_ref": raw.channel_ref,
                "calibration_version": raw.calibration_version,
                "gain_receipt": raw.gain_receipt,
            }
        elif isinstance(raw, ArtifactRef):
            value = {"digest": raw.digest, "kind": raw.kind}
        elif isinstance(raw, tuple):
            value = list(cast("tuple[Any, ...]", raw))
        else:
            value = raw
        out[name] = value
    return out


def verify_integrity(packet: CognitivePacket) -> bool:
    """复核 content_digest 与字段一致（不一致 = 完整性破坏，调用方 fail closed）。"""
    return content_digest(packet_fields(packet)) == packet.content_digest


def make_packet(
    *,
    event_id: str,
    subject_candidate_id: str,
    run_id: str,
    branch_id: str,
    activity_window_id: str,
    cycle_id: int,
    virtual_time: int,
    source_module: str,
    content_type: str,
    representation_level: RepresentationLevel,
    schema_version: str,
    payload_ref: ArtifactRef,
    confidence: "float | Unknown",
    provenance: Provenance = Provenance(),
    causal_parent_ids: tuple[str, ...] = (),
    access_scope: AccessScope,
) -> CognitivePacket:
    """冻结构造：校验合同 → 计算 content_digest → 返回不可变 envelope。"""
    str_fields: tuple[tuple[str, object], ...] = (
        ("event_id", event_id),
        ("subject_candidate_id", subject_candidate_id),
        ("run_id", run_id),
        ("branch_id", branch_id),
        ("activity_window_id", activity_window_id),
        ("source_module", source_module),
        ("content_type", content_type),
        ("schema_version", schema_version),
    )
    for name, value in str_fields:
        _require_non_empty_str(name, value)
    checked = ensure_typed_confidence(confidence, "confidence")
    packet = CognitivePacket(
        event_id=event_id,
        subject_candidate_id=subject_candidate_id,
        run_id=run_id,
        branch_id=branch_id,
        activity_window_id=activity_window_id,
        cycle_id=cycle_id,
        virtual_time=virtual_time,
        source_module=source_module,
        content_type=content_type,
        representation_level=representation_level,
        schema_version=schema_version,
        payload_ref=payload_ref,
        confidence=checked,
        provenance=provenance,
        causal_parent_ids=tuple(causal_parent_ids),
        access_scope=access_scope,
        content_digest="",
    )
    digest = content_digest(packet_fields(packet))
    return CognitivePacket(
        event_id=packet.event_id,
        subject_candidate_id=packet.subject_candidate_id,
        run_id=packet.run_id,
        branch_id=packet.branch_id,
        activity_window_id=packet.activity_window_id,
        cycle_id=packet.cycle_id,
        virtual_time=packet.virtual_time,
        source_module=packet.source_module,
        content_type=packet.content_type,
        representation_level=packet.representation_level,
        schema_version=packet.schema_version,
        payload_ref=packet.payload_ref,
        confidence=packet.confidence,
        provenance=packet.provenance,
        causal_parent_ids=packet.causal_parent_ids,
        access_scope=packet.access_scope,
        content_digest=digest,
    )


def revise(packet: CognitivePacket, event_id: str, **changes: Any) -> CognitivePacket:
    """修正语义：新事件（新 id）引用旧事件，禁改写历史（L00 §2.3 纪律）。"""
    _require_non_empty_str("event_id", event_id)
    if event_id == packet.event_id:
        raise EnvelopeViolation("revision event_id must differ from the revised event")
    allowed = {f.name for f in fields(packet)} - {"event_id", "content_digest"}
    unknown_keys = set(changes) - allowed
    if unknown_keys:
        raise EnvelopeViolation(f"cannot revise fields: {sorted(unknown_keys)}")
    kwargs: dict[str, Any] = {name: changes.get(name, getattr(packet, name)) for name in allowed}
    kwargs["event_id"] = event_id
    kwargs["causal_parent_ids"] = tuple(kwargs["causal_parent_ids"]) + (packet.event_id,)
    return make_packet(**kwargs)  # type: ignore[arg-type]


class UlidFactory:
    """确定性 ULID 工厂：48-bit 时间部（虚拟时间）+ 80-bit 随机部（RNG 流）。

    确定性纪律：随机部来自显式 CounterStream——同 (seed, 流位置) 产生同 id，
    重放可复现；单调可排序由 (time, random) 字典序保证。
    """

    def __init__(self, stream: CounterStream, time_source: Callable[[], int]) -> None:
        self._stream = stream
        self._time_source = time_source

    def new(self) -> str:
        time_part = self._time_source() & ((1 << 48) - 1)
        rand_part = self._stream.next_uint64() & ((1 << 80) - 1)
        value: int = (time_part << 80) | rand_part
        chars: list[str] = []
        for shift in range(125, -5, -5):
            chars.append(_ALPHABET[(value >> shift) & 0x1F])
        return "".join(chars)
