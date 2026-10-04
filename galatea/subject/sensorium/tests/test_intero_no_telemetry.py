"""内感受非 telemetry 面（L02 §8 不变量 4/§10 test_intero_no_telemetry.py）。

断言：内感受只来自 RECEIVED 包经形成面（telemetry 直填/裸 dict 注入全拒）；
OOD 越域值照常形成并标记（不推断不丢弃）。
"""
from pathlib import Path

import pytest

from galatea.subject.sensorium.calibration import bind_calibration
from galatea.subject.sensorium.form_intero import form_intero
from galatea.subject.sensorium.gain import C0_GAIN
from galatea.subject.sensorium.ingest import ingest
from galatea.subject.sensorium.ports import load_c0_sensorium_profile
from galatea.subject.sensorium.tests.conftest import intero_packet, time_basis
from galatea.kernel.unknown import UnknownReason

_ROOT = Path(__file__).resolve().parents[4]
_PROFILE_PATH = _ROOT / "config" / "profiles" / "c0_sensorium.profile.yaml"


def _profile_and_calibration():
    profile = load_c0_sensorium_profile(_PROFILE_PATH)
    return profile, bind_calibration(_PROFILE_PATH, profile.calibration_version)


def test_raw_telemetry_dict_cannot_form() -> None:
    """裸 telemetry dict（非 RECEIVED 包）不可达形成面——ingest 是唯一入口。

    schema 面：kind 必须与载体匹配（telemetry/异构载荷禁注入，Q-G00-12① 载体纪律）。
    """
    profile, _calibration = _profile_and_calibration()
    packet, _text = intero_packet(0)
    with pytest.raises(Exception, match="kind"):
        ingest(packet, '{"kind":"telemetry_direct","energy":0.42,"integrity":1.0,"events":[]}', profile, time_basis())
    with pytest.raises(Exception, match="missing fields"):
        ingest(packet, '{"kind":"interoceptive_state"}', profile, time_basis())


def test_ood_level_marked_not_dropped() -> None:
    """energy 越域（>1）→ 照常形成 + OOD unknown（L02 §6：不推断、不丢弃）。"""
    profile, calibration = _profile_and_calibration()
    packet, text = intero_packet(0, energy=1.5)
    signal = ingest(packet, text, profile, time_basis())
    frame, unknowns, _energy = form_intero(
        signal, 0, calibration.version_id, C0_GAIN, prev_energy_level=None,
    )
    assert frame.features.energy_level == 1.5                # 照常形成
    assert any(u.reason is UnknownReason.OOD for u in unknowns)


def test_intero_sensations_zero_new_thresholds() -> None:
    """四 sensation 零新阈值：离散事件直接转写世界侧冻结定义（Q-L01-08/Q-L01-09⑤）。"""
    profile, calibration = _profile_and_calibration()
    packet, text = intero_packet(0, events=["integrity_damage_event", "energy_depleted"])
    signal = ingest(packet, text, profile, time_basis())
    frame, _unknowns, _energy = form_intero(
        signal, 0, calibration.version_id, C0_GAIN, prev_energy_level=0.5,
    )
    assert frame.features.damage_event is True
    assert frame.features.energy_depleted is True
    assert isinstance(frame.features.energy_rate, float)   # 有前值 → 数值差分（REV-0012 R5：断言不得恒真）
    assert abs(frame.features.energy_rate - 0.3) < 1e-9    # 0.8（载荷默认）− 0.5（前值）
