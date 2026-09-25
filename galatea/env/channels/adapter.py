"""五类声明通道合同（L01 §2——通道外无边界）与接收侧 payload schema。

F0 范围 = schema 合同：通道名/content_type 常量 + ReceivedSignalPayload
（Q-T03：payload = Pydantic v2）+ 统一注册入口；render→transport 行为归 M0。
ReceivedSignalPacket 本体 = L00 CognitivePacket（representation_level=RECEIVED），
其 payload schema 在此登记——"接收"与"真值"（galatea.env.world.truth）分属不同类型。
"""
from collections.abc import Callable
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from galatea.kernel.packet import ArtifactRef
from galatea.kernel.payload import PayloadSchemaRegistry


class ChannelKind(StrEnum):
    """五类声明通道（L01 §2.2：通道外无边界，禁第六类）。"""

    EXTEROCEPTIVE = "exteroceptive"
    INTEROCEPTIVE = "interoceptive"
    PROPRIOCEPTIVE = "proprioceptive"
    OUTCOME = "outcome"
    LANGUAGE = "language"


CHANNEL_CONTENT_TYPES: dict[ChannelKind, str] = {
    kind: f"channel.{kind.value}.received.v1" for kind in ChannelKind
}


class ReceivedSignalPayload(BaseModel):
    """RECEIVED 包的 payload（Q-T03 Pydantic v2；frozen）。

    不含真值坐标/精确量（防 oracle 泄漏，L01 §4.2）；缺失经 missing + signal_ref
    缺省表达，不补零。
    """

    model_config = ConfigDict(frozen=True)

    modality: str
    channel_version: str
    signal_ref: ArtifactRef | None
    missing: bool = False


def register_channel_payload_schemas(registry: PayloadSchemaRegistry) -> None:
    """把五通道 payload schema 登记进内核 schema 注册表（幂等：重复注册拒绝）。"""
    for kind, content_type in CHANNEL_CONTENT_TYPES.items():
        registry.register(
            content_type,
            "v1",
            _validator_for(kind),
        )


def _validator_for(kind: ChannelKind) -> Callable[[bytes], None]:
    """返回该校验 payload 字节的 callable。"""

    def validate(payload: bytes) -> None:
        ReceivedSignalPayload.model_validate_json(payload)

    validate.__name__ = f"validate_{kind.value}_received"
    return validate


# ==========================================================================
# 行为层（M0）：render → transport(延迟/损坏/丢失) → RECEIVED 包 + DeliveryFact 分离
# ==========================================================================
from dataclasses import dataclass  # noqa: E402

from galatea.env.channels.delivery import ChannelDeliveryFact, MissingSignalEvent  # noqa: E402
from galatea.env.interventions.registry import InterventionRegistry  # noqa: E402
from galatea.env.profile import MW0Params  # noqa: E402
from galatea.kernel.packet import (  # noqa: E402
    AccessScope,
    CognitivePacket,
    Provenance,
    RepresentationLevel,
    UlidFactory,
    make_packet,
)
from galatea.kernel.registry import Registry  # noqa: E402
from galatea.kernel.rng import RngDirectory  # noqa: E402
from galatea.kernel.unknown import Unknown, UnknownReason  # noqa: E402

CHANNEL_VERSION = "v1"


@dataclass(frozen=True, slots=True)
class Transmission:
    """发送侧产物（render 完成，等待延迟到期投递）。"""

    channel: ChannelKind
    payload_ref: ArtifactRef
    truth_ref: ArtifactRef
    sent_at: int
    deliver_at: int


@dataclass(frozen=True, slots=True)
class ChannelDelivery:
    """单 cycle 投递结果：主体侧 RECEIVED 包与证据侧投递事实严格分离（L01 §4.2）。"""

    cycle: int
    packets: tuple[CognitivePacket, ...] = ()
    facts: tuple[ChannelDeliveryFact, ...] = ()
    missing: tuple[MissingSignalEvent, ...] = ()


