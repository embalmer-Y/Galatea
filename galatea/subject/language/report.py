"""SelfReport 与一致性判定 schema（L12 §2.2 report.py——"自述"分 schema 承载点）。

纪律：report ≠ model ≠ fact（HLD §11.1）——SelfReport 必须携带 derivation_refs
（无派生引用的自述在 schema 级即拒，R-REPORT 合同）；层级恒 EXTERNAL_STATEMENT；
一致性判定三态（CONSISTENT/DIVERGENT/UNKNOWN）是独立发现，不得为消除矛盾而改写。
F0 范围 = schema 合同；C4 范围 = R-REPORT 机械装配面（build_self_report：
SelfModelView 派生引用 → SelfReport，Q-L12-01 实现分型 MECHANICAL——报告数值
保真走 derivation_receipt 机械强制，措辞面经 R-TRANSLATE）。
"""
import enum
from dataclasses import dataclass

from galatea.kernel.packet import ArtifactRef
from galatea.subject.models.self_model import SelfModelView


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


def build_self_report(view: SelfModelView, report_id: str) -> SelfReport:
    """R-REPORT 机械装配（L12 §4.1：输入 = L04 SelfModelView 派生引用）。

    derivation_refs = 视图 derivation_receipts 的全部字段引用（字段级派生留证，
    Q-L12-05① 主层比较对象与此同源）；consistency 初始 UNKNOWN——判定是
    R-CHECKCONSIST 的独立产出（Q-L12-05③：判定 ≠ 报告构造，禁双向篡改）。
    """
    if not view.derivation_receipts:
        raise ValueError(
            "SelfModelView carries no derivation_receipts（无派生引用可装配——拒收）"
        )
    refs = tuple(f"{field}:{ref}" for field, field_refs in view.derivation_receipts for ref in field_refs)
    if not refs:
        raise ValueError("SelfModelView derivation_receipts carry no refs（空引用拒收）")
    return SelfReport(
        content_ref=ArtifactRef(digest=view.content_digest or report_id, kind="self_report"),
        derivation_refs=refs,
        consistency_with_internal=ConsistencyVerdict.UNKNOWN,
    )
