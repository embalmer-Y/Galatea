"""闭合判定（L13 §4.7：E1 硬条件——unresolved_paths 空 + 分母闭合 60 格）。

"registry 存在 ≠ 闭合证据"：闭合 = 每格至少一条带显式结论的 entry；
缺格即入 unresolved_paths（禁"默认通过"）。报告可经 kernel canonical digest
落 registry（报告本身可复算）。
"""
import enum
from dataclasses import dataclass

from galatea.kernel.digest import content_digest
from galatea.evidence.decision_registry.collect import CoreDecisionRegistry
from galatea.evidence.decision_registry.enumerate import MatrixSpec


@dataclass(frozen=True, slots=True)
class ClosureReport:
    """闭合报告：覆盖计数、未闭合格清单、分母闭合布尔。"""

    coverage_filled: int
    denominator: int
    unresolved_paths: tuple[str, ...]
    denominator_closed: bool

    def digest(self) -> str:
        """报告自身的内容摘要（入 registry，供复算比对）。"""
        return content_digest(
            {
                "coverage_filled": self.coverage_filled,
                "denominator": self.denominator,
                "unresolved_paths": list(self.unresolved_paths),
                "denominator_closed": self.denominator_closed,
            }
        )


class ClosureGate(enum.StrEnum):
    """闭合判定对 E1 门的语义（承 L13 §9 E1 行）。"""

    OPEN = "OPEN"          # 未闭合：E1 阻断
    CLOSED = "CLOSED"      # 60/60 且无未闭合路径


def close(registry: CoreDecisionRegistry, spec: MatrixSpec) -> ClosureReport:
    """判定闭合：任何无 entry 的格计入 unresolved_paths（确定性排序）。"""
    unresolved: list[str] = []
    covered = 0
    for path_class, path_type in spec.all_cells():
        entries = registry.entries_for(path_class, path_type)
        if entries:
            covered += 1
        else:
            unresolved.append(f"{path_class}/{path_type}")
    return ClosureReport(
        coverage_filled=covered,
        denominator=spec.denominator,
        unresolved_paths=tuple(unresolved),
        denominator_closed=not unresolved and covered == spec.denominator,
    )


def gate(report: ClosureReport, spec: MatrixSpec) -> ClosureGate:
    """E1 门语义：消费冻结文件的 closure_rule（ADR-G-0003 R9④）——两判据按冻结规则强制。"""
    rule = spec.closure_rule
    if rule.unresolved_paths_must_be_empty and report.unresolved_paths:
        return ClosureGate.OPEN
    if rule.denominator_must_close and not report.denominator_closed:
        return ClosureGate.OPEN
    return ClosureGate.CLOSED
