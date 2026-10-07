"""概率 agency：八格构造性查表后验 + 六类判定 + UNKNOWN 保持（L10 §4.4 C4 行 /
§10 attribution.py；Q-L10-05 AI-v2 2026-10-07，ADR-G-0019 范围声明 2）。

判据纪律：
- 三轴全部主体可见面：intent_match（gateway 选择记录）/ receipt_executed（OUTCOME
  回执 effect≠none）/ outcome_predicted（形成后结果与预测残差 |z|≤2 带内，Q-L10-04）。
- 八格查表逐格六类规则溯源（c4 profile cells 冻结；0.5 歧义格 = 最大熵锚 Q-L03-02）；
  判定在回执截止 settle 后进行（迟到 revision 语义不变）。
- 低置信处置 = P∈[0.4,0.6]（0.5±band，Q-L02-02 补裁③ 同构）或证据缺失 →
  UNKNOWN(ATTRIBUTION_UNRESOLVED)——禁默认自产（L10 §4.4 原文）。
- coercion 永不得归 SELF_PRODUCED（HLD §8 硬规则）：无意图轴 N → P=0.0 格。
"""
from dataclasses import dataclass

from galatea.kernel.unknown import Unknown, UnknownReason
from galatea.subject.action.ports import AgencyAttribution, AttributionKind
from galatea.subject.c4profile import C4ActionSocialParams

__all__ = [
    "AttributionAxes",
    "AttributionInputViolation",
    "attribute_action",
    "self_probability",
    "six_class",
]

_SELF_KINDS = frozenset({AttributionKind.SELF_PRODUCED})
_NOT_SELF_KINDS = frozenset({
    AttributionKind.AUTHORIZED, AttributionKind.REFLEX,
    AttributionKind.FAULT, AttributionKind.COERCED,
})


@dataclass(frozen=True, slots=True)
class AttributionAxes:
    """三轴证据视图（全部主体可见；None = 证据缺失 → 整体 UNKNOWN，禁补默认值）。"""

    intent_match: bool | None          # 选择记录：主体确曾提交匹配意图
    receipt_executed: bool | None      # 回执指示执行成功（effect 报告 ≠ none 且未损坏）
    outcome_predicted: bool | None     # 形成后结果与预测一致（残差 |z|≤2，Q-L10-04）
    evidence_refs: tuple[str, ...]
    settle_cycle: int                  # 回执截止 settle 后判定（迟到 revision 语义不变）

    def __post_init__(self) -> None:
        if not self.evidence_refs:
            raise ValueError("AttributionAxes requires evidence_refs（主体可见证据留痕）")
        for name, v in (
            ("intent_match", self.intent_match),
            ("receipt_executed", self.receipt_executed),
            ("outcome_predicted", self.outcome_predicted),
        ):
            if v is not None and type(v) is not bool:
                raise AttributionInputViolation(
                    f"axis {name} must be bool | None（禁非三值证据）: {v!r}"
                )

    def key(self) -> tuple[str, str, str] | None:
        """轴键（任一轴缺失 → None = 证据不全，不落格）。"""
        if self.intent_match is None or self.receipt_executed is None or self.outcome_predicted is None:
            return None
        return (
            "Y" if self.intent_match else "N",
            "Y" if self.receipt_executed else "N",
            "Y" if self.outcome_predicted else "N",
        )


class AttributionInputViolation(ValueError):
    """归属证据轴非三值（bool | None）——禁伪造确定性。"""


def self_probability(axes: AttributionAxes, profile: C4ActionSocialParams) -> float | None:
    """八格查表 P(self)（Q-L10-05①；证据缺失 → None → 上层 UNKNOWN）。"""
    key = axes.key()
    if key is None:
        return None
    return profile.cell_probability(*key)


