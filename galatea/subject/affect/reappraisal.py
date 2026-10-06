"""重新评价：请求处理、revision 事件与回执（L05 §4.3/§10 reappraisal.py，C2 实现期）。

合同（L05 §8 不变量 6 / D-13）：感受态**不可被语言或请求直接赋值**；请求只能
触发**经同一动力学算子的重算**（two_step 构造式，ADR-G-0015 层A：0.0875 锚），
产 revision 事件并留回执；禁历史改写（reappraisal_history 只追加）。

C2 = 机制面在位（请求类型 + 重算 + revision + 回执）；请求源（L09 metacontrol /
L06 回忆线索 / L12 typed 语言）C3+ 接线。
"""
from dataclasses import dataclass

from galatea.kernel.digest import content_digest
from galatea.subject.affect.dynamics import two_step

__all__ = ["ReappraisalRequest", "ReappraisalReceipt", "DirectAssignmentRejected", "reappraise"]


class DirectAssignmentRejected(RuntimeError):
    """感受态直写企图（D-13：语言/请求不得赋值感受态数值——只可触发重算）。"""


@dataclass(frozen=True, slots=True)
class ReappraisalRequest:
    """重评价请求（L05 §2.1 aff.reappraisal_in；必须回执）。"""

    target_belief_ref: str
    reason_code: str                  # 请求方原因码（L09/L06/L12 typed）
    requested_by: str
    original_input: float             # 原评价输入（重算被引用对象）
    revised_input: float              # 修正后输入（同一证据通道的修正值）
    requested_at: int

    def __post_init__(self) -> None:
        if not self.reason_code:
            raise ValueError("reason_code required（typed 请求纪律）")


@dataclass(frozen=True, slots=True)
class ReappraisalReceipt:
    """重评价回执（revision 事件 + 轨迹差——审计面）。"""

    request_ref: str
    revision_id: str
    delta: float                      # two_step(original) − two_step(revised)
    accepted: bool


def reappraise(
    request: ReappraisalRequest, tau_int: int, valence_integrator: float
) -> tuple[float, ReappraisalReceipt]:
    """处理请求：经 two_step 低通构造重算，产有界 revision 调整（非直写）。

    delta = two_step(original) − two_step(revised)（ADR 0.0875 构造式同源）；
    积分器调整 = lowpath 机械合成（调整量本身由动力学算子产出——重算非赋值）。
    """
    original_recomputed = two_step(request.original_input, tau_int)
    revised_recomputed = two_step(request.revised_input, tau_int)
    delta = original_recomputed - revised_recomputed
    new_integrator = valence_integrator + delta
    receipt = ReappraisalReceipt(
        request_ref=f"{request.requested_by}:{request.target_belief_ref}",
        revision_id=f"revision.{request.requested_at}.{request.target_belief_ref}",
        delta=delta,
        accepted=True,
    )
    return new_integrator, receipt


def revision_digest(revision_id: str, delta: float, requested_at: int) -> str:
    """revision 事件 digest（追加式历史——reappraisal_history 载体）。"""
    return content_digest({"revision_id": revision_id, "delta": delta, "at": requested_at})
