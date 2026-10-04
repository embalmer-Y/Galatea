"""REV-0012 闭环补丁三（临时，不入库）：R4 EXT_EVENT 覆盖 + 真实损坏流容错。"""
from pathlib import Path

# test_determinism.py: append EXT_EVENT coverage + corruption tolerance tests
p = Path("galatea/subject/sensorium/tests/test_determinism.py")
t = p.read_text(encoding="utf-8")
t += '''

def test_ext_event_second_extero_face_coverage() -> None:
    """REV-0012 R4：第二外感受面 EXT_EVENT 全覆盖——五元属性 + 回执双绑定 + bit-exact。

    判据①"≥2 外感受"的两个面都必须有覆盖（评审前仅 EXT_LOCAL_OBS 有测试）。
    """
    pipeline = _pipeline()
    hazard = ["integrity_damage_event", "energy_depleted"]
    a_frames, b_frames = [], []
    for pipeline_out_sink in (a_frames, b_frames):
        p2 = _pipeline()
        for delivery in range(6):
            events = hazard if delivery == 2 else ["storm_hit"]
            out = p2.process_cycle(delivery, [intero_packet(delivery, events=events)])
            pipeline_out_sink.extend(
                (f.frame_id, f.content_digest) for f in out.frames if f.modality.value == "EXT_EVENT"
            )
    assert a_frames == b_frames                       # bit-exact
    assert len(a_frames) >= 6                         # 每个 delivery 都有事件帧（t=2 之前窗关闭延迟）
    from galatea.subject.sensorium.ports import ExtEventFeatures

    out = _pipeline().process_cycle(0, [intero_packet(0, events=hazard)])
    # 窗关闭滞后 W=4：t=0 帧在 delivery 4 发布——采集至窗关闭
    collector = _pipeline()
    ext_event_frames = []
    for delivery in range(5):
        o = collector.process_cycle(delivery, [intero_packet(delivery, events=hazard)])
        ext_event_frames.extend(f for f in o.frames if f.modality.value == "EXT_EVENT")
    frame = ext_event_frames[0]
    assert isinstance(frame.features, ExtEventFeatures)
    assert frame.features.events == tuple(sorted(hazard))
    assert frame.source_received_ids                  # 来源
    assert frame.formed_time >= frame.effective_time  # 时间分离
    assert frame.quality.completeness == 1.0          # 质量
    assert frame.gain.applied_factor == 1.0           # 增益
    receipt = next(
        r for o in [out] for r in o.formation_receipts
    )   # 事件帧回执存在（EXT_EVENT 面）
    event_receipts = [
        r for o in [out] for r in o.formation_receipts if r.frame_id.startswith("sf.EXT_EVENT")
    ] or [r for r in collector_receipts() if r.frame_id.startswith("sf.EXT_EVENT")]
    assert event_receipts and event_receipts[0].frame_digest == frame.content_digest


def collector_receipts() -> list:   # pragma: no cover - R4 辅助（窗关闭后的事件回执）
    from galatea.subject.sensorium.tests.conftest import run_full_stream

    hazard = ["integrity_damage_event", "energy_depleted"]
    p2 = _pipeline()
    receipts: list = []
    for delivery in range(5):
        o = p2.process_cycle(delivery, [intero_packet(delivery, events=hazard)])
        receipts.extend(r for r in o.formation_receipts if r.frame_id.startswith("sf.EXT_EVENT"))
    return receipts


def test_corrupted_packet_typed_unknown_no_crash() -> None:
    """REV-0012 R3：损坏包（真实 0.01 损坏率语义）→ typed unknown 留痕，cycle 不崩止。"""
    pipeline = _pipeline()
    good = intero_packet(0)
    broken_packet, _good_text = intero_packet(1)
    corrupted_text = '{"kind":"interoceptive_state","energy":0.5,"integ'   # 截断 = 不可解码
    out = pipeline.process_cycle(0, [good, (broken_packet, corrupted_text), proprio_packet(0)])
    assert any(u.reason.value == "CALIBRATION_UNCERTAIN" for u in out.unknowns)   # 损坏留痕
    assert any(f.modality.value == "INTERO" for f in out.frames)                  # 好包照常形成
    assert not any(f.modality.value == "INTERO" and f.effective_time == 1 for f in out.frames)  # 损坏包不产帧
'''
p.write_text(t, encoding="utf-8")
print("R3/R4 tests added")
