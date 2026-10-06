"""动力学算子与感受态引擎（L05 §4.3/§10 dynamics.py，C2 实现期）。

公式与 ADR-G-0015 冻结前可行性探针**逐位同源**（评审独立重演锚）：
- 一阶低通 `s ← s + (1/τ)(x − s)`（层A 积分：τ_int=4，t63=4 拍、24 拍终值 0.99899661）；
- 衰减 = 低通输入 0（`s·(τ−1)/τ`；层A：16 拍后 0.35607413 = (15/16)^16 逐位）；
- 迟滞 band=0.1：ON ≥ center+band/2（0.55）、OFF ≤ center−band/2（0.45），
  2σ（±0.05）噪声 64 拍零误切换；
- 饱和 = 域边界 clip + saturation_hits 每拍 +1（层A：clip[−1,1] hits=8）；
- 恢复相位 = 稳态误差 ≤ band（层A：e=0.05 True / e=0.11 False 精确）；
- 重评价 two_step(x) := lowpass(lowpass(0, x, τ_int), x, τ_int)（层A：0.175−0.0875=0.0875）。

全部算子确定性（c2_affect.profile determinism none_c2——零 RNG 零墙钟）。
"""
from dataclasses import dataclass

from galatea.subject.affect.ports import AffectCycleInputs, DriveKind
from galatea.subject.affect.state import ActionClass, ActionTendencySet, Tendency

__all__ = ["lowpass", "decay_step", "hysteresis", "saturate", "in_recovery", "two_step", "AffectStep"]


def lowpass(state: float, x: float, tau: int) -> float:
    """一阶低通（ADR-G-0015 层A 公式；τ ≥ 1）。"""
    if tau < 1:
        raise ValueError(f"tau must be >= 1: {tau!r}")
    return state + (x - state) / tau


def decay_step(state: float, tau: int) -> float:
    """衰减一步 = 低通向 0（s·(τ−1)/τ；ADR (15/16)^16 逐位锚）。"""
    return lowpass(state, 0.0, tau)


def hysteresis(prev_on: bool, x: float, band: float, center: float = 0.5) -> bool:
    """迟滞开关（L05 §4.3：升/降阈值不同防抖动；ADR up_at=0.55/down_at=0.45 精确）。"""
    if x >= center + band / 2.0:
        return True
    if x <= center - band / 2.0:
        return False
    return prev_on


def saturate(x: float, lo: float, hi: float) -> tuple[float, bool]:
    """饱和 clip（Q-L05-01 域边界；返回 (值, 是否命中)。"""
    if x < lo:
        return lo, True
    if x > hi:
        return hi, True
    return x, False


def in_recovery(error: float, band: float) -> bool:
    """恢复相位（Q-L05-03⑤：误差回落 set-point±band 内；ADR e=0.05→T / e=0.11→F）。"""
    return error <= band


def two_step(x: float, tau: int) -> float:
    """重评价构造式 two_step(x) = lowpass(lowpass(0, x, τ), x, τ)（ADR 0.0875 锚）。"""
    return lowpass(lowpass(0.0, x, tau), x, tau)


@dataclass(frozen=True, slots=True)
class AffectStep:
    """单拍感受态引擎产物（engine.step 的中间量公开面，测试/证据侧消费）。"""

    weighted_error: float            # E = Σ w_d·e_d（L05 §4.2 字面，无归一）
    max_error: float                 # e_max = max_d e_d（arousal/urgency 输入）
    valence_raw: float               # −ΔE（未平滑效价）
    gate_gain_on: bool               # 增益调制发放门（迟滞，center=0.5）
    gate_threshold_on: bool          # 知觉阈值调制发放门
    gate_salience_on: bool           # workspace 显著性调制发放门（L07 消费面 = C2 次单元）


class AffectEngineCore:
    """纯函数步进核心（AffectPipeline 持有状态；本类只做无状态单拍计算）。

    C2 输入映射（全部机械钉死、零自由常量；L05 §4.1 各维来源的 C2 最小实现）：
    - valence = lowpass(−ΔE, τ_int)（§4.2 字面；探针层B 锚：18 步 −0.01/拍 →
      固定点 −0.0025/0.4375 = −0.0057142857…）；
    - arousal = lowpass(e_max, τ_int)（唤醒 = 最差驱力误差水平，域天然 [0,1]）；
    - urgency = lowpass(max(0, (e_max − band)/(1 − band)), τ_int)（band 上方线性归一）；
    - persistence = lowpass(min(1, |valence|/0.8), τ_dec)（伦理阈 0.8 归一——
      persistence = 1 ⟺ |valence| 达触发阈；慢尺度 = "持续"的操作化）；
    - controllability = lowpass(1{requested==effective}, τ_dec)（事件驱动归属统计，
      无事件拍保持；C3 由 L08 结算面接管）；
    - novelty = lowpass(mean |sensory residual|, τ_int)；缺源保持上一值 + Unknown；
    - uncertainty = lowpass(mean(1 − p_max), τ_int)；同上；
    - social_relevance = 0.0 + Unknown(CAPABILITY_LIMIT)（D-14 恒定，禁伪造）。
    """

    __slots__ = ()

    @staticmethod
    def drive_errors(inputs: AffectCycleInputs, set_points: dict[DriveKind, float],
                     prev: dict[DriveKind, float]) -> tuple[dict[DriveKind, float], tuple[str, ...]]:
        """驱力误差（缺席驱力保持上一有效值——L05 §6 行 1 禁编造；返回 (errors, unknown_refs)）。"""
        values: dict[DriveKind, float | None] = {
            DriveKind.ENERGY: inputs.body_energy,
            DriveKind.INTEGRITY: inputs.body_integrity,
            DriveKind.LOAD: inputs.body_load,
        }
        errors: dict[DriveKind, float] = {}
        unknowns: list[str] = []
        for kind in DriveKind:
            v = values[kind]
            if v is None:
                errors[kind] = prev.get(kind, 0.0)
                unknowns.append(f"drive.{kind.value}:MISSING_SIGNAL")
                continue
            errors[kind] = set_points[kind] - v
        return errors, tuple(unknowns)

    @staticmethod
    def tendency_set(affordance_strengths: tuple[tuple[str, float], ...]) -> ActionTendencySet:
        """tendencies = affordance 置信（Q-L05-06②：move 无前置恒可行 1.0；inhibited 默认 True）。"""
        by_name = dict(affordance_strengths)
        items: list[Tendency] = []
        for ac in ActionClass:
            strength = by_name.get(ac.value, 1.0 if ac is ActionClass.MOVE else 0.0)
            items.append(Tendency(action_class=ac, strength=strength, inhibited=True))
        return ActionTendencySet(items=tuple(items))
