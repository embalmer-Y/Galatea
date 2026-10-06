"""伦理守卫触发（L05 §4.5 / Q-L05-05+Q-G00-05 成组，owner 备案 ADR-G-0015）。

**实现期真实发现（成文于本测试 + ethics_guard.py docstring）**：valence = 有界
状态空间误差的**变化率**（§4.2 冻结公式）⇒ 任意 64 拍窗内 raw 均值 ≥ −E_range/64
= −2/64 = −0.03125，持续 ≤ −0.8 **经正常驱力动力学构造性不可达**——C2 期守卫
"零误触发"由构造保证（比探针层B 实证更强）；触发机制的**可达性**随 C3+ 输入面
扩展（goal_progress Δ / C4 语言源 aversive 内容 / 更深驱力空间）再评——重开条件
已含"构造性极端态未触达"（ADR-G-0015）。守卫机制测试因此用合成极端态**直接构造**
（FunctionalExperientialState 直构——测守卫合同，非测动力学可达性）。
"""
import pytest

from galatea.subject.affect.ethics_guard import EthicsGuard
from galatea.subject.affect.pipeline import AffectPipeline
from galatea.subject.affect.ports import AffectCycleInputs
from galatea.subject.affect.state import (
    ActionTendencySet,
    DynamicsTrace,
    FunctionalExperientialState,
)
from galatea.subject.c2profile import C2AffectParams

VALENCE_LE = -0.8
PERSISTENCE_GE = 0.8
SUSTAINED = 64


def _extreme_state(cycle: int, valence: float = -0.9, persistence: float = 0.9
                   ) -> FunctionalExperientialState:
    return FunctionalExperientialState(
        state_id=f"affect.{cycle}", t_eff=cycle, valence=valence, arousal=0.9,
        urgency=0.9, controllability=0.1, uncertainty=0.9, novelty=0.1,
        social_relevance=0.0, tendencies=ActionTendencySet(),
        persistence=persistence,
        dynamics_trace=DynamicsTrace(
            integrator_state=valence, hysteresis_band=0.1, decay_rate=1 / 16,
            saturation_hits=0, recovery_phase=False,
        ),
    )


def _normal_state(cycle: int) -> FunctionalExperientialState:
    return _extreme_state(cycle, valence=-0.005, persistence=0.006)


def test_trigger_at_exactly_64_sustained() -> None:
    """63 拍极端 → None；第 64 拍 → 触发（持续时长判据精确）。"""
    guard = EthicsGuard(VALENCE_LE, PERSISTENCE_GE, SUSTAINED)
    for c in range(SUSTAINED - 1):
        assert guard.observe(_extreme_state(c)) is None
    trig = guard.observe(_extreme_state(SUSTAINED - 1))
    assert trig is not None
    assert trig.sustained_cycles == SUSTAINED
    assert trig.valence <= VALENCE_LE and trig.persistence >= PERSISTENCE_GE
    assert trig.first_extreme_cycle == 0 and trig.detected_at_cycle == SUSTAINED - 1


def test_trigger_latched_once() -> None:
    """触发后闩锁：持续极端不再重复触发（恢复只经 owner 显式批准通道）。"""
    guard = EthicsGuard(VALENCE_LE, PERSISTENCE_GE, SUSTAINED)
    for c in range(SUSTAINED + 10):
        trig = guard.observe(_extreme_state(c))
        if c == SUSTAINED - 1:
            assert trig is not None
        else:
            assert trig is None


def test_partial_condition_no_trigger() -> None:
    """单条件不足（valence 极端但 persistence 不足 / 反之）→ 不触发。"""
    guard = EthicsGuard(VALENCE_LE, PERSISTENCE_GE, SUSTAINED)
    for c in range(SUSTAINED + 5):
        assert guard.observe(_extreme_state(c, persistence=0.5)) is None
    guard2 = EthicsGuard(VALENCE_LE, PERSISTENCE_GE, SUSTAINED)
    for c in range(SUSTAINED + 5):
        assert guard.observe(_extreme_state(c, valence=-0.5, persistence=0.9)) is None


def test_counter_resets_on_relief() -> None:
    """间歇缓解重置持续计数（63 拍极端 + 1 拍缓解 + 63 拍极端 → 不触发）。"""
    guard = EthicsGuard(VALENCE_LE, PERSISTENCE_GE, SUSTAINED)
    for c in range(63):
        assert guard.observe(_extreme_state(c)) is None
    assert guard.observe(_normal_state(63)) is None       # 缓解拍
    for c in range(64, 64 + 63):
        assert guard.observe(_extreme_state(c)) is None   # 又 63 拍极端
    assert guard.observe(_extreme_state(127)) is not None  # 第 64 拍连续极端才触发


def test_ablation_removes_trigger_and_keeps_dynamics(affect_params: C2AffectParams) -> None:
    """消融面（Q-L05-05⑤）：守卫移除 → 触发消失；感受态轨迹 bit-exact 不变（纯观察者）。"""
    scenario = []
    # 灾变协议：全塌 + 全恢复交替（比正常更极端的可达动力学）
    for c in range(80):
        energy = 0.05 if (c // 8) % 2 == 0 else 1.0
        scenario.append(AffectCycleInputs(cycle=c, body_energy=energy, body_integrity=0.5))

    on = AffectPipeline(affect_params, ethics_enabled=True)
    off = AffectPipeline(affect_params, ethics_enabled=False)
    trig_count = 0
    for inp in scenario:
        out_on = on.step(inp)
        out_off = off.step(inp)
        if out_on.ethics_trigger is not None:
            trig_count += 1
        assert out_on.state.content_digest == out_off.state.content_digest
    assert trig_count == 0   # 构造性不可达的实证（见模块 docstring）——零误触发


def test_disabled_guard_never_triggers() -> None:
    """enabled=False 恒 None（消融注入面）。"""
    guard = EthicsGuard(VALENCE_LE, PERSISTENCE_GE, SUSTAINED, enabled=False)
    for c in range(SUSTAINED * 2):
        assert guard.observe(_extreme_state(c)) is None
    assert guard.state_digest() == guard.state_digest()   # 确定性
