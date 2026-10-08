"""在线局部适应有界面（L11 §4.1 第二层 / §10 layers/online.py；Q-L09-05）。

adaptive_gain 界 = [0.5, 2.0]（单一有界调制因子界第四次贯穿——Q-L02-02/
Q-L07-02/Q-L09-01 同值同源）；界内漂移 = 在线适应（参数复位即回滚）；
越界 = BoundViolation 拒 + POLICY_PARAMS 提案走 promotion。
"""
from dataclasses import dataclass

__all__ = ["BoundViolation", "BoundedAdaptation", "propose_policy_params"]

_BOUND = (0.5, 2.0)


class BoundViolation(ValueError):
    """越出冻结界（渐进自扩权防线——L11 §4.1 纪律原文）。"""


@dataclass(frozen=True, slots=True)
class BoundedAdaptation:
    """有界适应步（当前值 + 请求值 → 应用值；不产新工件——参数复位即回滚）。"""

    parameter: str
    current: float
    requested: float

    def applied(self) -> float:
        lo, hi = _BOUND
        if not lo <= self.requested <= hi:
            raise BoundViolation(
                f"{self.parameter} requested {self.requested} outside frozen bound {_BOUND}"
                "（越界须走 promotion——Q-L09-05②）"
            )
        return self.requested


def propose_policy_params(parameter: str, requested: float) -> str:
    """越界目标 → POLICY_PARAMS 提案提示（提案构造在 learning/proposal.py；本函数
    返回提案 target_artifact 规范名，供装配层接 learning/promotion_if 面）。"""
    lo, hi = _BOUND
    if lo <= requested <= hi:
        raise ValueError(f"{requested} within bound——界内走在线适应，不需要提案")
    return f"policy_params.{parameter}"
