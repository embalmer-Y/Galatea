"""通道故障类型化 + 真值/投递 schema 合同（L01 §2/§4/§10；F0 schema 层）。"""
import dataclasses

import pytest

from galatea.env.channels.delivery import ChannelDeliveryFact, MissingSignalEvent
from galatea.env.channels.adapter import (
    CHANNEL_CONTENT_TYPES,
    ChannelKind,
    ReceivedSignalPayload,
    register_channel_payload_schemas,
)
from galatea.env.world.truth import BodyTruth, EffectDomain, EffectFact, Patch, WorldEvent, WorldState, WorldTruthEvent
from galatea.kernel.packet import AccessScope, ArtifactRef
from galatea.kernel.payload import PayloadSchemaRegistry, SchemaViolation
from galatea.kernel.unknown import Unknown, UnknownReason


def _ref() -> ArtifactRef:
    return ArtifactRef(digest="0" * 64, kind="world_state")


def test_world_truth_objects_are_evidence_only_and_frozen() -> None:
    event = WorldTruthEvent(tick=1, world_state_digest="d", state_ref=_ref(), causal_parents=())
    assert event.access_scope is AccessScope.EVIDENCE_ONLY
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.tick = 2  # type: ignore[misc]


def test_effect_fact_represents_requested_vs_effective_divergence() -> None:
    fact = EffectFact(
        action_window=(4, 5),
        requested_effect="forage",
        effective_effect="none",
        domain=EffectDomain.SIMULATED,
    )
    assert fact.requested_effect != fact.effective_effect  # 分歧显形（禁合并）
    assert fact.access_scope is AccessScope.EVIDENCE_ONLY


def test_world_state_carries_grid_body_events() -> None:
    state = WorldState(
        grid=((Patch(kind="resource", resource_level=3, respawn_timer=0),),),
        body=BodyTruth(pos=(0, 0), orientation="N", energy=1.0, integrity=1.0, load=0.0),
        events=(WorldEvent(kind="storm", pos=(2, 2), tick=1),),
    )
    assert state.events[0].kind == "storm"


def test_delivery_fact_is_evidence_only() -> None:
    fact = ChannelDeliveryFact(
        sent_truth_ref=_ref(), delivered=True, delay_cycles=1, corrupted=False, channel_version="v1"
    )
    assert fact.access_scope is AccessScope.EVIDENCE_ONLY


def test_missing_signal_requires_typed_unknown() -> None:
    good = Unknown(reason=UnknownReason.MISSING_SIGNAL, evidence_refs=(), detail=None, detected_by="env", virtual_time=1)
    event = MissingSignalEvent(channel_version="v1", expected_truth_ref=_ref(), unknown=good)
    assert event.unknown.reason is UnknownReason.MISSING_SIGNAL
    bad = Unknown(reason=UnknownReason.OOD, evidence_refs=(), detail=None, detected_by="env", virtual_time=1)
    with pytest.raises(ValueError):
        MissingSignalEvent(channel_version="v1", expected_truth_ref=_ref(), unknown=bad)


def test_five_channel_schemas_registered() -> None:
    assert len(CHANNEL_CONTENT_TYPES) == 5
    assert set(CHANNEL_CONTENT_TYPES) == set(ChannelKind)
    registry = PayloadSchemaRegistry()
    register_channel_payload_schemas(registry)
    assert set(registry.registered()) == set(CHANNEL_CONTENT_TYPES.values())
    with pytest.raises(SchemaViolation):
        register_channel_payload_schemas(registry)  # 重复注册拒绝


def test_received_signal_payload_schema() -> None:
    payload = ReceivedSignalPayload(
        modality="exteroceptive", channel_version="v1",
        signal_ref={"digest": "1" * 64, "kind": "signal"},
    )
    json_bytes = payload.model_dump_json().encode("utf-8")
    parsed = ReceivedSignalPayload.model_validate_json(json_bytes)
    assert parsed.modality == "exteroceptive"
    missing = ReceivedSignalPayload(modality="outcome", channel_version="v1", signal_ref=None, missing=True)
    assert missing.missing and missing.signal_ref is None  # 缺失不补零


# ==========================================================================
# 行为层（M0）：投递/延迟/fault/损坏/DeliveryFact 分离
# ==========================================================================
import json as _json
import tempfile
from pathlib import Path

from galatea.env.channels.adapter import ChannelBus
from galatea.env.channels.extero import ExteroceptiveChannel
from galatea.env.channels.intero import InteroceptiveChannel
from galatea.env.channels.language_stub import LanguageStubChannel
from galatea.env.channels.outcome import OutcomeChannel
from galatea.env.channels.proprio import ProprioceptiveChannel
from galatea.env.interventions.registry import InterventionRegistry
from galatea.env.profile import load_profile
from galatea.env.world.mw0 import MW0World
from galatea.kernel.clock import CycleClock
from galatea.kernel.packet import RepresentationLevel
from galatea.kernel.registry import Registry
from galatea.kernel.rng import RngDirectory, reference_block_blake2s
from galatea.kernel.state import Stores
from galatea.kernel.unknown import UnknownReason

_PROFILE = load_profile(Path(__file__).resolve().parents[2] / "config" / "profiles" / "m0_mw0.profile.yaml")


