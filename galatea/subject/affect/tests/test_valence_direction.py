"""valence 方向性（L05 §7 unit：积分/迟滞算子、valence 方向性计算——确定性、可手算）。

探针锚（ADR-G-0015 层B）：偶拍 −0.01 步进的 E → 固定点 = −0.0025/0.4375
= −0.0057142857…（一阶低通解析解；实测逼近）。
"""
import pytest

from galatea.subject.affect.ports import AffectCycleInputs
from galatea.subject.affect.pipeline import AffectPipeline
from galatea.subject.affect.valence import valence_step
from galatea.subject.c2profile import C2AffectParams


def test_improvement_positive_worsening_negative(affect_params: C2AffectParams) -> None:
    """改善 → raw 正；恶化 → raw 负（§4.2 字面）。"""
    up = valence_step(0.0, error_now=0.10, error_prev=0.20, tau_int=affect_params.tau_int)
    assert up.raw == pytest.approx(0.10)
    down = valence_step(0.0, error_now=0.20, error_prev=0.10, tau_int=affect_params.tau_int)
    assert down.raw == pytest.approx(-0.10)
    # 平滑方向一致（零初值单步：raw/τ_int）
    assert up.smoothed == pytest.approx(0.10 / affect_params.tau_int)


def test_probe_layer_b_fixed_point(affect_params: C2AffectParams) -> None:
    """层B 探针场景：偶拍步进 −0.01 → 固定点 −0.0025/0.4375（解析）逐位逼近。"""
    pipe = AffectPipeline(affect_params)
    outs = []
    for c in range(64):
        energy = 1.0 - 0.01 * (c // 2 + 1) if c < 36 else 0.82
        outs.append(pipe.step(AffectCycleInputs(cycle=c, body_energy=energy, body_integrity=1.0)))
    fixed_point = -0.0025 / 0.4375
    assert fixed_point == pytest.approx(-0.0057142857, abs=1e-10)
    # 偶拍步进期末（c=35）已逼近固定点（同数量级、单调恶化段 valence 恒负）
    worst = min(o.state.valence for o in outs)
    assert worst == pytest.approx(fixed_point, abs=2e-5)
    assert all(o.state.valence <= 0.0 for o in outs if o.step.weighted_error > 0.18)
    # 步进停止后衰减回 0（层B：刺激撤除回落）
    assert outs[-1].state.valence == pytest.approx(0.0, abs=1e-3)


def test_stabilized_error_zero_valence(affect_params: C2AffectParams) -> None:
    """误差大但稳定 → valence → 0（效价 = 变化率，非水平——非 reward 结构面）。"""
    pipe = AffectPipeline(affect_params)
    outs = [
        pipe.step(AffectCycleInputs(cycle=c, body_energy=0.5, body_integrity=0.5))
        for c in range(40)
    ]
    assert outs[-1].state.valence == pytest.approx(0.0, abs=1e-5)   # 一阶衰减残余 ~0.25·0.75^39
    assert outs[-1].state.arousal == pytest.approx(0.5, abs=1e-5)   # 唤醒 = 误差水平（0.5·(1−0.75^39) 残余）
