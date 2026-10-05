"""全栈 bit-exact 集成测试（真实总线忠实流：sensorium → perception → world →
prediction → 感觉层误差；双跑 digest 恒等）。"""
import json

import pytest

from galatea.subject.c1profile import load_c1_profile
from galatea.subject.models.body import build_body_belief
from galatea.subject.models.prediction import predict_body, predict_orientation, predict_window
from galatea.subject.models.world import WorldModel
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
from galatea.subject.sensorium.pred_error import sense_errors


def _run_stream(cycles: int = 24) -> str:
    """真实 schema 流全栈运行（24 cycles = 6 窗批）；返回全产物 digest 序列。"""
    prof = load_c1_profile()
    sensorium = make_sensorium()
    perception = PerceptionPipeline(prof)
    world = WorldModel(prof, run_id="R")
    window = uniform_window(0.9)
    marks: list[str] = []
    body = None
    for delivery in range(cycles):
        packets = [intero_payload(delivery), proprio_payload(delivery)]
        if delivery >= 1:
            packets.append(make_packet(
                CARRIER_EXTERO, delivery, {"kind": "observation_window", "window": window}
            ))
        out = sensorium.process_cycle(delivery, packets)
        by_t: dict[int, list] = {}
        for frame in out.frames:
            by_t.setdefault(frame.effective_time, []).append(frame)
        for t in sorted(by_t):
            frames = tuple(by_t[t])
            perc = perception.process_window(t, frames)
            intero_frame = next((f for f in frames if f.modality.value == "INTERO"), None)
            proprio_frame = next((f for f in frames if f.modality.value == "PROPRIO"), None)
            if intero_frame is not None:
                body = build_body_belief(intero_frame, proprio_frame, "body.R", t)
            world_belief = world.update(
                t, perc.cells, move_receipts=(), forage_receipts=(), requested_moves=()
            )
            preds = (
                predict_body(body, t + 1)
                + predict_orientation(body, t + 1)
                + predict_window(world_belief, prof, t + 1)
            )
            errors, unmatched = sense_errors(preds, frames)
            marks.append(json.dumps({
                "t": t,
                "beliefs": [b.digest() for b in perc.beliefs],
                "abstains": [a.abstain_id for a in perc.abstains],
                "world_digest": world_belief.digest(),
                "errors": [(e.frame_id, e.residual) for e in errors],
                "unmatched": list(unmatched),
            }, sort_keys=True))
    return json.dumps(marks, sort_keys=True)


def test_stream_double_run_bit_exact():
    """同流双跑 → 全栈产物 digest 逐位恒等（C1 全组件确定性）。"""
    assert _run_stream(24) == _run_stream(24)


def test_stream_produces_real_products():
    """预测/误差/对象非空产物面（禁空转探针，INC-08 成规）。"""
    prof = load_c1_profile()
    _, _, belief, _ = world_with_observation_helper()
    preds = predict_window(belief, prof, 8)
    assert preds
    errors, unmatched = sense_errors(preds, frames_at(uniform_window(0.9), 7))
    assert errors or unmatched
    # 身体持续性预测与同拍帧匹配 → 真实残差（observed 0.8 − expected 0.62 = +0.18）
    errors2, _ = sense_errors(predict_body(_body(), 7), frames_at(uniform_window(0.9), 7))
    assert errors2
    assert errors2[0].residual[0] == pytest.approx(0.8 - 0.62)


def world_with_observation_helper():
    from galatea.subject.models.tests.conftest import world_with_observation

    return world_with_observation(7, 0.9)


def _body():
    from galatea.subject.models.body import build_body_belief

    frames = frames_at(uniform_window(0.9), 7, energy=0.62)
    intero = next(f for f in frames if f.modality.value == "INTERO")
    proprio = next(f for f in frames if f.modality.value == "PROPRIO")
    return build_body_belief(intero, proprio, "body.R", 7)