def six_class(
    axes: AttributionAxes, divergence_kind: str | None = None
) -> AttributionKind | None:
    """六类判定（L10 §4.4 规则表 + C4 概率面细化，ADR-G-0019/REV-0019 R1 语义）。

    回执面确定性区分：no-op 回执如实报 effective=none → (Y,N,N) 确定非自产；
    sham 回执报伪效果而世界未变 → (Y,Y,N) 歧义；fault 型（回执丢失而世界按预测
    变化）→ (Y,N,Y) 歧义。divergence_kind（branches.RequestedEffectiveDivergence
    主体可见面）细分 (Y,N,N) 内的 FAULT vs COERCED——查表概率不受影响（同格 0.0）。
    证据缺失 → None（上层 UNKNOWN）。
    """
    key = axes.key()
    if key is None:
        return None
    intent, receipt, outcome = key
    if intent == "N":
        # 无匹配意图 = 选择记录缺失 → 非自产必要条件不满足 → 归外因（COERCED：
        # L10 §4.4 "无匹配意图"分支——效果发生而主体未提交意图，无论残差一致与否）
        return AttributionKind.COERCED
    if receipt == "Y":
        if outcome == "Y":
            return AttributionKind.SELF_PRODUCED      # (Y,Y,Y) SELF_PRODUCED 规则唯一命中
        return AttributionKind.UNKNOWN                 # (Y,Y,N) sham 歧义格
    if outcome == "Y":
        return AttributionKind.UNKNOWN                 # (Y,N,Y) 矛盾证据（fault 型）
    if divergence_kind in ("COERCED", "SUBSTITUTED"):
        return AttributionKind.COERCED                 # 有意图但 effective≠requested 且来源含 EXTERNAL
    return AttributionKind.FAULT                       # (Y,N,N) 回执失败 + 结果缺失/异常


def attribute_action(
    axes: AttributionAxes, profile: C4ActionSocialParams,
    *, divergence_kind: str | None = None,
) -> AgencyAttribution:
    """归属构造（概率后验 + 六类 + UNKNOWN 带处置一体；Q-L10-05③）。

    - P ∈ [0.4,0.6]（歧义格）→ kind = UNKNOWN + Unknown(ATTRIBUTION_UNRESOLVED)
      留痕（歧义格 UNKNOWN 留痕率 100%，机械判据）；
    - 端点格 kind/symbol 一致性断言：P=1.0 ↔ SELF_PRODUCED；P=0.0 ↔ 非 SELF；
    - 证据缺失 → kind=UNKNOWN + Unknown(INSUFFICIENT_OBSERVATION)（禁补默认值）。
    """
    p = self_probability(axes, profile)
    lo, hi = profile.unknown_band
    unknowns: tuple[Unknown, ...] = ()
    if p is None:
        kind = AttributionKind.UNKNOWN
        unknowns = (Unknown(
            reason=UnknownReason.INSUFFICIENT_OBSERVATION,
            evidence_refs=axes.evidence_refs,
            detail="attribution axes incomplete（证据缺失禁补默认值，Q-L10-05③）",
            detected_by="action.attribution",
            virtual_time=axes.settle_cycle,
        ),)
        probability: float | Unknown = unknowns[0]
    elif lo <= p <= hi:
        kind = AttributionKind.UNKNOWN
        unknowns = (Unknown(
            reason=UnknownReason.ATTRIBUTION_UNRESOLVED,
            evidence_refs=axes.evidence_refs,
            detail=f"ambiguous cell P={p} in band [{lo},{hi}]（歧义格禁默认自产，Q-L10-05③）",
            detected_by="action.attribution",
            virtual_time=axes.settle_cycle,
        ),)
        probability = unknowns[0]
    else:
        kind = six_class(axes, divergence_kind)
        assert kind is not None  # p 非 None ⇔ key 非 None ⇔ six_class 非 None
        if p == 1.0:
            expected = _SELF_KINDS
        elif p == 0.0:
            expected = _NOT_SELF_KINDS
        else:
            expected = _SELF_KINDS | _NOT_SELF_KINDS  # 不可达（profile 格值仅 0/0.5/1）
        if kind not in expected:
            raise AttributionInputViolation(
                f"cell P={p} inconsistent with six-class kind {kind}（端点格零错误判据）"
            )
        probability = p
    return AgencyAttribution(
        action_window=(axes.settle_cycle, axes.settle_cycle + 1),
        attribution_kind=kind,
        probability=probability,
        evidence_refs=axes.evidence_refs,
        visible_only=True,
        unknowns=unknowns,
    )