def _harness(corruption_override: float | None = None):
    tmp = Path(tempfile.mkdtemp())
    registry = Registry(tmp / "registry", Stores(tmp / "stores"), CycleClock())
    rng = RngDirectory(b"bus-seed", reference_block_blake2s)
    world = MW0World(_PROFILE.params, rng, branch_id="B")
    interventions = InterventionRegistry()
    bus = ChannelBus(
        _PROFILE.params, registry, rng, branch_id="B", interventions=interventions,
        corruption_override=corruption_override,
    )
    return bus, world, registry, interventions


def test_bus_delivers_with_delay_and_separates_fact_from_signal() -> None:
    bus, world, registry, _interventions = _harness()
    truth_ref = ArtifactRef(digest=world.state_digest(), kind="world_state_ref")
    ExteroceptiveChannel(bus, world).render_and_submit(cycle=5, truth_ref=truth_ref)
    early = bus.deliver(cycle=5)
    assert early.packets == () and early.facts == ()  # 延迟 1 cycle：当拍未到期
    delivery = bus.deliver(cycle=6)
    assert len(delivery.packets) == 1 and len(delivery.facts) == 1
    packet, fact = delivery.packets[0], delivery.facts[0]
    assert packet.representation_level is RepresentationLevel.RECEIVED
    assert fact.delivered and not fact.corrupted and fact.delay_cycles == 1
    assert fact.sent_truth_ref == truth_ref
    # 分离：RECEIVED 包 payload 不含投递事实/真值引用（投递 ≠ 接收）
    payload_blob = registry.get(packet.payload_ref).blob
    assert b"sent_truth" not in payload_blob
    assert b"world_state_ref" not in payload_blob
    assert bus.pending() == 0


def test_fault_drops_delivery_to_missing_signal() -> None:
    bus, world, _registry, interventions = _harness()
    interventions.register(record_id="iflt", kind="fault", registered_at_cycle=0, from_cycle=1, to_cycle=20)
    ExteroceptiveChannel(bus, world).render_and_submit(cycle=5, truth_ref=ArtifactRef(digest="d" * 64, kind="world_state_ref"))
    delivery = bus.deliver(cycle=6)
    assert delivery.packets == ()  # 载荷被丢弃
    assert len(delivery.missing) == 1
    assert delivery.missing[0].unknown.reason is UnknownReason.MISSING_SIGNAL
    assert delivery.facts[0].delivered is False


def test_corruption_perturbs_payload_and_records_fact() -> None:
    bus, world, registry, _interventions = _harness(corruption_override=1.0)  # 恒损坏（测试钩子）
    ExteroceptiveChannel(bus, world).render_and_submit(cycle=1, truth_ref=ArtifactRef(digest="e" * 64, kind="world_state_ref"))
    delivery = bus.deliver(cycle=2)
    assert delivery.facts[0].corrupted is True and delivery.facts[0].delivered is True
    garbled = registry.get(delivery.packets[0].payload_ref).blob
    try:
        ReceivedSignalPayload.model_validate_json(garbled)
        raised = False
    except Exception:
        raised = True
    assert raised  # 字节级扰动使坏数据在主体侧 schema 校验失败（L02 typed unknown 路径）


def test_all_five_channels_submit_and_deliver() -> None:
    bus, world, _registry, _interventions = _harness()
    truth_ref = ArtifactRef(digest=world.state_digest(), kind="world_state_ref")
    ExteroceptiveChannel(bus, world).render_and_submit(1, truth_ref)
    InteroceptiveChannel(bus, world).render_and_submit(1, truth_ref, events=())
    ProprioceptiveChannel(bus, world).render_and_submit(1, truth_ref)
    OutcomeChannel(bus).render_and_submit(1, truth_ref, command_id="c1", effect="move_n_to_0_1")
    LanguageStubChannel(bus).submit_typed_statement(1, truth_ref, text="please forage", requester="experiment_control")
    delivery = bus.deliver(cycle=2)  # 全通道延迟 ≤1
    assert len(delivery.packets) == 5
    assert {p.source_module for p in delivery.packets} == {
        "env.channel.exteroceptive", "env.channel.interoceptive",
        "env.channel.proprioceptive", "env.channel.outcome", "env.channel.language",
    }
    assert all(f.delivered for f in delivery.facts)
    assert bus.pending() == 0


def test_intero_reports_integrity_and_damage_event() -> None:
    bus, world, registry, _interventions = _harness()
    damage, eventful = world.storm_hit()
    assert eventful and damage > 0  # 初始 integrity 1.0，命中即 ≥ 阈值
    assert bus.deliver(cycle=0).packets == ()  # 无提交无投递
    truth_ref = ArtifactRef(digest=world.state_digest(), kind="world_state_ref")
    InteroceptiveChannel(bus, world).render_and_submit(1, truth_ref, events=())
    delivery = bus.deliver(cycle=1)  # interoceptive delay=0 → 当拍到期
    assert len(delivery.packets) == 1
    signal = _json.loads(registry.get(delivery.packets[0].payload_ref).blob)
    assert signal["integrity"] == 0.9  # 1.0 − 0.10（storm_damage_per_hit）
    assert signal["energy"] == 1.0
