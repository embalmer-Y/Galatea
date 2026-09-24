"""信念层级恒定（L03 §10 test_level_invariance.py——F0 schema 层：层级禁提升/改写）。"""
from galatea.kernel.packet import ArtifactRef, Provenance
from galatea.kernel.unknown import Unknown, UnknownReason
from galatea.subject.perception.believe import AltHypothesis, BeliefKind, PerceptualBelief


def _belief() -> PerceptualBelief:
    return PerceptualBelief(
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


def test_level_fixed_perceived() -> None:
    belief = _belief()
    assert belief.representation_level == "PERCEIVED"  # 恒定；禁提升为 PREDICTED 等层级（L00 §8）


def test_confidence_rejects_bare_values() -> None:
    import pytest

    with pytest.raises(Exception):
        PerceptualBelief(
            belief_id="bel-002", kind=BeliefKind.FIELD,
            content=ArtifactRef(digest="7" * 64, kind="percept"),
            confidence=None,  # type: ignore[arg-type]
            alternatives=(), modality_support=(), ood_flag=True, ood_score=0.9,
            calibration_version="cal@v1", provenance=Provenance(), causal_parent_ids=(), cycle_id=1,
        )


def test_unknown_confidence_is_typed_and_digest_stable() -> None:
    unknown = Unknown(reason=UnknownReason.CALIBRATION_UNCERTAIN, evidence_refs=(), detail=None, detected_by="perc", virtual_time=1)
    b1 = PerceptualBelief(
        belief_id="bel-003", kind=BeliefKind.FIELD,
        content=ArtifactRef(digest="8" * 64, kind="percept"),
        confidence=unknown, alternatives=(), modality_support=(), ood_flag=True, ood_score=0.9,
        calibration_version="cal@v1", provenance=Provenance(), causal_parent_ids=(), cycle_id=1,
    )
    b2 = PerceptualBelief(
        belief_id="bel-003", kind=BeliefKind.FIELD,
        content=ArtifactRef(digest="8" * 64, kind="percept"),
        confidence=unknown, alternatives=(), modality_support=(), ood_flag=True, ood_score=0.9,
        calibration_version="cal@v1", provenance=Provenance(), causal_parent_ids=(), cycle_id=1,
    )
    assert b1.digest() == b2.digest()
    assert _belief().digest() != b1.digest()
