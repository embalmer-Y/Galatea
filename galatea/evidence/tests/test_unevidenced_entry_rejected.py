"""无证据不入册（L13 §4.7/§7：无证据条目注入 → 检出且不落册）。"""
from pathlib import Path

import pytest

from galatea.evidence.decision_registry.collect import (
    CoreDecisionRegistry,
    DecisionPathEntry,
    EntryRejected,
    UnevidencedRegistryEntry,
)
from galatea.evidence.decision_registry.enumerate import CellConclusion, load_matrix

FROZEN_MATRIX = Path(__file__).resolve().parents[3] / "config" / "evidence" / "decision_path_matrix.yaml"


def _spec():
    return load_matrix(FROZEN_MATRIX)


def test_entry_without_evidence_rejected_and_not_stored() -> None:
    registry = CoreDecisionRegistry(_spec())
    entry = DecisionPathEntry(
        path_class="continuity_recovery",
        path_type="normal",
        conclusion=CellConclusion.IMPLEMENTED_VERIFIED,
        evidence_refs=(),
        reason="",
    )
    with pytest.raises(UnevidencedRegistryEntry):
        registry.register(entry)
    assert len(registry) == 0
    assert registry.all_entries() == ()


def test_unknown_cell_rejected() -> None:
    registry = CoreDecisionRegistry(_spec())
    entry = DecisionPathEntry(
        path_class="nonexistent_class",
        path_type="normal",
        conclusion=CellConclusion.IMPLEMENTED_VERIFIED,
        evidence_refs=("r1",),
        reason="",
    )
    with pytest.raises(EntryRejected):
        registry.register(entry)
    assert len(registry) == 0


def test_conclusion_without_reason_rejected() -> None:
    registry = CoreDecisionRegistry(_spec())
    for conclusion in (CellConclusion.NOT_APPLICABLE, CellConclusion.DEFERRED_ADJUDICATED):
        entry = DecisionPathEntry(
            path_class="continuity_recovery",
            path_type="normal",
            conclusion=conclusion,
            evidence_refs=("r1",),
            reason="",
        )
        with pytest.raises(EntryRejected):
            registry.register(entry)
    assert len(registry) == 0


def test_registry_is_append_only() -> None:
    registry = CoreDecisionRegistry(_spec())
    entry = DecisionPathEntry(
        path_class="continuity_recovery",
        path_type="normal",
        conclusion=CellConclusion.IMPLEMENTED_VERIFIED,
        evidence_refs=("REV-0002",),
        reason="fixture",
    )
    registry.register(entry)
    assert len(registry) == 1
    for banned in ("remove", "unregister", "delete", "clear", "pop"):
        assert not hasattr(registry, banned), f"registry must not expose {banned!r}"
