"""R-CHECKCONSIST：自我报告一致性机械判定（L12 §4.4 / §10 consistency.py；Q-L12-05）。

判定 = 两层独立产出 CONSISTENT|DIVERGENT|UNKNOWN（Q-L12-05①）：主层 = L04
SelfModelView 字段级（R-REPORT derivation_refs 逐字段）；副层 = 主体信念/归属面
（比较器同构，输入由装配层按在位信念面供给）。数值阈值 = **绝对差**
|reported − derived| ≤ 0.1（band=0.1=2σ，Q-L05-03③ 同锚；REV-0019 R4 钉死：
绝对差非相对差；float64 直接比较，边界对 (0.5,0.6)=CONSISTENT / (0.55,0.45)=
DIVERGENT 的表示噪声如实成文——实现期测试钉死）。分类型精确匹配。derived 侧
Unknown → UNKNOWN（禁将未知强判一致）。DIVERGENT = 一等发现**零修改**（禁改
内部状态、禁改报告——L12 §4.4 原文）。实现分型 = MECHANICAL（Q-L12-01 补裁：
机械判定是 Q-L12-05 裁决本体的直接要求）。
"""
from dataclasses import dataclass
from typing import Any

from galatea.kernel.unknown import Unknown
from galatea.subject.language.report import ConsistencyVerdict

__all__ = ["ConsistencyInput", "LanguageInternalMismatch", "check_consistency", "compare_layer"]

BAND = 0.1   # Q-L05-03③ band=0.1=2σ 同锚（REV-0019 R4 钉死绝对差语义）


@dataclass(frozen=True, slots=True)
class ConsistencyInput:
    """单层比较输入（数值对 + 分类型对；全部主体可见面）。"""

    numeric_reported: tuple[tuple[str, float], ...]
    numeric_derived: tuple[tuple[str, "float | Unknown"], ...]
    categorical_reported: tuple[tuple[str, str], ...] = ()
    categorical_derived: tuple[tuple[str, "str | Unknown"], ...] = ()

    def __post_init__(self) -> None:
        if not self.numeric_reported and not self.categorical_reported:
            raise ValueError("ConsistencyInput requires at least one reported field（无主张即无判定）")


@dataclass(frozen=True, slots=True)
class LanguageInternalMismatch:
    """语言-内部不一致（一等发现；零修改处置——L12 §4.4 原文）。"""

    field_name: str
    reported: str
    derived: str
    ts: int


def _lookup(pairs: "tuple[tuple[str, Any], ...]", name: str) -> Any:
    for k, v in pairs:
        if k == name:
            return v
    return None


def compare_layer(input_: ConsistencyInput) -> ConsistencyVerdict:
    """单层机械比较（绝对差带 + 分类型精确 + derived Unknown → UNKNOWN）。"""
    saw_unknown = False
    for name, reported in input_.numeric_reported:
        derived = _lookup(input_.numeric_derived, name)
        if derived is None:
            return ConsistencyVerdict.UNKNOWN            # derived 字段缺席 = 无从判定
        if isinstance(derived, Unknown):
            saw_unknown = True                            # 禁将未知强判一致（Q-L12-05①）
            continue
        if abs(reported - derived) > BAND:                # float64 直接比较（REV-0019 R4）
            return ConsistencyVerdict.DIVERGENT
    for name, reported in input_.categorical_reported:
        derived = _lookup(input_.categorical_derived, name)
        if derived is None:
            return ConsistencyVerdict.UNKNOWN
        if isinstance(derived, Unknown):
            saw_unknown = True
            continue
        if reported != derived:                           # 分类型精确匹配（枚举不一致即 DIVERGENT）
            return ConsistencyVerdict.DIVERGENT
    if saw_unknown:
        return ConsistencyVerdict.UNKNOWN
    return ConsistencyVerdict.CONSISTENT


def check_consistency(
    primary: ConsistencyInput, secondary: ConsistencyInput | None, ts: int
) -> tuple[ConsistencyVerdict, LanguageInternalMismatch | None]:
    """两层独立判定聚合（Q-L12-05①：任一 DIVERGENT → DIVERGENT；否则任一 UNKNOWN →
    UNKNOWN；副层缺席（装配层未接信念面）→ 主层判定承载——副层比较器与主层同构，
    输入接线随 L04/L10 信念面深化）。DIVERGENT 产出 LanguageInternalMismatch 留痕，
    **零修改**内部状态与报告。"""
    v_primary = compare_layer(primary)
    v_secondary = compare_layer(secondary) if secondary is not None else None
    if ConsistencyVerdict.DIVERGENT in (v_primary, v_secondary):
        diverging = primary if v_primary is ConsistencyVerdict.DIVERGENT else secondary
        assert diverging is not None
        name, reported, derived = _first_divergence(diverging)
        return ConsistencyVerdict.DIVERGENT, LanguageInternalMismatch(
            field_name=name, reported=reported, derived=derived, ts=ts,
        )
    if ConsistencyVerdict.UNKNOWN in (v_primary, v_secondary):
        return ConsistencyVerdict.UNKNOWN, None
    return ConsistencyVerdict.CONSISTENT, None


def _first_divergence(input_: ConsistencyInput) -> tuple[str, str, str]:
    for name, reported in input_.numeric_reported:
        derived = _lookup(input_.numeric_derived, name)
        if derived is not None and not isinstance(derived, Unknown) and abs(reported - derived) > BAND:
            return name, repr(reported), repr(derived)
    for name, reported in input_.categorical_reported:
        derived = _lookup(input_.categorical_derived, name)
        if derived is not None and not isinstance(derived, Unknown) and reported != derived:
            return name, reported, str(derived)
    raise ValueError("no divergence found（调用方须以 DIVERGENT 判定进入）")
