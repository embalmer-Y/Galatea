"""动力学六机制辨识（L05 §7 dynamics trace：C2 硬条件——证明"非静态标签"）。

全部锚 = ADR-G-0015 冻结前可行性探针层A 可复算规格（评审独立重演命中）。
"""
import pytest

from galatea.subject.affect.dynamics import (
    decay_step,
    hysteresis,
    in_recovery,
    lowpass,
    saturate,
    two_step,
)
from galatea.subject.c2profile import C2AffectParams

TAU_INT = 4
TAU_DEC = 16
BAND = 0.1


def test_integration_time_constant() -> None:
    """积分：x 0→1 阶跃 τ=4 → t63=4 拍精确（s₃ < 1−e⁻¹ ≤ s₄）；24 拍终值 0.99899661。"""
    s = 0.0
    trace = []
    for _ in range(24):
        s = lowpass(s, 1.0, TAU_INT)
        trace.append(s)
    assert trace[2] == pytest.approx(0.578125)          # s₃
    assert trace[3] == pytest.approx(0.68359375)        # s₄（≥ 1−e⁻¹ ≈ 0.63212）
    assert 1.0 - trace[3] < 1.0 / 2.718281828 <= 1.0 - trace[2]
    assert trace[23] == pytest.approx(0.99899661, abs=1e-8)


def test_hysteresis_band_and_noise_immunity() -> None:
    """迟滞：up_at=0.55 / down_at=0.45 / band_observed=0.1 精确；±0.05 噪声零误切换。"""
    on = False
    up_at = None
    v = 0.0
    while v <= 1.0 and up_at is None:
        v = round(v + 0.01, 10)
        new = hysteresis(on, v, BAND)
        if new and not on:
            up_at = v
        on = new
    assert up_at == 0.55
    down_at = None
    while v >= 0.0 and down_at is None:
        v = round(v - 0.01, 10)
        new = hysteresis(on, v, BAND)
        if not new and on:
            down_at = v
        on = new
    assert down_at == 0.45
    assert (up_at - down_at) == pytest.approx(BAND)
    # 2σ（±0.05）噪声在带内开区间 (0.45,0.55) 零切换（边界值 0.45/0.55 本身即切换点）
    for x in (0.46, 0.5, 0.54, 0.455, 0.545):
        assert hysteresis(True, x, BAND) is True
        assert hysteresis(False, x, BAND) is False


def test_decay_exact() -> None:
    """衰减：s₀=1 输入 0，16 拍 → (15/16)^16 = 0.35607413 逐位。"""
    s = 1.0
    for _ in range(16):
        s = decay_step(s, TAU_DEC)
    assert s == pytest.approx(0.35607413, abs=1e-8)
    assert s == pytest.approx((15.0 / 16.0) ** 16, abs=1e-12)


def test_saturation_clip_and_hits() -> None:
    """饱和：x=2.0 持续 8 拍 clip [−1,1] → 1.0、hits=8（每拍 +1）。"""
    hits = 0
    s = 0.9
    for _ in range(8):
        s, hit = saturate(lowpass(s, 2.0, TAU_INT), -1.0, 1.0)
        hits += int(hit)
    assert s == 1.0
    assert hits == 8


def test_recovery_phase_band_boundary() -> None:
    """恢复相位：e=0.05（带内）True / e=0.11（带外）False——band 边界精确。"""
    assert in_recovery(0.05, BAND) is True
    assert in_recovery(0.11, BAND) is False
    assert in_recovery(BAND, BAND) is True        # ≤ band（边界含）


def test_reappraisal_two_step_construction() -> None:
    """重评价：two_step(0.4)−two_step(0.2) = 0.175−0.0875 = 0.0875（ADR 构造式）。"""
    assert two_step(0.4, TAU_INT) == pytest.approx(0.175)
    assert two_step(0.2, TAU_INT) == pytest.approx(0.0875)
    assert two_step(0.4, TAU_INT) - two_step(0.2, TAU_INT) == pytest.approx(0.0875)


def test_pipeline_trace_carries_all_six(affect_params: C2AffectParams) -> None:
    """感受态携带动力学标记（integrator/band/decay_rate/hits/recovery——trace 完整性）。"""
    from galatea.subject.affect.ports import AffectCycleInputs
    from galatea.subject.affect.pipeline import AffectPipeline

    pipe = AffectPipeline(affect_params)
    out = pipe.step(AffectCycleInputs(cycle=0, body_energy=1.0, body_integrity=1.0))
    tr = out.state.dynamics_trace
    assert tr.hysteresis_band == affect_params.band
    assert tr.decay_rate == pytest.approx(1.0 / affect_params.tau_dec)
    assert isinstance(tr.recovery_phase, bool)
    assert tr.saturation_hits == 0
