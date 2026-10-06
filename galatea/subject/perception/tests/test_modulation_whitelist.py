"""调制白名单测试（L03 §4.5/§7 modulation_whitelist 行；C2：believe_threshold 接收面开启）。"""
import pytest

from galatea.subject.perception.modulation import (
    BELIEVE_THRESHOLD_BOUND,
    FORBIDDEN_FIELDS,
    ModulationField,
    ModulationRejected,
    apply_modulation,
)

#: C2 白名单三字段（常量类承载，L03 §4.5 冻结枚举值）
WHITELIST = (ModulationField.PRECISION_WEIGHTS, ModulationField.BELIEVE_THRESHOLD,
             ModulationField.COMPETITION_WINDOW)


def test_whitelist_fields_without_source_rejected():
    """白名单内字段中无 C2 调制源者（precision_weights/competition_window）——拒绝留痕。"""
    for field in WHITELIST:
        if field == ModulationField.BELIEVE_THRESHOLD:
            continue
        with pytest.raises(ModulationRejected) as info:
            apply_modulation(field, 0.7)
        assert "no modulation source" in str(info.value)


@pytest.mark.parametrize("field", FORBIDDEN_FIELDS)
def test_forbidden_fields_never_acceptable(field):
    """禁改字段（输入特征/标度/层级/历史）恒拒且不抛调制面异常（白名单外路径）。"""
    receipt = apply_modulation(field, object())
    assert receipt.accepted is False
    assert "forbidden" in receipt.reason


def test_unknown_field_rejected():
    receipt = apply_modulation("mystery_field", 1)
    assert receipt.accepted is False


def test_believe_threshold_c2_face_bounded():
    """C2 接收面：believe_threshold ∈ [0.4,0.6]（0.5 ± band）接受；越界 clip + CLIPPED。"""
    r = apply_modulation(ModulationField.BELIEVE_THRESHOLD, 0.6)
    assert r.accepted and r.applied_value == 0.6 and r.bound_check == "IN_BOUND"
    r_lo = apply_modulation(ModulationField.BELIEVE_THRESHOLD, 0.1)
    assert r_lo.accepted and r_lo.applied_value == BELIEVE_THRESHOLD_BOUND[0]
    assert r_lo.bound_check == "CLIPPED" and r_lo.requested_value == 0.1
    r_bad = apply_modulation(ModulationField.BELIEVE_THRESHOLD, None)
    assert r_bad.accepted is False
