"""对齐窗部分到达与迟到 revision（L02 §4.3/§10 test_alignment_partial.py；Q-L02-03）。

时序语义：W_align=4 → effective_time=t 的窗在 delivery = t+4 关闭（原子发布）；
回溯深度 = 1 窗（4 cycles）——窗关闭后 4 cycles 内迟到 → revision 帧；超出 → Unknown。
"""
from pathlib import Path

import pytest

from galatea.kernel.unknown import UnknownReason
from galatea.subject.sensorium.alignment import AlignmentWindow, LateBeyondLookback
from galatea.subject.sensorium.calibration import bind_calibration
from galatea.subject.sensorium.ingest import ingest
from galatea.subject.sensorium.pipeline import SensoriumPipeline
from galatea.subject.sensorium.ports import load_c0_sensorium_profile
from galatea.subject.sensorium.tests.conftest import extero_packet, intero_packet, proprio_packet

_ROOT = Path(__file__).resolve().parents[4]
_PROFILE_PATH = _ROOT / "config" / "profiles" / "c0_sensorium.profile.yaml"


def _pipeline() -> SensoriumPipeline:
    profile = load_c0_sensorium_profile(_PROFILE_PATH)
    return SensoriumPipeline(profile, bind_calibration(_PROFILE_PATH, profile.calibration_version))


def test_missing_carrier_partial_publish_no_zero_fill() -> None:
    """载体缺席 → 窗关闭时 MISSING_SIGNAL + 其余模态照常发布（不等待、不补零）。"""
    pipeline = _pipeline()
    missing_frames = []
    for delivery in range(5):   # t=0..1 的窗在 delivery 4..5 关闭（extero 从未到达）
        out = pipeline.process_cycle(delivery, [intero_packet(delivery), proprio_packet(delivery)])
        missing_frames.extend(out.frames)
        if delivery >= 4:
            assert any(
                u.reason is UnknownReason.MISSING_SIGNAL and "effective_time=0" in str(u.evidence_refs)
                for u in out.unknowns
            ), f"delivery {delivery}: extero absence must surface as MISSING_SIGNAL"
    # 部分对齐发布：INTERO/PROPRIO 帧存在，EXT_LOCAL_OBS 帧不存在（禁补零空帧）
    assert any(f.modality.value == "INTERO" for f in missing_frames)
    assert all(f.modality.value != "EXT_LOCAL_OBS" for f in missing_frames)


def test_late_within_window_no_missing() -> None:
    """extero 延迟 1 到达（窗未关）：正常入槽，无 MISSING_SIGNAL、无 revision。"""
    pipeline = _pipeline()
    out: object = None
    for delivery in range(5):
        out = pipeline.process_cycle(delivery, [
            extero_packet(max(0, delivery - 1)), intero_packet(delivery), proprio_packet(delivery),
        ])
    assert out is not None
    assert not any(u.reason is UnknownReason.MISSING_SIGNAL for u in out.unknowns)
    assert all(f.revision_of is None for f in out.frames)
    assert any(f.modality.value == "EXT_LOCAL_OBS" and f.effective_time == 0 for f in out.frames)


def test_late_revision_within_lookback() -> None:
    """窗关闭后、回溯深度内到达 → revision 帧（引用旧帧，envelope 不可变）。"""
    from galatea.subject.sensorium.tests.conftest import run_full_stream

    pipeline = _pipeline()
    run_full_stream(pipeline, 6)   # t=0/1 的窗随 extero 正常发布（delivery 4/5）
    out = pipeline.process_cycle(6, [extero_packet(0)])   # 迟到 2 cycles < 回溯 4
    revisions = [f for f in out.frames if f.revision_of is not None]
    assert revisions and all(r.modality.value == "EXT_LOCAL_OBS" for r in revisions)
    assert all(r.revision_of == "sf.EXT_LOCAL_OBS.0" for r in revisions)
    assert all(
        not isinstance(r.alignment_confidence, float) for r in revisions
    )   # 迟到 revision 置信降级 = typed Unknown（Q-L02-03）


def test_late_beyond_lookback_unknown_no_historical_frame() -> None:
    """超回溯深度迟到 → typed Unknown（禁历史帧改写）；其余窗照常。"""
    pipeline = _pipeline()
    for delivery in range(10):
        pipeline.process_cycle(delivery, [intero_packet(delivery), proprio_packet(delivery)])
    out = pipeline.process_cycle(10, [extero_packet(0)])   # 迟到 6 cycles ≥ 回溯 4
    assert all(f.modality.value != "EXT_LOCAL_OBS" or f.effective_time != 0 for f in out.frames)
    assert any(u.reason is UnknownReason.INSUFFICIENT_OBSERVATION for u in out.unknowns)


def test_window_submit_beyond_lookback_raises() -> None:
    profile = load_c0_sensorium_profile(_PROFILE_PATH)
    window = AlignmentWindow(profile)
    packet, text = extero_packet(0)
    signal = ingest(packet, text, profile)
    with pytest.raises(LateBeyondLookback):
        window.submit(signal, delivery_cycle=100)
