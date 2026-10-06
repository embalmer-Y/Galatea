"""内稳态价值：valence 计算（L05 §4.2/§10 valence.py，C2 实现期）。

**valence = −d/dt Σ_d w_d·e_d 的有界平滑**（改善正/恶化负）：
- raw = −(E_t − E_{t−1})，E = Σ w_d e_d（Q-L05-02 w_d=1:1:1，字面无归一）；
- 平滑 = 一阶低通 τ_int=4（c2_affect.profile §valence：平滑窗 = τ_integrator）；
- 饱和 clip [−1,1] + hits（Q-L05-01 域 / Q-L05-03④）。

**不是 reward**（not_reward 结构面）：不存在环境标量奖励项、不存在"最大化累积
奖励"目标函数（HLD §11.1；本模块无累积量、无折扣、无最大化算子——结构即证明）。
输入只经 BodyBelief 值（ports 层 telemetry 拒绝，不变量 2）。

探针锚（ADR-G-0015 层B，评审核算命中）：每拍 −0.01 的 E 步进 + 偶拍间隔，
固定点 = −0.0025/0.4375 = −0.0057142857…（实测 −0.00571396 逼近）。
"""
from dataclasses import dataclass

from galatea.subject.affect.dynamics import lowpass, saturate

__all__ = ["ValenceUpdate", "valence_step"]


@dataclass(frozen=True, slots=True)
class ValenceUpdate:
    """单拍 valence 计算产物（审计面：raw/平滑前/发布值分离）。"""

    raw: float
    smoothed: float
    published: float
    saturation_hit: bool


def valence_step(prev_smoothed: float, error_now: float, error_prev: float, tau_int: int) -> ValenceUpdate:
    """效价单拍：raw = −ΔE → 低通 τ_int → clip [−1,1]（确定性，零 RNG）。"""
    raw = -(error_now - error_prev)
    smoothed = lowpass(prev_smoothed, raw, tau_int)
    published, hit = saturate(smoothed, -1.0, 1.0)
    return ValenceUpdate(raw=raw, smoothed=smoothed, published=published, saturation_hit=hit)
