"""感觉/知觉解离测试（L03 §1 C1 硬条件/§7 dissociation 行）。

解离双向可证：
(a) 破坏知觉（注入知觉故障：OOD 域出）→ 感觉帧形成完整性**不变**（帧数/回执/
    增益绑定照常——audit 通过）；
(b) 降质感觉输入（资源消失 → 弱信号）→ 知觉正确率与置信度**同步下降**，
    而感觉形成完整性仍不变。
"""
from galatea.subject.perception.pipeline import PerceptionPipeline
from galatea.subject.perception.tests.conftest import (
    frames_at,
    intero_payload,
    make_packet,
    make_sensorium,
    proprio_payload,
    uniform_window,
)
from galatea.subject.sensorium.ingest import CARRIER_EXTERO
from galatea.subject.sensorium.pipeline import audit


def _formation_metrics(window: list[list[float]], cycles: int = 9) -> tuple[int, int]:
    """全流形成面指标（帧数、回执数；逐 cycle audit）。"""
    sensorium = make_sensorium()
    total_frames = 0
    total_receipts = 0
    for delivery in range(cycles):
        packets = [intero_payload(delivery), proprio_payload(delivery)]
        if delivery >= 1:
            packets.append(make_packet(
                CARRIER_EXTERO, delivery, {"kind": "observation_window", "window": window}
            ))
        out = sensorium.process_cycle(delivery, packets)
        audit(out.frames, out.formation_receipts, out.gain_receipts)
        total_frames += len(out.frames)
        total_receipts += len(out.formation_receipts)
    return total_frames, total_receipts


def test_broken_perception_does_not_touch_formation():
    """(a) OOD 输入下：感觉形成完整性不变（audit 通过 + 帧数与正常流一致）。"""
    broken_window = uniform_window(0.9)
    broken_window[0][0] = 5.0          # OOD 域出（知觉侧故障注入）
    good_frames, good_receipts = _formation_metrics(uniform_window(0.9))
    broken_frames, broken_receipts = _formation_metrics(broken_window)
    assert good_frames == broken_frames > 0
    assert good_receipts == broken_receipts > 0


def test_degraded_input_lowers_perceptual_confidence_but_not_formation():
    """(b) 降质输入：资源消失（0.9→0.0）→ 对象信念消失/置信下降，形成面照常。"""
    pipeline = PerceptionPipeline()
    strong = pipeline.process_window(7, frames_at(uniform_window(0.9), 7))
    weak = pipeline.process_window(7, frames_at(uniform_window(0.0), 7))
    assert len(strong.objects) == 1
    assert strong.objects[0].posterior > 0.9
    assert not weak.objects           # 知觉侧选择性失败（低于阈值 → abstain）
    assert weak.abstains
    good_frames, _ = _formation_metrics(uniform_window(0.0))
    assert good_frames > 0            # 感觉形成完整性不变
