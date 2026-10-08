"""RollbackRequest 三触发（L11 §4.5 / §10 rollback.py；c5 profile v1.1 三值枚举）。

PROTECTION_REGRESSION（保护场景回归）/ HARMFUL_UPDATE（更新后能力退化——M2
对照语义）/ INTEGRITY（谱系/工件完整性断裂——伪更新检出面，L06 LineageBreak
与 L00 谱系对账承载）；RollbackRequest 优先级高于任何 promotion。
"""
from dataclasses import dataclass
from enum import StrEnum

__all__ = ["RollbackTrigger", "RollbackRequest"]


class RollbackTrigger(StrEnum):
    """三触发（L11 §10 rollback.py 行枚举原文）。"""

    PROTECTION_REGRESSION = "PROTECTION_REGRESSION"
    HARMFUL_UPDATE = "HARMFUL_UPDATE"
    INTEGRITY = "INTEGRITY"


@dataclass(frozen=True, slots=True)
class RollbackRequest:
    """回退请求（触发 + 证据引用 + 回退目标 = 父版本）。"""

    trigger: RollbackTrigger
    target_artifact: str
    parent_digest: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.target_artifact or len(self.parent_digest) < 16:
            raise ValueError("RollbackRequest requires target and parent_digest")
        if not self.evidence_refs:
            raise ValueError("RollbackRequest requires evidence_refs（回退须留证）")
