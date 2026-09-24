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
