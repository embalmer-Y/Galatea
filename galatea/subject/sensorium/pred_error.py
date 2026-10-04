"""感觉层预测误差（L02 §4.5/§10 pred_error.py；C0 范围）。

C0 无预测源（L03/L04/L09 的 SensoryPrediction 归 C1/C4）——本档 C0 行为 =
无匹配预测 → 只形成、不产误差（**禁伪造零误差**，L02 §4.5）；预测无匹配帧的
处置面归 L09/L04，本档记 typed Unknown（C1 接线）。C0 交付合同面：
predictions 为空序列 → 空误差序列（恒真行为，C1 换统计/精度加权实现）。
"""
from typing import Any

from galatea.subject.sensorium.ports import SensoryFrame


def sense_errors(predictions: tuple[Any, ...], frames: tuple[SensoryFrame, ...]) -> tuple[Any, ...]:
    """感觉层预测误差（层级化三分量的感觉层分量，禁与知觉层/模型层顶替）。

    C0：predictions 恒空（无预测源）→ 返回 ()；任何非空 predictions 在 C0 即
    合同违规（预测源 C1 才存在）——fail closed 防伪造误差面。
    """
    if predictions:
        raise ValueError(
            "SensoryPrediction sources do not exist at C0（L02 §9：预测误差比较归 C1/C4）；"
            "禁伪造零误差或凭空误差"
        )
    return ()
