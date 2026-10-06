"""增益应用与回执（L02 §4.4/§10 gain.py；Q-G00-12③ C0 形态 → Q-L02-02 C2 接收面）。

- C0（apply_gain）：恒等 1.0、PROFILE 来源、无调制入口（任何非 None 输入拒）；
- C2（apply_gain_c2，Q-L02-02 裁决 2026-10-06）：**增益调制因子界 [0.5, 2.0]**——
  requested 越界 = clip + bound_check=CLIPPED（正常路径非错误）；回执必返且
  requested/applied 成对呈现（evaluator 只采信 applied）；**形成义务无条件**
  （不变量 6：增益不改变是否形成——CLIPPED 到界亦不改变形成面）；
- 特征缩放（L02 §4.4"作用于当期形成的特征缩放"）：连续强度面（EXT_LOCAL_OBS
  窗格值 / INTERO 标量）× applied 后受模态域 [0,1] clip（饱和即增益的物理语义）；
  分类 one-hot 面（EXT_EVENT/PROPRIO 朝向）豁免——缩放 one-hot 非放大而是畸变；
- 增益不改历史：只作用于当期形成，禁回写已发布帧或改写 ReceivedSignal。
"""
from typing import Any

from galatea.subject.sensorium.ports import GainReceipt, GainState, ModulationRejected

__all__ = ["C0_GAIN", "GAIN_BOUND", "apply_gain", "apply_gain_c2", "scale_intensity"]

C0_GAIN = GainState(applied_factor=1.0, source="PROFILE")

#: C2 增益调制因子界（Q-L02-02①：[0.5, 2.0]，2 的幂，Q-G00-08）
GAIN_BOUND: tuple[float, float] = (0.5, 2.0)


def apply_gain(frame_id: str, modulation: Any) -> tuple[GainState, GainReceipt]:
    """C0 增益：恒等应用 + 回执；modulation 非 None 即拒（C2 面 = apply_gain_c2，两合同分立）。"""
    if modulation is not None:
        raise ModulationRejected(
            "gain modulation input rejected at C0 face（C2 面 = apply_gain_c2；"
            "本档不得因调制改变是否形成）"
        )
    return C0_GAIN, GainReceipt(
        frame_id=frame_id, requested_gain=1.0, applied_gain=1.0, bound_check="IDENTITY_C0"
    )


def apply_gain_c2(frame_id: str, requested: float | None) -> tuple[GainState, GainReceipt]:
    """C2 增益面：None = 无调制（恒等）；requested → clip [0.5,2.0] + 回执（Q-L02-02）。"""
    if requested is None:
        return C0_GAIN, GainReceipt(
            frame_id=frame_id, requested_gain=1.0, applied_gain=1.0, bound_check="IDENTITY_C0"
        )
    lo, hi = GAIN_BOUND
    applied = min(max(float(requested), lo), hi)
    bound_check = "IN_BOUND" if applied == float(requested) else "CLIPPED"
    return (
        GainState(applied_factor=applied, source="MODULATION"),
        GainReceipt(
            frame_id=frame_id, requested_gain=float(requested), applied_gain=applied,
            bound_check=bound_check,
        ),
    )


def scale_intensity(value: float, factor: float) -> float:
    """连续强度特征缩放（×factor 后模态域 [0,1] clip——饱和语义；分类面豁免见模块 docstring）。"""
    scaled = value * factor
    if scaled < 0.0:
        return 0.0
    if scaled > 1.0:
        return 1.0
    return scaled
