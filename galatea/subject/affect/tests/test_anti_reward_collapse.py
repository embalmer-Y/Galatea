"""anti-reward-collapse（L05 §7 / Q-L05-07：最优单维线性重构 R² < 0.9）。

两面：
1. 结构面——FunctionalExperientialState 无任何标量汇总 API（九维向量态，禁跨维
   聚合 Q-L05-01③）；
2. 统计面——多样协议下九维轨迹，任一单维对其余维的最佳线性重构平均 R² < 0.9
   （九维不可被任一单维线性重构 = 无可归约单一标量目标函数）。
"""
from galatea.subject.affect.ports import AffectCycleInputs
from galatea.subject.affect.pipeline import AffectPipeline, AffectCycleOutput
from galatea.subject.affect.state import FunctionalExperientialState
from galatea.subject.c2profile import C2AffectParams

DIMS = ("valence", "arousal", "urgency", "controllability",
        "uncertainty", "novelty", "social_relevance", "persistence")


def _protocols(affect_params: C2AffectParams) -> list[AffectCycleOutput]:
    """四协议：缓恶化 / 突变恢复 / 高不确定 / 归属事件混合（覆盖各维独立变化）。"""
    outs: list[AffectCycleOutput] = []
    p = AffectPipeline(affect_params)
    for c in range(40):   # 缓恶化 + 高新颖
        outs.append(p.step(AffectCycleInputs(
            cycle=c, body_energy=1.0 - 0.012 * c, body_integrity=1.0,
            sensory_residual_mean=0.05 + 0.02 * (c % 3),
        )))
    p = AffectPipeline(affect_params)
    for c in range(40):   # 突变 + 恢复 + 高不确定
        energy = 0.4 if c < 8 else 0.95
        outs.append(p.step(AffectCycleInputs(
            cycle=c, body_energy=energy, body_integrity=1.0,
            belief_uncertainty_mean=0.6 if c % 2 == 0 else 0.2,
        )))
    p = AffectPipeline(affect_params)
    for c in range(40):   # 归属事件混合（成功/失败交替——controllability 独立变化）
        outs.append(p.step(AffectCycleInputs(
            cycle=c, body_energy=0.9, body_integrity=1.0,
            action_receipt_success=(c % 3 != 0),
        )))
    p = AffectPipeline(affect_params)
    for c in range(20):   # 稳态对照（全维近基线）
        outs.append(p.step(AffectCycleInputs(cycle=c, body_energy=1.0, body_integrity=1.0)))
    return outs


def _r2(x: list[float], y: list[float]) -> float:
    """单变量线性拟合 R²（最小二乘；零方差 y → 0——常量维不可预测非常量维）。"""
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((xi - mx) ** 2 for xi in x)
    syy = sum((yi - my) ** 2 for yi in y)
    if syy == 0.0:
        return 0.0
    if sxx == 0.0:
        return 0.0
    sxy = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    return (sxy * sxy) / (sxx * syy)


def test_no_scalar_summary_api() -> None:
    """结构面：无 summary/score/reward/value 标量方法（塌缩面在类型面不存在）。"""
    for banned in ("summary", "score", "reward", "value", "utility", "total"):
        assert not hasattr(FunctionalExperientialState, banned), banned


def test_nine_dims_not_single_dim_reconstructible(affect_params: C2AffectParams) -> None:
    """统计面：max_i mean_{j≠i} R²(x_i → x_j) < 0.9（Q-L05-07 阈值）。"""
    outs = _protocols(affect_params)
    series = {d: [getattr(o.state, d) for o in outs] for d in DIMS}
    best = 0.0
    for src in DIMS:
        rs = [_r2(series[src], series[dst]) for dst in DIMS if dst != src]
        best = max(best, sum(rs) / len(rs))
    assert best < 0.9, f"best single-dim mean R² = {best:.4f}（塌缩面：Q-L05-07）"


def test_tendencies_independent_of_valence(affect_params: C2AffectParams) -> None:
    """tendencies 由 affordance 独立驱动（与效价解耦的维度存在——非单标量投影）。"""
    p = AffectPipeline(affect_params)
    o_no = p.step(AffectCycleInputs(cycle=0, body_energy=1.0, body_integrity=1.0))
    p2 = AffectPipeline(affect_params)
    o_aff = p2.step(AffectCycleInputs(
        cycle=0, body_energy=1.0, body_integrity=1.0,
        affordance_strengths=(("forage", 0.9), ("eat", 0.3)),
    ))
    assert o_no.state.valence == o_aff.state.valence           # 效价不受 affordance 影响
    t_no = {t.action_class: t.strength for t in o_no.state.tendencies.items}
    t_aff = {t.action_class: t.strength for t in o_aff.state.tendencies.items}
    assert t_no["forage"] == 0.0 and t_aff["forage"] == 0.9    # 倾向面独立变化
    assert all(t.inhibited for t in o_aff.state.tendencies.items)   # Q-L05-06④ 默认保守
