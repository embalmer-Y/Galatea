"""记忆端口合同：来源类型/层级断言（L06 §2/§10 ports.py——M2 最小切片）。

纪律：来源类型是**强制字段**（L06 §2.2，六类冻结枚举）；UNKNOWN 来源的记忆
不得用于自我连续性主张或归属证据；LANGUAGE_INPUT 记忆禁写 episodic 经历
（D-13）；回忆恒为 RECALLED、禁提升为知觉或事实（L06 §1，层级守卫在
RecalledContent 构造面机械强制）。
"""
import enum
from dataclasses import dataclass, field

from galatea.kernel.packet import RepresentationLevel
from galatea.kernel.unknown import Unknown

__all__ = [
    "SourceType",
    "MemorySubsystem",
    "ConsolidationState",
    "RecalledContent",
    "MemoryLevelViolation",
    "assert_recall_level",
]


class SourceType(enum.StrEnum):
    """来源六类（L06 §2.2 纪律冻结枚举；强制字段，UNKNOWN 受使用限）。"""

    PERCEIVED = "PERCEIVED"
    SELF_GENERATED = "SELF_GENERATED"
    RECALLED_DERIVED = "RECALLED_DERIVED"
    LANGUAGE_INPUT = "LANGUAGE_INPUT"
    IMAGINED_DERIVED = "IMAGINED_DERIVED"
    UNKNOWN = "UNKNOWN"


class MemorySubsystem(enum.StrEnum):
    """八子系统（L06 §1 承 card_02 §1；M2 切片只启用 WORKING/EPISODIC——m2_continuity.profile）。"""

    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    AFFECTIVE_VALUE = "affective_value"
    PROSPECTIVE = "prospective"
    AUTOBIOGRAPHICAL = "autobiographical"
    METAMEMORY = "metamemory"


class ConsolidationState(enum.StrEnum):
    """条目状态机（L06 §4 items.py：LABILE→…→FORGOTTEN）。"""

    LABILE = "LABILE"
    CONSOLIDATING = "CONSOLIDATING"
    CONSOLIDATED = "CONSOLIDATED"
    PROTECTED = "PROTECTED"
    ARCHIVED = "ARCHIVED"
    FORGOTTEN = "FORGOTTEN"


class MemoryLevelViolation(ValueError):
    """层级违例：回忆内容冒充知觉/事实，或 RECALLED 之外的记忆层级伪装（L06 §1）。"""


@dataclass(frozen=True, slots=True)
class RecalledContent:
    """检索输出（L06 §2.2 mem.recall：level 恒 RECALLED，构造面机械强制）。"""

    memory_ref: str
    subsystem: MemorySubsystem
    source_type: SourceType
    content_ref: str
    reliability: float
    retrieved_at: int
    level: RepresentationLevel = field(default=RepresentationLevel.RECALLED, init=False)
    unknowns: tuple[Unknown, ...] = ()

    def __post_init__(self) -> None:
        if self.level is not RepresentationLevel.RECALLED:
            raise MemoryLevelViolation("RecalledContent.level is immutable RECALLED（L06 §1 层级守卫）")
        if not 0.0 <= self.reliability <= 1.0:
            raise ValueError("reliability out of [0,1]")


def assert_recall_level(level: RepresentationLevel) -> None:
    """层级守卫（L06 §1：RECALLED 禁提升——下游消费 RECALLED 内容时不得重标）。"""
    if level is not RepresentationLevel.RECALLED:
        raise MemoryLevelViolation(
            f"recalled content cannot be relabeled {level.value}（RECALLED 禁提升为知觉/事实）"
        )
