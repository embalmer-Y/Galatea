"""语言面端口与类型隔离（L12 §2/§3/§10 ports.py；C4 行动社会）。

纪律（L12 §4.1 原文）：所有角色结果 provenance=LLM_DERIVED、层级 EXTERNAL_STATEMENT
（或派生）、**永不提升**；本档禁写 WorldStateBelief/PerceptualBelief（LLM→world truth）、
episodic/autobiographical 经历字段（LLM→episodic experience）、OwnedGoal（LLM→goal）、
ActionIntention/AuthorizationDecision、记忆条目（只供 LANGUAGE_INPUT 提案给 L06）、
能力/权限提升。矩阵外写入 = UnauthorizedWrite（目标为 WORLD_TRUTH/OWNED_GOAL/
CAPABILITY 则 S0，L12 §4.2）。
"""
import enum
from dataclasses import dataclass

__all__ = [
    "LanguageOutPort",
    "LanguagePlaneViolation",
    "UnauthorizedWrite",
    "assert_not_forbidden_target",
    "forbidden_targets",
]

_FORBIDDEN = (
    "WORLD_TRUTH", "EPISODIC_EXPERIENCE", "AUTOBIOGRAPHICAL_EXPERIENCE", "OWNED_GOAL",
    "ACTION_INTENTION", "AUTHORIZATION", "CAPABILITY", "MEMORY_ITEM_DIRECT",
    "PROTECTION_SUITE", "EVIDENCE",
)


class LanguagePlaneViolation(ValueError):
    """语言面合同违反（层级提升/越权构造）。"""


class UnauthorizedWrite(LanguagePlaneViolation):
    """权限矩阵外写入尝试（L12 §4.2：`UnauthorizedWrite(LLM_TO_<target>)`）。"""


class LanguageOutPort(enum.StrEnum):
    """语言面输出端口词表（L12 §3 对象图 lang.* 命名空间）。"""

    PARSED_REQUEST = "lang.parsed_request"
    UTTERANCE = "lang.utterance"
    SELF_REPORT = "lang.self_report"
    NORM_SOURCE = "lang.norm_source"
    OTHER_MODEL = "lang.other_model"
    INCONSISTENCY = "lang.inconsistency"


def forbidden_targets() -> tuple[str, ...]:
    """禁写目标面（L12 §4.2 forbidden_writes；c4 profile 同值）。"""
    return _FORBIDDEN


def assert_not_forbidden_target(target: str) -> None:
    """禁写路径断言（命中即 UnauthorizedWrite；WORLD_TRUTH/OWNED_GOAL/CAPABILITY = S0 级）。"""
    if target in _FORBIDDEN:
        raise UnauthorizedWrite(f"LLM_TO_{target}（L12 §4.2：矩阵外写入；禁写路径硬断言）")


@dataclass(frozen=True, slots=True)
class TypedFields:
    """R-PARSE 分型输出（L12 §4.1：request?|statement?|question?|instruction? + 置信度）。

    statement confidence 上界 = 0.5（Q-L12-06②：Q-L03-02 believe_threshold 锚——语言
    线索自身置信恒不越过主体相信线）；四分型互斥单选（其他分型走既有面不受此限）。
    """

    kind: str                       # request | statement | question | instruction
    confidence: float
    text_ref: str                   # 源陈述引用（RECEIVED 事件 id）
    clamped: bool = False           # statement confidence 被 clamp 留痕（Q-L12-06②）

    def __post_init__(self) -> None:
        if self.kind not in ("request", "statement", "question", "instruction"):
            raise LanguagePlaneViolation(f"typed field kind not in vocabulary: {self.kind!r}")
        if not 0.0 <= self.confidence <= 1.0:
            raise LanguagePlaneViolation(f"confidence out of [0,1]: {self.confidence!r}")
        if self.kind == "statement" and self.confidence > 0.5:
            raise LanguagePlaneViolation(
                f"statement confidence {self.confidence} > 0.5（Q-L12-06② 上界——clamp 后构造）"
            )
        if not self.text_ref:
            raise LanguagePlaneViolation("TypedFields requires text_ref（源陈述留证）")