class ChannelBus:
    """五通道总线。

    纪律：
    - 投递事实（发了什么/何时/是否损坏/是否送达）只入 facts（EVIDENCE_ONLY）；
      主体只拿 RECEIVED 包——"投递 ≠ 接收"的机械承载；
    - fault 干预在投递时刻生效：丢弃载荷 → MissingSignalEvent + fact(delivered=False)；
    - 损坏 = 载荷字节级扰动后另行入库（主体拿到坏数据，schema 校验自会拒绝），
      fact.corrupted=True 只在证据侧；丢失率 0.0（Q-L01-09⑦），丢失仅经 fault；
    - RNG 全部来自 L00 派生流（Q-T11）：transport/ulid 按通道分流。
    """

    def __init__(
        self,
        params: MW0Params,
        registry: Registry,
        rng_directory: RngDirectory,
        branch_id: str,
        interventions: InterventionRegistry,
        *,
        run_id: str = "R",
        subject_candidate_id: str = "S",
        corruption_override: float | None = None,
    ) -> None:
        self.params = params
        self._registry = registry
        self._interventions = interventions
        self._run_id = run_id
        self._branch = branch_id
        self._subject = subject_candidate_id
        self._corruption_rate = params.channel_corruption_rate if corruption_override is None else corruption_override
        self._buffers: dict[ChannelKind, list[Transmission]] = {kind: [] for kind in ChannelKind}
        self._transport_rng = {
            kind: rng_directory.stream(branch_id, f"channel.{kind.value}", "transport") for kind in ChannelKind
        }
        self._ulid_rng = {
            kind: rng_directory.stream(branch_id, f"channel.{kind.value}", "ulid") for kind in ChannelKind
        }
        self._render_rng = rng_directory.stream(branch_id, "env", "render")

    @property
    def render_stream(self):
        """观测噪声流（world.render_window 消费；(env,mw0,render)，Q-L01-01）。"""
        return self._render_rng

    def submit(
        self,
        channel: ChannelKind,
        signal_bytes: bytes,
        truth_ref: ArtifactRef,
        cycle: int,
    ) -> ArtifactRef:
        """render 完成 → 入库 → 按通道延迟排入投递缓冲。"""
        delay = self.params.channel_delay_cycles[channel.value]
        payload_ref = self._registry.put(signal_bytes, "payload")
        self._buffers[channel].append(
            Transmission(channel=channel, payload_ref=payload_ref, truth_ref=truth_ref, sent_at=cycle, deliver_at=cycle + delay)
        )
        return payload_ref

    def _fault_active(self, channel: ChannelKind, cycle: int) -> bool:
        return any(r.kind == "fault" for r in self._interventions.active_at(cycle))

    def _make_packet(self, transmission: Transmission, payload_ref: ArtifactRef) -> CognitivePacket:
        ulid = UlidFactory(self._ulid_rng[transmission.channel], lambda: transmission.deliver_at)
        return make_packet(
            event_id=ulid.new(),
            subject_candidate_id=self._subject,
            run_id=self._run_id,
            branch_id=self._branch,
            activity_window_id=f"ch.{transmission.channel.value}",
            cycle_id=transmission.deliver_at,
            virtual_time=transmission.deliver_at,
            source_module=f"env.channel.{transmission.channel.value}",
            content_type=CHANNEL_CONTENT_TYPES[transmission.channel],
            representation_level=RepresentationLevel.RECEIVED,
            schema_version=CHANNEL_VERSION,
            payload_ref=payload_ref,
            confidence=1.0,
            provenance=Provenance(channel_ref=f"channel.{transmission.channel.value}@{CHANNEL_VERSION}"),
            causal_parent_ids=(),
            access_scope=AccessScope.MODULE_LOCAL,  # L01 §2.1：channel.received → 仅 L02
        )

    def deliver(self, cycle: int) -> ChannelDelivery:
        """投递全部到期传输：fault 丢弃、损坏扰动、其余按 RECEIVED 包交付。"""
        packets: list[CognitivePacket] = []
        facts: list[ChannelDeliveryFact] = []
        missing: list[MissingSignalEvent] = []
        for kind, buffer in self._buffers.items():
            due = [t for t in buffer if t.deliver_at <= cycle]
            if not due:
                continue
            self._buffers[kind] = [t for t in buffer if t.deliver_at > cycle]
            for transmission in due:
                fact = ChannelDeliveryFact(
                    sent_truth_ref=transmission.truth_ref,
                    delivered=False,
                    delay_cycles=transmission.deliver_at - transmission.sent_at,
                    corrupted=False,
                    channel_version=CHANNEL_VERSION,
                )
                if self._fault_active(kind, cycle):
                    unknown = Unknown(
                        reason=UnknownReason.MISSING_SIGNAL,
                        evidence_refs=(),
                        detail=f"fault intervention on {kind.value}",
                        detected_by=f"env.channel.{kind.value}",
                        virtual_time=cycle,
                    )
                    missing.append(MissingSignalEvent(channel_version=CHANNEL_VERSION, expected_truth_ref=transmission.truth_ref, unknown=unknown))
                    facts.append(fact)
                    continue
                payload_ref = transmission.payload_ref
                corrupted = self._transport_rng[kind].next_float01() < self._corruption_rate
                if corrupted:
                    entry = self._registry.get(transmission.payload_ref)
                    garbled = bytes(b ^ 0x5A for b in entry.blob[:8]) + entry.blob[8:]
                    payload_ref = self._registry.put(garbled, "payload")
                facts.append(
                    ChannelDeliveryFact(
                        sent_truth_ref=transmission.truth_ref,
                        delivered=True,
                        delay_cycles=transmission.deliver_at - transmission.sent_at,
                        corrupted=corrupted,
                        channel_version=CHANNEL_VERSION,
                    )
                )
                packets.append(self._make_packet(transmission, payload_ref))
        return ChannelDelivery(cycle=cycle, packets=tuple(packets), facts=tuple(facts), missing=tuple(missing))

    def pending(self) -> int:
        return sum(len(b) for b in self._buffers.values())
