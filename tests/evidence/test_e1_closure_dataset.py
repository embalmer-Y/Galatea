"""E1 60 格闭合数据集测试（既有 append-only 册 + close/gate 承载）。"""
from galatea.evidence.decision_registry.closure import ClosureGate
from galatea.evidence.decision_registry.collect import CellConclusion
from galatea.evidence.decision_registry_data import E1_CLOSURE_ENTRIES, e1_closure_report


def test_grid_complete_and_closed() -> None:
    assert len(E1_CLOSURE_ENTRIES) == 60   # 6×10 全枚举
    report, gate = e1_closure_report()
    assert report.denominator_closed
    assert report.unresolved_paths == ()
    assert gate is ClosureGate.CLOSED
    assert report.digest()


def test_na_cells_confined_to_remote() -> None:
    """MW0 不适用面 = remote 列专属（无网络负清单的结构面）——其他列全实现/延后。"""
    for e in E1_CLOSURE_ENTRIES:
        if e.conclusion is CellConclusion.NOT_APPLICABLE:
            assert e.path_type == "remote", (
                f"{e.path_class}x{e.path_type} N-A outside remote column"
            )


def test_deferred_cells_have_governance_anchor() -> None:
    deferred = [e for e in E1_CLOSURE_ENTRIES
                if e.conclusion is CellConclusion.DEFERRED_ADJUDICATED]
    assert deferred   # P1 面（现实授权）显式延后且带锚
    for e in deferred:
        assert any(r.startswith(("Q-", "ADR-")) for r in e.evidence_refs)
