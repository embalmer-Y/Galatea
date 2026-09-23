"""canonical JSON 稳定性与 envelope 合同（L00 §4.4/§2.3/§7）。"""
import dataclasses

import pytest
from hypothesis import given
from hypothesis import strategies as st

from galatea.kernel.digest import canonical_json, blob_digest, content_digest
from galatea.kernel.packet import (
    AccessScope,
    ArtifactRef,
    CognitivePacket,
    EnvelopeViolation,
    Provenance,
    RepresentationLevel,
    make_packet,
    packet_fields,
    revise,
    verify_integrity,
)
from galatea.kernel.unknown import NotTypedUnknown, Unknown, UnknownReason


def _packet(**overrides: object) -> CognitivePacket:
    fields: dict[str, object] = {
        "event_id": "E01",
        "subject_candidate_id": "S1",
        "run_id": "R1",
        "branch_id": "B1",
        "activity_window_id": "W1",
        "cycle_id": 4,
        "virtual_time": 4,
        "source_module": "sense",
        "content_type": "test.signal.v1",
        "representation_level": RepresentationLevel.RECEIVED,
        "schema_version": "v1",
        "payload_ref": ArtifactRef(digest="0" * 64, kind="payload"),
        "confidence": 0.5,
        "provenance": Provenance(),
        "causal_parent_ids": (),
        "access_scope": AccessScope.MODULE_LOCAL,
    }
    fields.update(overrides)
    return make_packet(**fields)  # type: ignore[arg-type]


def test_key_order_irrelevant() -> None:
    assert canonical_json({"a": 1, "b": 2}) == canonical_json({"b": 2, "a": 1})
    assert canonical_json({"x": {"b": 1, "a": 2}}) == canonical_json({"x": {"a": 2, "b": 1}})


def test_float_repr_roundtrip() -> None:
    assert canonical_json({"v": 0.1}) == b'{"v":0.1}'
    assert canonical_json({"v": -0.0}) == canonical_json({"v": -0.0})
    assert content_digest({"v": 1e300}) == content_digest({"v": 1e300})


def test_bytes_tagged_and_tuples_flattened() -> None:
    encoded = canonical_json({"b": b"\x00\xff"})
    assert b"__bytes_b64__" in encoded
    assert canonical_json((1, 2)) == canonical_json([1, 2])


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_fail_closed(bad: float) -> None:
    with pytest.raises(ValueError):
        canonical_json({"v": bad})


def test_non_string_key_rejected() -> None:
    with pytest.raises(TypeError):
        canonical_json({1: "x"})


@given(
    st.recursive(
        st.one_of(
            st.none(),
            st.booleans(),
            st.integers(-10**9, 10**9),
            st.floats(allow_nan=False, allow_infinity=False),
            st.text(max_size=32),
            st.binary(max_size=32),
        ),
        lambda children: st.one_of(
            st.lists(children, max_size=6),
            st.dictionaries(st.text(max_size=8), children, max_size=6),
        ),
        max_leaves=12,
    )
)
def test_canonical_json_deterministic(value: object) -> None:
    assert canonical_json(value) == canonical_json(value)


def test_envelope_frozen_and_digest_stable() -> None:
    p1 = _packet()
    p2 = _packet()
    assert p1.content_digest == p2.content_digest
    assert verify_integrity(p1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        p1.source_module = "other"  # type: ignore[misc]


def test_envelope_rejects_anonymous_and_bare_confidence() -> None:
    with pytest.raises(EnvelopeViolation):
        _packet(source_module="")
    with pytest.raises(EnvelopeViolation):
        _packet(event_id="")
    with pytest.raises(NotTypedUnknown):
        _packet(confidence=None)  # type: ignore[arg-type]
    with pytest.raises(NotTypedUnknown):
        _packet(confidence="unknown")  # type: ignore[arg-type]
    with pytest.raises(NotTypedUnknown):
        _packet(confidence=1.5)


def test_unknown_confidence_serialized_into_digest() -> None:
    u = Unknown(reason=UnknownReason.INSUFFICIENT_OBSERVATION, evidence_refs=("e",), detail=None, detected_by="sense", virtual_time=4)
    p_unknown = _packet(confidence=u)
    p_float = _packet(confidence=0.5)
    assert p_unknown.content_digest != p_float.content_digest
    assert verify_integrity(p_unknown)


def test_verify_integrity_detects_tamper() -> None:
    p = _packet()
    tampered = CognitivePacket(
        **{**packet_fields(p), "content_digest": p.content_digest, "cycle_id": 99}  # type: ignore[arg-type]
    )
    assert not verify_integrity(tampered)


def test_revision_references_old_event() -> None:
    p = _packet()
    r = revise(p, "E02", confidence=0.9)
    assert p.event_id in r.causal_parent_ids
    assert r.event_id == "E02"
    assert r.content_digest != p.content_digest
    with pytest.raises(EnvelopeViolation):
        revise(p, "E01")  # 同 id = 改写历史，禁止
    with pytest.raises(EnvelopeViolation):
        revise(p, "E03", content_digest="x")  # digest 与 event_id 不可经 changes 篡改
