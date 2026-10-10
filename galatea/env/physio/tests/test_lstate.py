"""L0–L5 状态机全转移测试（Q-L10-03/08/11 冻结语义；含 REV-0025 探针 12 锚全量）。"""
import pytest

from galatea.env.physio.lstate import (
    ESTOP_EVENT,
    LStateViolation,
    PhysioLStateMachine,
)

_DWELL = 64


def _always_ok(_level: int) -> bool:
    return True


def _always_no(_level: int) -> bool:
    return False


def test_l1_rejects_task_and_l2_grant_climb() -> None:
    sm = PhysioLStateMachine(_DWELL)
    assert sm.submit("calibrate_sensors", 1).outcome == "REJECTED_PASSIVE"
    sm.grant(2, _DWELL, _always_ok)
    assert sm.level == 2
    assert sm.submit("calibrate_sensors", _DWELL).outcome == "EXECUTED_CALIB"
    assert sm.submit("calibrate_sensors", _DWELL).effects == "calibration_only"


def test_no_skip_and_dwell_enforced() -> None:
    sm = PhysioLStateMachine(_DWELL)
    with pytest.raises(LStateViolation, match="no-skip"):
        sm.grant(3, _DWELL, _always_ok)          # L1→L3 禁跳
    with pytest.raises(LStateViolation, match="min dwell"):
        sm.grant(2, _DWELL - 1, _always_ok)      # 部署起算驻留不足
    sm.grant(2, _DWELL, _always_ok)
    with pytest.raises(LStateViolation, match="min dwell"):
        sm.grant(3, 2 * _DWELL - 1, _always_ok)  # L2 驻留 63 < 64
    sm.grant(3, 2 * _DWELL, _always_ok)
    assert sm.level == 3


def test_authz_validator_gates_grant() -> None:
    sm = PhysioLStateMachine(_DWELL)
    with pytest.raises(LStateViolation, match="authorization invalid"):
        sm.grant(2, _DWELL, _always_no)


def test_shadow_compute_only_at_l3_and_effects_honest() -> None:
    sm = PhysioLStateMachine(_DWELL)
    sm.grant(2, _DWELL, _always_ok)
    assert sm.submit("shadow_compute", _DWELL).outcome == "REJECTED_CAPABILITY"
    sm.grant(3, 2 * _DWELL, _always_ok)
    decision = sm.submit("shadow_compute", 2 * _DWELL)
    assert decision.outcome == "EXECUTED_COMPUTE"
    assert decision.effects == "compute_only"    # L3 不执行（L10 §4.6 字面）


def test_fault_downgrades_to_l1_and_requires_reauth() -> None:
    sm = PhysioLStateMachine(_DWELL)
    sm.grant(2, _DWELL, _always_ok)
    assert sm.fault(2 * _DWELL) == "DOWNGRADED_L1"
    assert sm.level == 1
    assert sm.submit("calibrate_sensors", 2 * _DWELL).outcome == "REJECTED_AUTH_REQUIRED"
    with pytest.raises(LStateViolation, match="re-authorization required"):
        sm.grant(2, 3 * _DWELL, _always_ok)      # 未再授权前禁升
    assert sm.reauthorize(3 * _DWELL) == "REAUTH_L1"
    with pytest.raises(LStateViolation, match="min dwell"):
        sm.grant(2, 3 * _DWELL - 1, _always_ok)  # L1 驻留自降级时刻起算：63 < 64
    sm.grant(2, 4 * _DWELL, _always_ok)          # 128→256 驻留远足
    assert sm.level == 2


def test_estop_floor_and_no_downgrade_below_l0() -> None:
    sm = PhysioLStateMachine(_DWELL)
    assert sm.estop(5) == ESTOP_EVENT
    assert sm.level == 0
    assert sm.submit("selfcheck", 6).outcome == "REJECTED_ESTOP"
    assert sm.fault(7) == "NOOP_AT_L0"           # 地板不可降
    assert sm.reauthorize(8) == "REAUTH_L1"      # 唯一出口 = L1
    assert sm.level == 1
    assert sm.submit("actuate", 9).outcome == "REJECTED_PASSIVE"


def test_estop_upper_bound_one_cycle_and_partial_execution_honest() -> None:
    sm = PhysioLStateMachine(_DWELL)
    sm.grant(2, _DWELL, _always_ok)
    first = sm.submit("calibrate_sensors", 2 * _DWELL)      # 在途
    assert first.outcome == "EXECUTED_CALIB"
    assert sm.estop(2 * _DWELL + 1) == ESTOP_EVENT
    settled = sm.apply_estop_to_in_flight(2 * _DWELL + 1)
    assert len(settled) == 1
    assert settled[0].outcome == "PARTIAL_EXECUTED_ESTOP"   # 禁视为完成（Q-L10-08②）
    assert "requested=calibrate_sensors" in settled[0].detail
    assert sm.estop_latency_cycles(2 * _DWELL, 2 * _DWELL + 1) <= 1


def test_mw0_domain_isolation_at_every_level() -> None:
    for initial in (1,):
        sm = PhysioLStateMachine(_DWELL)
        assert initial == 1
        for primitive in ("move", "forage", "eat", "rest", "look"):
            decision = sm.submit(primitive, 0)
            assert decision.outcome == "REJECTED_DOMAIN_ISOLATION"
        sm.grant(2, _DWELL, _always_ok)
        sm.grant(3, 2 * _DWELL, _always_ok)
        for primitive in ("move", "forage"):
            assert sm.submit(primitive, 2 * _DWELL).outcome == "REJECTED_DOMAIN_ISOLATION"


def test_l4_l5_capability_sets_frozen() -> None:
    sm = PhysioLStateMachine(_DWELL)
    sm.grant(2, _DWELL, _always_ok)
    sm.grant(3, 2 * _DWELL, _always_ok)
    sm.grant(4, 3 * _DWELL, _always_ok)
    assert sm.submit("actuate_limited", 3 * _DWELL).effects == "physical_limited"
    assert sm.submit("actuate", 3 * _DWELL).outcome == "REJECTED_CAPABILITY"
    sm.grant(5, 4 * _DWELL, _always_ok)
    assert sm.submit("actuate", 4 * _DWELL).effects == "physical"


def test_initial_level_constrained() -> None:
    with pytest.raises(LStateViolation, match="initial_level"):
        PhysioLStateMachine(_DWELL, initial_level=3)
