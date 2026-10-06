"""telemetry 直填拒绝（L05 §6 行 2 / §8 不变量 2：S1 面）。"""
import pytest

from galatea.subject.affect.ports import AffectCycleInputs, TelemetrySourceRejected


def test_telemetry_flagged_rejected() -> None:
    """telemetry 标记输入构造即拒（UnauthorizedInput(TELEMETRY_TO_AFFECT) 留痕面）。"""
    with pytest.raises(TelemetrySourceRejected):
        AffectCycleInputs(cycle=0, body_energy=0.5, telemetry_flagged=True)


def test_body_domain_enforced() -> None:
    """belief 值域 [0,1] 强制（越域 = 非法 BodyBelief 面）。"""
    with pytest.raises(ValueError):
        AffectCycleInputs(cycle=0, body_energy=1.5)
    with pytest.raises(ValueError):
        AffectCycleInputs(cycle=0, body_integrity=-0.1)


def test_load_must_be_zero_or_absent() -> None:
    """load ≡ 0（Q-L01-09⑥ schema 占位——非零即拒）。"""
    with pytest.raises(ValueError):
        AffectCycleInputs(cycle=0, body_energy=1.0, body_load=0.3)
    AffectCycleInputs(cycle=0, body_energy=1.0, body_load=0.0)
    AffectCycleInputs(cycle=0, body_energy=1.0)   # 缺席 → typed Unknown 保持
