"""管线状态序列化测试（Q-L13-17：跨重启状态连续性的机械证明）。

核心判据：崩溃前消耗内感受流 → snapshot → 新管线 restore → 续帧的 energy_rate
= 正确派生差分（**未恢复的 fresh 管线同帧只能产 INSUFFICIENT_OBSERVATION Unknown**
——_prev_energy 基线缺失）。窗内 pending 信号随快照存活（对齐窗语义不断）。
"""
import json
from pathlib import Path

from galatea.subject.sensorium.calibration import bind_calibration
from galatea.subject.sensorium.pipeline import SensoriumPipeline
from galatea.subject.sensorium.ports import load_c0_sensorium_profile
from galatea.subject.sensorium.tests.conftest import intero_packet, time_basis

_ROOT = Path(__file__).resolve().parents[4]
_PROFILE_PATH = _ROOT / "config" / "profiles" / "c0_sensorium.profile.yaml"


def _pipeline() -> SensoriumPipeline:
    profile = load_c0_sensorium_profile(_PROFILE_PATH)
    return SensoriumPipeline(profile, bind_calibration(_PROFILE_PATH, profile.calibration_version),
                             time_basis())


def _energy_packet(cycle: int, energy: float):
    from galatea.subject.sensorium.tests.conftest import CARRIER_INTERO, make_packet
    payload = {"kind": "interoceptive_state", "energy": energy,
               "integrity": 1.0, "events": []}
    return make_packet(CARRIER_INTERO, cycle, payload)


def test_state_continuity_across_restore() -> None:
    pa = _pipeline()
    energies = [1.0, 0.9, 0.8, 0.7]
    for cycle, e in enumerate(energies):
        pkt, text = _energy_packet(cycle, e)
        pa.process_cycle(cycle, [(pkt, text)])
    state = pa.snapshot()
    # JSON round-trip（序列化纪律：可落盘可复算）
    state_rt = json.loads(json.dumps(state, sort_keys=True))
    assert state_rt["schema"] == "pipeline_state.v1"
    assert state_rt == state                        # 同状态同快照（确定性）
    digest_a = json.dumps(state_rt, sort_keys=True)

    # 恢复管线：续第 4 拍（energy 0.6）——恢复后首窗即出正确差分
    pb = _pipeline()
    pb.restore_snapshot(state_rt)
    assert json.dumps(pb.snapshot(), sort_keys=True) == digest_a   # 恢复态 ≡ 快照态
    pkt, text = _energy_packet(4, 0.6)
    out = pb.process_cycle(4, [(pkt, text)])
    rates = [f.features.energy_rate for o in [out] for f in o.frames
             if isinstance(getattr(f.features, "energy_rate", None), (int, float))]
    # 对齐窗延迟出帧（due = t0 ≤ delivery−W−1）——续拍至窗排出
    for cycle in range(5, 9):
        pkt, text = _energy_packet(cycle, 0.6)
        out = pb.process_cycle(cycle, [(pkt, text)])
        rates += [f.features.energy_rate for f in out.frames
                  if isinstance(getattr(f.features, "energy_rate", None), (int, float))]
    # 恢复基线 _prev_energy=0.7（崩溃前末帧）→ 后续差分 = 0.6−0.7 = −0.1（连续！）
    # （t0=0 的 Unknown 为合法首帧语义——恢复后其余帧差分全数值）
    assert rates and all(abs(r - (-0.1)) < 1e-9 for r in rates), rates


def test_fresh_pipeline_same_frame_is_unknown() -> None:
    """反证锚：未恢复的 fresh 管线同帧 energy_rate = Unknown（基线缺失）——恢复的价值所在。"""
    pf = _pipeline()
    pkt, text = _energy_packet(4, 0.6)
    out = pf.process_cycle(4, [(pkt, text)])
    assert not [f for f in out.frames
                if isinstance(getattr(f.features, "energy_rate", None), (int, float))]


def test_pending_window_survives_snapshot() -> None:
    """窗内 pending 信号随快照存活：快照前投递的包在恢复后正常成帧（对齐窗语义不断）。"""
    pa = _pipeline()
    pkt, text = intero_packet(0)
    pa.process_cycle(0, [(pkt, text)])              # t0=0 入窗（W=4 未关）
    state = json.loads(json.dumps(pa.snapshot(), sort_keys=True))
    assert state["window"], "pending window empty at snapshot——窗态未被序列化"
    pb = _pipeline()
    pb.restore_snapshot(state)
    # 续拍至窗关闭：t0=0 的帧在恢复侧正常形成
    formed = False
    for cycle in range(1, 6):
        pkt2, text2 = intero_packet(cycle)
        out = pb.process_cycle(cycle, [(pkt2, text2)])
        if any(f.effective_time == 0 for f in out.frames):
            formed = True
    assert formed
