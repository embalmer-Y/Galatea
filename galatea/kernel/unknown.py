"""typed unknown（L00 §6.1；Q-L00-02 CONFIRMED：冻结清单 10 项，增删走 schema 版本）。

纪律：一切不确定性必须类型化——裸 None / 空串 / 字符串 "unknown" 充当不确定性
一律拒绝（CI 静态规则 + 本模块运行时双重拒绝）。
"""
import enum
from dataclasses import dataclass


class UnknownReason(enum.StrEnum):
    """冻结清单（f0_l00.profile.yaml unknown_reasons；Q-L00-02，2026-09-23）。"""

    MISSING_SIGNAL = "MISSING_SIGNAL"
    CALIBRATION_UNCERTAIN = "CALIBRATION_UNCERTAIN"
    SOURCE_AMBIGUOUS = "SOURCE_AMBIGUOUS"
    OOD = "OOD"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    INSUFFICIENT_OBSERVATION = "INSUFFICIENT_OBSERVATION"
    CAPABILITY_LIMIT = "CAPABILITY_LIMIT"
    ATTRIBUTION_UNRESOLVED = "ATTRIBUTION_UNRESOLVED"
    DECISION_PATH_UNRESOLVED = "DECISION_PATH_UNRESOLVED"
    STREAM_MISSING = "STREAM_MISSING"


@dataclass(frozen=True, slots=True)
class Unknown:
    """类型化不确定性：携带原因、证据引用与检出者。"""

    reason: UnknownReason
    evidence_refs: tuple[str, ...]
    detail: str | None
    detected_by: str
    virtual_time: int


class NotTypedUnknown(ValueError):
    """以裸 None/空串/"unknown" 等充当不确定性（L00 §6.1 禁止）。"""


def ensure_typed_confidence(value: object, field: str) -> "float | Unknown":
    """运行时守卫：置信位必须是有界 float 或 typed Unknown。"""
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise NotTypedUnknown(f"{field}: non-finite float is not a confidence")
        if not 0.0 <= value <= 1.0:
            raise NotTypedUnknown(f"{field}: confidence out of [0,1]: {value!r}")
        return value
    if isinstance(value, Unknown):
        return value
    raise NotTypedUnknown(
        f"{field}: bare {type(value).__name__} is not a typed confidence"
        "（禁裸 None/空串/字符串 unknown，L00 §6.1）"
    )


@dataclass(frozen=True, slots=True)
class UnknownsEntry:
    """登记表条目：append-only，id 单调。"""

    entry_id: int
    unknown: Unknown


class UnknownsLog:
    """subject_state.unknowns 的登记表（唯一写者：产生该 unknown 的模块经本表落账）。"""

    def __init__(self) -> None:
        self._entries: list[UnknownsEntry] = []
        self._next_id: int = 1

    def add(self, unknown: Unknown) -> int:
        entry = UnknownsEntry(entry_id=self._next_id, unknown=unknown)
        self._entries.append(entry)
        self._next_id += 1
        return entry.entry_id

    def snapshot(self) -> tuple[UnknownsEntry, ...]:
        """只读快照（append-only：后续 add 不影响既有快照）。"""
        return tuple(self._entries)

    def count(self, reason: UnknownReason) -> int:
        return sum(1 for e in self._entries if e.unknown.reason is reason)
