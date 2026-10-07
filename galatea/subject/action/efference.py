"""EfferenceCopy 与感觉预测闭环（L10 §4.3 C4 行 / §10 efference.py；ADR-G-0019 范围声明 1）。

时序纪律（原文）：提交命令**同步**产生 EfferenceCopy(motor_command_copy)，分发
L04（forward model 计算 SensoryPrediction）与 L02（比较）；EfferenceCopy 必须
**早于或同 cycle** 于效果到达——预测是先行的，非事后拟合（L10 §7 efference timing
C4 判据：移除 efference → forward 预测退化，可干预消融面）。
"""
from dataclasses import dataclass

from galatea.subject.action.ports import SubmittedCommand
from galatea.subject.models.ports import ModelPrediction

__all__ = ["EfferenceCopy", "EfferenceTimingViolation", "issue_efference_copy"]


class EfferenceTimingViolation(ValueError):
    """EfferenceCopy 晚于效果到达（L10 §4.3 时序纪律违反——预测沦为事后拟合）。"""


@dataclass(frozen=True, slots=True)
class EfferenceCopy:
    """感觉运动闭环载体（L10 §4.3：motor_command_copy + prediction_ref + 时序对）。

    prediction_ref 指向 L04 ModelPrediction（forward model 按请求动作积分的
    SensoryPrediction，L04 §9 C4 行）；比较残差由 L02 pred_error 消费（预测来自
    L04/L09，比较在本档——L02 §9 C4 行）。
    """

    motor_command_copy: str          # SubmittedCommand.command_id（选择记录 = 归属证据①同源）
    requested_action: str            # primitive[:param]（请求语义，Q-L01-01 方向合同）
    issued_cycle: int                # 发布时 = 命令提交 cycle（同步产生）
    prediction_ref: str              # ModelPrediction.prediction_id（forward 面先行发布）
    valid_time: int                  # 预测目标窗世界时

    def __post_init__(self) -> None:
        if not self.motor_command_copy or not self.requested_action:
            raise ValueError("EfferenceCopy requires command copy and requested action")
        if not self.prediction_ref:
            raise ValueError("EfferenceCopy requires a forward prediction_ref（禁无预测的副本）")
        if self.issued_cycle > self.valid_time:
            raise EfferenceTimingViolation(
                f"efference issued at {self.issued_cycle} later than prediction valid_time"
                f" {self.valid_time}（先行动作积分的预测必须先行，L10 §4.3）"
            )


def issue_efference_copy(
    command: SubmittedCommand, prediction: ModelPrediction, issued_cycle: int
) -> EfferenceCopy:
    """命令提交同步产生副本并绑定 forward 预测（L10 §4.3 原文的机械兑现）。

    前置：prediction 必须是先行发布的 PREDICTED 层（T1 先行语义，Q-L04-09③），
    且其 valid_time ≥ issued_cycle（时序纪律断言，构造期强制）。
    """
    if prediction.representation_level != "PREDICTED":
        raise EfferenceTimingViolation(
            f"efference prediction must be PREDICTED level, got {prediction.representation_level}"
        )
    return EfferenceCopy(
        motor_command_copy=command.command_id,
        requested_action=command.requested_action,
        issued_cycle=issued_cycle,
        prediction_ref=prediction.prediction_id,
        valid_time=prediction.valid_time,
    )
