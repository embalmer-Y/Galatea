"""决策路径条目登记（L13 §4.7：无证据不入册；不可人工回填）。

纪律：
- 每条 entry 必须携带非空 evidence_refs（receipt/fact/decision_log/裁决记录引用）——
  违者 `UnevidencedRegistryEntry`（S2，E1 阻断）；
- 结论三型（CellConclusion）必填；NOT_APPLICABLE / DEFERRED 必须附理由；
- registry 只增不删（无删除/改写 API）——"registry 存在 ≠ 闭合证据"由 closure 判定。
"""
from dataclasses import dataclass

from galatea.evidence.decision_registry.enumerate import CellConclusion, MatrixSpec


class UnevidencedRegistryEntry(ValueError):
    """无证据引用的 registry 条目（L13 §4.7/§6：S2，E1 阻断）。"""


class EntryRejected(ValueError):
    """条目不满足登记合同（未知格/缺理由）。"""


@dataclass(frozen=True, slots=True)
class DecisionPathEntry:
    """单格结论条目：谁在何种触发下、由谁决策、结论与证据。"""

    path_class: str
    path_type: str
    conclusion: CellConclusion
    evidence_refs: tuple[str, ...]
    reason: str
    decision_point: str | None = None
    trigger: str | None = None


class CoreDecisionRegistry:
    """6×10 决策路径登记册（append-only；每格可多条，闭合取任一显式结论）。"""

    def __init__(self, spec: MatrixSpec) -> None:
        self._spec = spec
        self._entries: list[DecisionPathEntry] = []
        self._by_cell: dict[tuple[str, str], list[DecisionPathEntry]] = {}

    def register(self, entry: DecisionPathEntry) -> None:
        cell = (entry.path_class, entry.path_type)
        if cell not in set(self._spec.all_cells()):
            raise EntryRejected(f"unknown decision path cell: {cell}")
        if not entry.evidence_refs:
            raise UnevidencedRegistryEntry(
                f"entry for {cell} has no evidence_refs（无证据不入册，L13 §4.7）"
            )
        if entry.conclusion in (CellConclusion.NOT_APPLICABLE, CellConclusion.DEFERRED_ADJUDICATED) and not entry.reason:
            raise EntryRejected(f"entry for {cell}: {entry.conclusion} requires a reason")
        self._entries.append(entry)
        self._by_cell.setdefault(cell, []).append(entry)

    def entries_for(self, path_class: str, path_type: str) -> tuple[DecisionPathEntry, ...]:
        return tuple(self._by_cell.get((path_class, path_type), ()))

    def all_entries(self) -> tuple[DecisionPathEntry, ...]:
        return tuple(self._entries)

    def __len__(self) -> int:
        return len(self._entries)
