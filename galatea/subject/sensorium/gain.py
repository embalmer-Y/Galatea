"""增益应用与回执（L02 §4.4/§10 gain.py；Q-G00-12③ C0 形态）。

C0 = 恒等 1.0、PROFILE 来源、**无调制入口**（ModulationField 类型不存在于本档——
任何调制输入在类型面即拒，ModulationRejected）；gain_max 上界与 bound_check=CLIPPED
归 C2（Q-L02-02）。形成义务无条件：增益不改变是否形成（L02 §8 不变量 6）。
"""
from typing import Any

from galatea.subject.sensorium.ports import GainReceipt, GainState, ModulationRejected

C0_GAIN = GainState(applied_factor=1.0, source="PROFILE")


def apply_gain(frame_id: str, modulation: Any) -> tuple[GainState, GainReceipt]:
    """C0 增益：恒等应用 + 回执；modulation 非 None 即拒（C2 未到，无调制入口）。"""
    if modulation is not None:
        raise ModulationRejected(
            "gain modulation input rejected at C0（Q-G00-12③：gain_max/GainReceipt 调制面归 C2，"
            "ModulationField 归 L05——本档不得因调制改变是否形成）"
        )
    return C0_GAIN, GainReceipt(
        frame_id=frame_id, requested_gain=1.0, applied_gain=1.0, bound_check="IDENTITY_C0"
    )
