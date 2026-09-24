"""信念层级恒定（L03 §10 test_level_invariance.py——F0 schema 层：层级禁提升/改写）。"""
import pytest

from galatea.kernel.packet import ArtifactRef, Provenance
from galatea.kernel.unknown import NotTypedUnknown, Unknown, UnknownReason
from galatea.subject.perception.believe import AltHypothesis, BeliefKind, PerceptualBelief


def _belief(**overrides: object) -> PerceptualBelief:
    fields: dict[str, object] = dict(
        belief_id="bel-001",
        kind=BeliefKind.OBJECT,
        content=ArtifactRef(digest="5" * 64, kind="percept"),
        confidence=0.7,
        alternatives=(AltHypothesis(content_ref=ArtifactRef(digest="6" * 64, kind="percept"), posterior=0.2),),
        modality_support=(("exteroceptive", ("f1", "f2")),),
        ood_flag=False,
        ood_score=0.1,
        calibration_version="cal@v1",
        provenance=Provenance(source_events=("e1",)),
        causal_parent_ids=("e1",),
        cycle_id=4,
    )
    fields.update(overrides)
    return PerceptualBelief(**fields)  # type: ignore[arg-type]


def test_level_fixed_perceived() -> None:
    belief = _belief()
    assert belief.representation_level == "PERCEIVED"  # 恒定；禁提升为 PREDICTED 等层级（L00 §8）


def test_level_cannot_be_forged_at_construction() -> None:
    """伪造层级即拒（REV-0003 R4：init=False + post_init 双保险）。"""
    with pytest.raises(TypeError):
        _belief(representation_level="RECEIVED")  # type: ignore[call-arg]  # 构造参数不存在


def test_confidence_rejects_bare_values() -> None:
    with pytest.raises(NotTypedUnknown):
        _belief(confidence=None)  # type: ignore[arg-type]


def test_unknown_confidence_is_typed_and_digest_stable() -> None:
    unknown = Unknown(reason=UnknownReason.CALIBRATION_UNCERTAIN, evidence_refs=(), detail=None, detected_by="perc", virtual_time=1)
    b1 = _belief(belief_id="bel-003", kind=BeliefKind.FIELD, confidence=unknown, ood_flag=True, ood_score=0.9, cycle_id=1,
                 content=ArtifactRef(digest="8" * 64, kind="percept"))
    b2 = _belief(belief_id="bel-003", kind=BeliefKind.FIELD, confidence=unknown, ood_flag=True, ood_score=0.9, cycle_id=1,
                 content=ArtifactRef(digest="8" * 64, kind="percept"))
    assert b1.digest() == b2.digest()
    assert _belief().digest() != b1.digest()
