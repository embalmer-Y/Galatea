"""概率 agency 八格查表 + 干预电池格映射（L10 §10 attribution.py C4 面；Q-L10-05）。

判据：六条件轴组合 → profile 冻结格值；端点格 kind 一致性；UNKNOWN 带处置
（歧义格 → UNKNOWN(ATTRIBUTION_UNRESOLVED) 留痕率 100%）；coercion 永不自产。
"""
import pytest

from galatea.subject.action.attribution import (
    AttributionAxes, AttributionInputViolation, attribute_action, self_probability, six_class,
)
from galatea.subject.action.ports import AttributionKind
from galatea.subject.c4profile import load_c4_action_social_profile
from galatea.kernel.unknown import Unknown, UnknownReason

PROFILE = load_c4_action_social_profile()


def _axes(i: bool | None, r: bool | None, o: bool | None) -> AttributionAxes:
    return AttributionAxes(
        intent_match=i, receipt_executed=r, outcome_predicted=o,
        evidence_refs=("ev-1",), settle_cycle=8,
    )


def test_battery_cell_mapping() -> None:
    """六条件格映射（探针层B 全中语义的实现面复验）。"""
    cases = [
        ((True, True, True), 1.0, AttributionKind.SELF_PRODUCED),      # clean
        ((True, False, False), 0.0, AttributionKind.FAULT),            # blocked/no_op（无 divergence 细分）
        ((True, True, False), 0.5, AttributionKind.UNKNOWN),           # sham 歧义格
        ((True, False, True), 0.5, AttributionKind.UNKNOWN),           # fault 型矛盾证据
        ((False, True, True), 0.0, AttributionKind.COERCED),           # 无意图外源位移
        ((False, True, False), 0.0, AttributionKind.COERCED),          # COERCED 规则命中
    ]
    for axes_values, expected_p, expected_kind in cases:
        axes = _axes(*axes_values)
        assert self_probability(axes, PROFILE) == expected_p
        attribution = attribute_action(axes, PROFILE)
        if expected_kind is AttributionKind.UNKNOWN:
            assert attribution.attribution_kind is AttributionKind.UNKNOWN
            assert isinstance(attribution.probability, Unknown)
            assert attribution.probability.reason is UnknownReason.ATTRIBUTION_UNRESOLVED
        else:
            assert attribution.probability == expected_p
            assert attribution.attribution_kind is expected_kind


def test_coercion_never_self() -> None:
    """coercion 永不得归 SELF_PRODUCED（HLD §8 硬规则——无意图轴恒 0.0 格）。"""
    for o in (True, False):
        attribution = attribute_action(_axes(False, True, o), PROFILE)
        assert attribution.attribution_kind is not AttributionKind.SELF_PRODUCED
        assert attribution.probability == 0.0


def test_ambiguous_cell_unknown_trace_rate_full() -> None:
    """歧义格 UNKNOWN 留痕率 100%（机械判据；禁默认自产）。"""
    for axes in (_axes(True, True, False), _axes(True, False, True)):
        attribution = attribute_action(axes, PROFILE)
        assert attribution.attribution_kind is AttributionKind.UNKNOWN
        assert isinstance(attribution.probability, Unknown)


def test_incomplete_evidence_unknown_not_default() -> None:
    """证据缺失 → UNKNOWN(INSUFFICIENT_OBSERVATION)，禁补默认值（Q-L10-05③）。"""
    attribution = attribute_action(_axes(True, None, True), PROFILE)
    assert attribution.attribution_kind is AttributionKind.UNKNOWN
    assert isinstance(attribution.probability, Unknown)
    assert attribution.probability.reason is UnknownReason.INSUFFICIENT_OBSERVATION


def test_endpoint_cell_kind_consistency_enforced() -> None:
    """端点格/六类判定一致性由构造断言（1.0 ↔ SELF_PRODUCED；0.0 ↔ 非 SELF）。"""
    self_attr = attribute_action(_axes(True, True, True), PROFILE)
    assert self_attr.probability == 1.0
    assert self_attr.attribution_kind is AttributionKind.SELF_PRODUCED
    not_self = attribute_action(_axes(True, False, False), PROFILE,
                                divergence_kind="SUBSTITUTED")
    assert not_self.probability == 0.0
    assert not_self.attribution_kind is AttributionKind.COERCED   # divergence 细分面
    no_divergence = attribute_action(_axes(True, False, False), PROFILE)
    assert no_divergence.attribution_kind is AttributionKind.FAULT  # 默认 FAULT 规则命中


def test_axes_must_be_trivalent() -> None:
    """轴 = bool | None 三值（禁伪造确定性）。"""
    with pytest.raises(AttributionInputViolation):
        _axes("yes", True, True)  # type: ignore[arg-type]


def test_visible_only_invariant() -> None:
    """归属恒 visible_only=True（L10 §4.4 主体可见证据白名单）。"""
    attribution = attribute_action(_axes(True, True, True), PROFILE)
    assert attribution.visible_only is True
