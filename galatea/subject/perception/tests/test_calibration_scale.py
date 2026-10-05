"""置信标度与校准测试（L03 §4.3/§7 calibration_scale 行；ECE 接口手算复核）。"""
import pytest

from galatea.kernel.unknown import NotTypedUnknown, Unknown, UnknownReason
from galatea.subject.perception.confidence import (
    CalibrationMismatch,
    CalibrationScale,
    ece_equal_mass,
    load_calibration_version,
)


def test_calibration_version_from_frozen_profile():
    """c1-static-v1 单版本延续（Q-L02-01）；版本治理 = profile 重冻结。"""
    scale = load_calibration_version()
    assert scale.version_id == "c1-static-v1"


def test_scale_rejects_out_of_bounds():
    scale = CalibrationScale(version_id="c1-static-v1")
    with pytest.raises(NotTypedUnknown):
        scale.check_value(1.5)
    with pytest.raises(NotTypedUnknown):
        scale.check_value(float("nan"))


def test_scale_accepts_bounded_and_unknown():
    scale = CalibrationScale(version_id="c1-static-v1")
    assert scale.check_value(0.4) == 0.4
    unk = Unknown(reason=UnknownReason.OOD, evidence_refs=(), detail=None,
                  detected_by="t", virtual_time=0)
    assert scale.check_value(unk) is unk


def test_ece_perfect_calibration_zero():
    """完美校准：置信 1.0 且全部正确 → 每箱 |acc − conf| = 0。"""
    n = 60
    confidences = tuple(1.0 for _ in range(n))
    correct = tuple(True for _ in range(n))
    assert ece_equal_mass(confidences, correct) == pytest.approx(0.0)


def test_ece_hand_check():
    """手算复核：两箱等质量——箱 1（0.2×20）acc 0.5、箱 2（0.8×40）acc 0.75。"""
    confidences = (0.2,) * 20 + (0.8,) * 40
    correct = (True, False) * 10 + (True, False, True, True) * 10
    ece = ece_equal_mass(confidences, correct)
    expected = (20 / 60) * abs(0.5 - 0.2) + (40 / 60) * abs(0.75 - 0.8)
    assert ece == pytest.approx(expected, abs=1e-12)


def test_ece_length_mismatch():
    with pytest.raises(ValueError):
        ece_equal_mass((0.5,), (True, False))
