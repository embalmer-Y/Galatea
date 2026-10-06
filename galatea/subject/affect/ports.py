"""端口合同与禁止路径断言（L05 §2/§10 ports.py，C2 实现期）。

纪律（L05 §8）：
- `aff.modulation` 是唯一对外作用通道；不存在 affect → gateway / ActionIntention /
  OwnedGoal / WorkspaceFrame / 主体记忆条目的写入路径（类型面即无此方法，
  ProhibitedWritePath 保留为检出合同）；
- 驱力唯一内稳态输入 = BodyBelief 值（L04），**禁 telemetry 直填**（不变量 2）——
  telemetry 标记输入构造即拒（TelemetrySourceRejected，L05 §6 行 2，S1 面）；
- 感受态不可被语言直接赋值（D-13），只可经 ReappraisalRequest 触发重算并留回执。
"""
import enum
from dataclasses import dataclass

__all__ = [
    "DriveKind",
    "AffectCycleInputs",
    "TelemetrySourceRejected",
    "ProhibitedWritePath",
    "assert_no_command_path",
]


class DriveKind(enum.StrEnum):
    """MW0 驱力最小集（L05 §4.5；c2_affect.profile drives.set）。"""

    ENERGY = "energy"
    INTEGRITY = "integrity"
    LOAD = "load"          # Q-L01-09⑥ load≡0（schema 保留不生效）


class TelemetrySourceRejected(RuntimeError):
    """检出 telemetry 直填企图（L05 §6 行 2：UnauthorizedInput(TELEMETRY_TO_AFFECT)，S1）。"""


class ProhibitedWritePath(RuntimeError):
    """检出 affect → gateway/intention/goal/frame/memory 写入（L05 §6 行 8，S0 面）。"""


def assert_no_command_path(module_globals: dict[str, object]) -> None:
    """结构断言：给定模块命名空间中不得有行动/目标/工作空间平面对象（显式传入——
    进程级 sys.modules 检查在共享测试进程下会误伤其它套件的合法 import）。

    消费面：合同测试逐 affect 模块调用本断言（第二防线；import-linter 之外）。
    """
    import types

    banned = ("galatea.subject.action", "galatea.subject.goals", "galatea.subject.workspace")
    for name, value in module_globals.items():
        if isinstance(value, types.ModuleType):
            if value.__name__ in banned or any(value.__name__.startswith(b + ".") for b in banned):
                raise ProhibitedWritePath(
                    f"affect plane module leaks command-plane import: {name} -> {value.__name__}"
                )


@dataclass(frozen=True, slots=True)
class AffectCycleInputs:
    """单 cycle 感受态输入（全部主体可见面；None = 缺席 → typed Unknown 保持上一有效值）。

    来源合同（L05 §2.1）：body_* 只来自 L04 InteroceptiveBodyBelief（禁 telemetry）；
    sensory_residual_mean 来自 L02 SensoryPredictionError（形成后信号）；
    belief_uncertainty_mean 来自 L03 窗信念（1 − max posterior 均值）；
    action_receipt_success 事件来自主体侧执行回执台账（Q-L08-09⑩ 同源——
    requested==effective 的归属统计代理，C3 由 L08 结算面接管）；
    affordance_strengths 来自 L03 affordance（Q-L05-06②：tendencies 输入）。
    """

    cycle: int
    body_energy: float | None = None
    body_integrity: float | None = None
    body_load: float | None = None
    telemetry_flagged: bool = False
    sensory_residual_mean: float | None = None
    belief_uncertainty_mean: float | None = None
    action_receipt_success: bool | None = None
    affordance_strengths: tuple[tuple[str, float], ...] = ()

    def __post_init__(self) -> None:
        if self.telemetry_flagged:
            raise TelemetrySourceRejected(
                "telemetry → DriveState/FunctionalExperientialState 直填（L05 §8 不变量 2，S1 拒绝留痕）"
            )
        for name in ("body_energy", "body_integrity"):
            v = getattr(self, name)
            if v is not None and not 0.0 <= v <= 1.0:
                raise ValueError(f"{name} out of [0,1]: {v!r}")
        if self.body_load not in (None, 0.0):
            raise ValueError("body_load must be 0.0 or None（Q-L01-09⑥ load≡0）")
        for _, s in self.affordance_strengths:
            if not 0.0 <= s <= 1.0:
                raise ValueError(f"affordance strength out of [0,1]: {s!r}")
