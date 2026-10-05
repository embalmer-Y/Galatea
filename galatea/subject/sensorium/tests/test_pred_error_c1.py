"""感觉层预测误差 C1 接线测试（L02 §4.5/§10；Q-L02-06 formed_features_flat）。

P09 纪律：本测试在 sensorium 平面内自足（不 import 知觉面装置——总线忠实流
装置在此内联，与生产同源于冻结 m0 profile 延迟表）。
"""
import pytest

from galatea.subject.models.ports import ModelPrediction
from galatea.subject.sensorium.calibration import bind_calibration
from galatea.subject.sensorium.pipeline import SensoriumPipeline
from galatea.subject.sensorium.ports import load_c0_sensorium_profile
from galatea.subject.sensorium.pred_error import flatten_frame, sense_errors
from galatea.subject.sensorium.tests.conftest import extero_packet, intero_packet, proprio_packet, time_basis
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[4]


def _frames_at(window, t: int, energy: float = 0.8):
    """总线忠实流（extero 延迟 1 / intero-proprio 零延迟；W_align=4 关闭）→ t 帧组。"""
    profile = load_c0_sensorium_profile()
    calibration = bind_calibration(
        _ROOT / "config" / "profiles" / "c0_sensorium.profile.yaml", profile.calibration_version
    )
    pipeline = SensoriumPipeline(profile, calibration, time_basis())
    collected: dict[int, list] = {}
    for delivery in range(t + 5):
        packets = [intero_packet(delivery, energy=energy), proprio_packet(delivery)]
        if delivery >= 1:
            packets.append(extero_packet(delivery, window=window))
        out = pipeline.process_cycle(delivery, packets)
        for frame in out.frames:
            collected.setdefault(frame.effective_time, []).append(frame)
    return tuple(collected.get(t, ()))


def _uniform_window(center_value: float) -> list[list[float]]:
    return [
        [center_value if (r == 2 and c == 2) else 0.0 for c in range(5)]
        for r in range(5)
    ]


def test_extero_window_25_dims():
    """EXT_LOCAL_OBS = 5×5 展平 25 维（Q-L02-06）。"""
    extero = next(f for f in _frames_at(_uniform_window(0.9), 7) if f.modality.value == "EXT_LOCAL_OBS")
    vec = flatten_frame(extero)
    assert len(vec) == 25
    assert vec[12] == pytest.approx(0.9)      # 中心格（行优先展平）


def test_proprio_one_hot_4_dims():
    proprio = next(f for f in _frames_at(_uniform_window(0.9), 7) if f.modality.value == "PROPRIO")
    assert flatten_frame(proprio) == (1.0, 0.0, 0.0, 0.0)   # N 域首 token


def test_intero_4_scalars():
    intero = next(f for f in _frames_at(_uniform_window(0.9), 7, energy=0.62) if f.modality.value == "INTERO")
    assert flatten_frame(intero) == (0.62, 1.0, 0.0, 0.0)


def test_residual_real_computation():
    """真实残差 = observed − expected（float64 同维差；偏移预测 → 逐格残差）。"""
    frames = _frames_at(_uniform_window(0.5), 7)
    prediction = ModelPrediction(
        prediction_id="mp.t7", target_modality="EXT_LOCAL_OBS",
        expected_window=tuple(tuple(float(v) for v in row) for row in _uniform_window(0.5)),
        valid_time=7,
    )
    errors, unmatched = sense_errors((prediction,), frames)
    assert not unmatched
    assert len(errors) == 1
    assert all(abs(r) < 1e-9 for r in errors[0].residual)
    shifted = [[0.6 if (r == 2 and c == 2) else 0.0 for c in range(5)] for r in range(5)]
    prediction2 = ModelPrediction(
        prediction_id="mp.t7b", target_modality="EXT_LOCAL_OBS",
        expected_window=tuple(tuple(float(v) for v in row) for row in shifted),
        valid_time=7,
    )
    errors2, _ = sense_errors((prediction2,), frames)
    assert errors2[0].residual[12] == pytest.approx(-0.1)


def test_unmatched_prediction_recorded_not_forged():
    """预测无匹配帧 → unmatched 留痕（禁伪造零误差，C0 成规）。"""
    frames = _frames_at(_uniform_window(0.5), 7)
    prediction = ModelPrediction(
        prediction_id="mp.t99", target_modality="INTERO",
        expected_body=(0.8, 1.0), valid_time=99,
    )
    errors, unmatched = sense_errors((prediction,), frames)
    assert not errors
    assert unmatched == ("mp.t99",)


def test_no_predictions_empty():
    """无预测 → 空误差（C0 成规保持；禁凭空误差）。"""
    frames = _frames_at(_uniform_window(0.5), 7)
    assert sense_errors((), frames) == ((), ())
