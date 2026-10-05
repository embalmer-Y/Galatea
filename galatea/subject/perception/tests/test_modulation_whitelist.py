"""调制白名单测试（L03 §4.5/§7 modulation_whitelist 行；C1 无调制源 → 恒拒）。"""
import pytest

from galatea.subject.perception.modulation import (
    FORBIDDEN_FIELDS,
    ModulationField,
    ModulationRejected,
    apply_modulation,
)


@pytest.mark.parametrize("field", [f.value for f in ModulationField])
def test_whitelisted_fields_rejected_c1(field):
    """白名单内字段在 C1 同样拒绝——无调制源（L05 归 C2），拒绝留痕。"""
    with pytest.raises(ModulationRejected) as info:
        apply_modulation(field, 0.7)
    assert "C1" in str(info.value)


@pytest.mark.parametrize("field", FORBIDDEN_FIELDS)
def test_forbidden_fields_never_acceptable(field):
    """禁改字段（输入特征/标度/层级/历史）恒拒且不抛调制面异常（白名单外路径）。"""
    receipt = apply_modulation(field, object())
    assert receipt.accepted is False
    assert "forbidden" in receipt.reason


def test_unknown_field_rejected():
    receipt = apply_modulation("mystery_field", 1)
    assert receipt.accepted is False
