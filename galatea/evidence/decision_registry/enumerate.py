"""核心决策路径矩阵枚举（L13 §4.7；Q-G00-04/Q-L13-04 CONFIRMED 2026-09-23）。

职责：加载 F0 冻结的 `config/evidence/decision_path_matrix.yaml`（card_04 原文
六类 × 十类 = 60 格分母），校验其完整性，向 registry/closure 提供唯一矩阵事实源。
矩阵逐格结论属 E1 交付——本模块只供分母，不产生结论。
"""
import enum
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml


class MatrixViolation(ValueError):
    """冻结矩阵文件与合同不符（分母/类目数/闭合规则缺失）。"""


class CellConclusion(enum.StrEnum):
    """单格显式结论三型（L13 §4.7：已实现并验证 / 不适用并说明 / 已裁决延后）。"""

    IMPLEMENTED_VERIFIED = "IMPLEMENTED_VERIFIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    DEFERRED_ADJUDICATED = "DEFERRED_ADJUDICATED"


@dataclass(frozen=True, slots=True)
class ClosureRule:
    """E1 闭合判据（冻结文件的 closure_rule 节）。"""

    unresolved_paths_must_be_empty: bool
    denominator_must_close: bool
    entry_requires_evidence_ref: bool


@dataclass(frozen=True, slots=True)
class MatrixSpec:
    """6×10 决策路径矩阵的唯一事实源（自冻结 YAML 加载，只读）。"""

    path_classes: tuple[str, ...]
    path_types: tuple[str, ...]
    denominator: int
    default_status: str
    conclusion_owner_gate: str
    closure_rule: ClosureRule

    def all_cells(self) -> tuple[tuple[str, str], ...]:
        """全部 (path_class, path_type) 格，确定性排序。"""
        return tuple((c, t) for c in self.path_classes for t in self.path_types)


def load_matrix(path: Path) -> MatrixSpec:
    """加载并校验冻结矩阵文件；不符即 MatrixViolation（fail closed）。"""
    doc = cast("dict[str, Any]", yaml.safe_load(path.read_text(encoding="utf-8")))
    for name in ("path_classes", "path_types", "matrix", "closure_rule"):
        if doc.get(name) is None:
            raise MatrixViolation(f"missing section: {name}")
    classes_doc = cast("list[Any]", doc["path_classes"])
    types_doc = cast("list[Any]", doc["path_types"])
    matrix = cast("dict[str, Any]", doc["matrix"])
    rule = cast("dict[str, Any]", doc["closure_rule"])
    if len(classes_doc) != 6:
        raise MatrixViolation(f"path_classes must have exactly 6 entries, got {len(classes_doc)}")
    if len(types_doc) != 10:
        raise MatrixViolation(f"path_types must have exactly 10 entries, got {len(types_doc)}")
    if matrix.get("denominator") != len(classes_doc) * len(types_doc):
        raise MatrixViolation(f"matrix.denominator must equal 6×10=60, got {matrix.get('denominator')}")
    cells_default = cast("dict[str, Any]", matrix.get("cells_default"))
    if not all(isinstance(rule.get(k), bool) for k in ("unresolved_paths_must_be_empty", "denominator_must_close", "entry_requires_evidence_ref")):
        raise MatrixViolation("closure_rule must be a mapping of three booleans")
    return MatrixSpec(
        path_classes=tuple(str(c) for c in classes_doc),
        path_types=tuple(str(t) for t in types_doc),
        denominator=int(matrix["denominator"]),
        default_status=str(cells_default.get("status", "PENDING")),
        conclusion_owner_gate=str(cells_default.get("owner_gate", "E1")),
        closure_rule=ClosureRule(
            unresolved_paths_must_be_empty=cast("bool", rule["unresolved_paths_must_be_empty"]),
            denominator_must_close=cast("bool", rule["denominator_must_close"]),
            entry_requires_evidence_ref=cast("bool", rule["entry_requires_evidence_ref"]),
        ),
    )
