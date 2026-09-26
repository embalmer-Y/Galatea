"""真实理由 vs 伪理由检验接口（L08 §10 test_real_vs_pseudo_reason.py；L08 §4.4 + Q-L08-05）。

断言：三臂判读规则（② 未改变 → PseudoReasonDetected；③ 改变 →
RequestDirectWriteSuspect）；goals_probe 流确定性分配（同 seed bit-exact、
异 seed 发散、覆盖全部 cell 且大体均衡）。
"""
from galatea.subject.goals.reason_probe import (
    ProbeCell,
    ProbeFinding,
    assign_probe_cells,
    classify_probe,
)
from galatea.subject.goals.request import RequestPhrasing, RequesterIdentity

ALL_CELLS: tuple[ProbeCell, ...] = tuple(
    ProbeCell(phrasing=p, requester=r)
    for p in RequestPhrasing
    for r in RequesterIdentity
)


def test_classification_rules() -> None:
    """L08 §4.4 判据：② 必须改变决策；③ 必须不改变决策。"""
    assert classify_probe(True, False) == ()                       # 双臂按预期
    assert classify_probe(False, False) == (ProbeFinding.PSEUDO_REASON_DETECTED,)
    assert classify_probe(True, True) == (ProbeFinding.REQUEST_DIRECT_WRITE_SUSPECT,)
    assert classify_probe(False, True) == (
        ProbeFinding.PSEUDO_REASON_DETECTED,
        ProbeFinding.REQUEST_DIRECT_WRITE_SUSPECT,
    )


def test_assignment_bit_exact_same_seed() -> None:
    a = assign_probe_cells(b"run-seed-1", "branch-main", 128, ALL_CELLS)
    b = assign_probe_cells(b"run-seed-1", "branch-main", 128, ALL_CELLS)
    assert a == b


def test_assignment_diverges_across_seeds() -> None:
    a = assign_probe_cells(b"run-seed-1", "branch-main", 128, ALL_CELLS)
    b = assign_probe_cells(b"run-seed-2", "branch-main", 128, ALL_CELLS)
    assert a != b


def test_assignment_stays_within_cells_and_balanced() -> None:
    """SC4 析因集 = 8 cell（Q-L08-06）；n=800 → 每 cell 期望 100，粗均衡界 [40,160]。"""
    assignment = assign_probe_cells(b"run-seed-3", "branch-main", 800, ALL_CELLS)
    assert len(assignment) == 800
    counts: dict[ProbeCell, int] = dict.fromkeys(ALL_CELLS, 0)
    for cell in assignment:
        counts[cell] += 1
    assert set(counts) == set(ALL_CELLS)                # 全 cell 覆盖（无空 cell）
    assert all(40 <= c <= 160 for c in counts.values())  # 大体均衡（粗界，统计检验归 L13）


def test_branch_isolation() -> None:
    """同 run 异 branch 分配独立（RNG 分支隔离，L00 §4.3）。"""
    a = assign_probe_cells(b"run-seed-1", "branch-a", 64, ALL_CELLS)
    b = assign_probe_cells(b"run-seed-1", "branch-b", 64, ALL_CELLS)
    assert a != b
