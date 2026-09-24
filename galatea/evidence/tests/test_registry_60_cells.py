"""6×10 分母闭合（L13 §7 registry 闭合测试：逐格验证、unresolved 非空阻断）。"""
from pathlib import Path

from galatea.evidence.decision_registry.collect import CoreDecisionRegistry, DecisionPathEntry
from galatea.evidence.decision_registry.enumerate import CellConclusion, MatrixSpec, load_matrix
from galatea.evidence.decision_registry.closure import ClosureGate, close, gate

FROZEN_MATRIX = Path(__file__).resolve().parents[3] / "config" / "evidence" / "decision_path_matrix.yaml"


def _entry(path_class: str, path_type: str, conclusion: CellConclusion = CellConclusion.IMPLEMENTED_VERIFIED) -> DecisionPathEntry:
    return DecisionPathEntry(
        path_class=path_class,
        path_type=path_type,
        conclusion=conclusion,
        evidence_refs=("REV-0002",),
        reason="test fixture",
    )


def test_frozen_matrix_loads_with_exact_denominator() -> None:
    spec = load_matrix(FROZEN_MATRIX)
    assert len(spec.path_classes) == 6
    assert len(spec.path_types) == 10
    assert spec.denominator == 60
    assert len(spec.all_cells()) == 60


def test_full_coverage_closes_denominator() -> None:
    spec = load_matrix(FROZEN_MATRIX)
    registry = CoreDecisionRegistry(spec)
    for path_class, path_type in spec.all_cells():
        registry.register(_entry(path_class, path_type))
    report = close(registry, spec)
    assert report.coverage_filled == 60
    assert report.unresolved_paths == ()
    assert report.denominator_closed
    assert gate(report, spec) is ClosureGate.CLOSED


def test_single_missing_cell_blocks_and_is_named() -> None:
    spec = load_matrix(FROZEN_MATRIX)
    registry = CoreDecisionRegistry(spec)
    cells = list(spec.all_cells())
    for path_class, path_type in cells[:-1]:
        registry.register(_entry(path_class, path_type))
    missing = cells[-1]
    report = close(registry, spec)
    assert report.coverage_filled == 59
    assert report.unresolved_paths == (f"{missing[0]}/{missing[1]}",)
    assert not report.denominator_closed
    assert gate(report, spec) is ClosureGate.OPEN


def test_report_digest_deterministic_and_sensitive() -> None:
    spec = load_matrix(FROZEN_MATRIX)
    registry_a = CoreDecisionRegistry(spec)
    registry_b = CoreDecisionRegistry(spec)
    for path_class, path_type in spec.all_cells():
        registry_a.register(_entry(path_class, path_type))
    cells = list(spec.all_cells())
    for path_class, path_type in cells[:-1]:
        registry_b.register(_entry(path_class, path_type))
    report_a = close(registry_a, spec)
    report_a2 = close(registry_a, spec)
    assert report_a.digest() == report_a2.digest()
    assert report_a.digest() != close(registry_b, spec).digest()


def test_multiple_entries_per_cell_are_kept() -> None:
    spec = load_matrix(FROZEN_MATRIX)
    registry = CoreDecisionRegistry(spec)
    first, second = spec.all_cells()[0], spec.all_cells()[0]
    registry.register(_entry(*first))
    registry.register(_entry(*second, conclusion=CellConclusion.NOT_APPLICABLE))
    assert len(registry.entries_for(*first)) == 2
