"""SelfReport 与一致性判定 schema（L12 §2.2 report.py——"自述"分 schema 承载点）。

纪律：report ≠ model ≠ fact（HLD §11.1）——SelfReport 必须携带 derivation_refs
（无派生引用的自述在 schema 级即拒，R-REPORT 合同）；层级恒 EXTERNAL_STATEMENT；
一致性判定三态（CONSISTENT/DIVERGENT/UNKNOWN）是独立发现，不得为消除矛盾而改写。
F0 范围 = schema 合同；R-REPORT 行为归 C4。
"""
import enum
from dataclasses import dataclass

from galatea.kernel.packet import ArtifactRef


class ConsistencyVerdict(enum.StrEnum):
    """自我报告 vs 内部状态判定（L12 §2.2 lang.self_report）。"""

    CONSISTENT = "CONSISTENT"
    DIVERGENT = "DIVERGENT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class SelfReport:
    """自我报告（派生视图，非事实非边界）。"""

    content_ref: ArtifactRef
    derivation_refs: tuple[str, ...]
    consistency_with_internal: ConsistencyVerdict
    cited_evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.derivation_refs:
            raise ValueError("SelfReport requires derivation_refs（无派生引用的自述拒收，L12 §4.4）")
