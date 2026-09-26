"""目标链四型分离与端口合同（L08 §2/§3/§8/§10 ports.py）。

纪律：request ≠ candidate ≠ goal ≠ intention（HLD §11.1）——四型为独立类型，
无公共构造路径与继承关系（三型定义点：request.py / candidates.py / owned.py；
ActionIntention 在 L09 control.intention.py）。OwnedGoal 唯一写者 = Goal Ownership
（本包 lifecycle.py）；外部请求 / LLM / orchestrator / 情感驱力 / 工作空间帧直写
OwnedGoal 一律 ProhibitedWritePathError（机械拒绝，非约定，L08 §3/§6）。
M1 范围 = schema + 分离断言 + 禁写路径检查；conflicts.py/arbitrate.py 属 C3（Q-L08-01）。
"""
import enum
from dataclasses import dataclass

__all__ = [
    "GoalDecision",
    "RejectionCode",
    "SettlePredicate",
    "GoalDecisionLog",
    "GoalWriter",
    "ProhibitedWritePathError",
    "assert_goal_writer",
    "assert_four_type_separation",
]


class GoalDecision(enum.StrEnum):
    """目标决策五态（L08 §2.2 goal.decision_log）。"""

    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    MODIFY = "MODIFY"
    DEFER = "DEFER"
    RELEASE = "RELEASE"


class RejectionCode(enum.StrEnum):
    """拒绝/日志码。C-1…C-7 未过码 = L08 §4.2 冻结文本（m1_goals_min.profile
    checklist.reject_reason_codes）；EXPIRED = L08 §6；CAPACITY = Q-L08-09⑤。"""

    CAPABILITY = "CAPABILITY"              # C-1
    VIABILITY = "VIABILITY"                # C-2
    EXTERNAL_ONLY = "EXTERNAL_ONLY"        # C-5（M1 核心机械检查）
    UNBOUNDED = "UNBOUNDED"                # C-6
    UNSETTLEABLE = "UNSETTLEABLE"          # C-7
    EXPIRED = "EXPIRED"                    # 候选 TTL 过期（禁静默丢弃）
    CAPACITY = "CAPACITY"                  # 批次上界截断（Q-L08-09⑤）


class SettlePredicate(enum.StrEnum):
    """C-7 结算判据词表（M1 三谓词，Q-L08-09③；全部只读主体可见态；C1+ 扩词表经新 Q）。"""

    PRIMITIVE_COMPLETION = "primitive_completion"   # 原语完成回执到达
    STORED_FOOD_AT_LEAST = "stored_food_at_least"   # 参数 n 冻结于 M1 统计计划
    ENERGY_AT_LEAST = "energy_at_least"             # 参数 x 同上


@dataclass(frozen=True, slots=True)
class GoalDecisionLog:
    """理由仲裁证据（L08 §2.2 goal.decision_log；Recorder/L13 消费，append-only）。"""

    candidate_id: str
    decision: GoalDecision
    reason_refs: tuple[str, ...]
    counterfactual_sensitive: bool
    rejection_code: RejectionCode | None = None
    ts: int = 0


class GoalWriter(enum.StrEnum):
    """候选写者身份（L08 §3 禁止条款的机械检查面）。"""

    GOAL_OWNERSHIP = "GOAL_OWNERSHIP"      # 本包 lifecycle.py——唯一合法写者
    EXTERNAL_REQUEST = "EXTERNAL_REQUEST"  # 外部请求直写 → ProhibitedWritePath
    LLM = "LLM"                            # LLM/语言直写 → UnauthorizedWrite（D-13）
    ORCHESTRATOR = "ORCHESTRATOR"          # orchestrator/实验控制直写
    AFFECT_DRIVE = "AFFECT_DRIVE"          # L05 情感/驱力绕过 Motive→checklist
    WORKSPACE_FRAME = "WORKSPACE_FRAME"    # L07 帧直写（帧只提供素材）


class ProhibitedWritePathError(ValueError):
    """禁止写入路径触发（L08 §6：ProhibitedWritePath / UnauthorizedWrite 家族）。

    S0/S1 级流程缺陷的运行时显形：外部请求、LLM、orchestrator、情感驱力、
    工作空间帧均无 OwnedGoal 写路径；唯一写者 = Goal Ownership。
    """

    def __init__(self, writer: GoalWriter, detail: str) -> None:
        self.writer = writer
        super().__init__(f"prohibited write path {writer.value} → OwnedGoal: {detail}")


def assert_goal_writer(writer: GoalWriter) -> None:
    """禁写路径机械检查（L08 §3/§8）：非 Goal Ownership 写 OwnedGoal 即抛。"""
    if writer is not GoalWriter.GOAL_OWNERSHIP:
        raise ProhibitedWritePathError(
            writer, "only Goal Ownership may construct/modify OwnedGoal（L08 §3）"
        )


def assert_four_type_separation(
    request: object, candidate: object, goal: object, intention: object
) -> None:
    """四型分离断言（HLD §11.1：request ≠ candidate ≠ goal ≠ intention）。

    机械判据：四对象类型两两不同，且任一类型不是另一类型的子类
    （禁隐式转换/别名继承——L08 §4.1"三型独立类型"的四型扩展）。
    """
    types: tuple[type, ...] = (type(request), type(candidate), type(goal), type(intention))
    if len(set(types)) != 4:
        raise TypeError(f"four-type separation violated: {[t.__name__ for t in types]}")
    for i, a in enumerate(types):
        for j, b in enumerate(types):
            if i != j and issubclass(a, b):
                raise TypeError(
                    f"four-type separation violated: {a.__name__} is subclass of {b.__name__}"
                )
