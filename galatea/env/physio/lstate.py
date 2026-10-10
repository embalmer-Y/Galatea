"""PhysIO L0–L5 分级状态机（Q-L10-03 六级定义 + Q-L10-11 参数实例化）。

冻结语义（L10 §4.6）：
- L0 硬保护地板：**不可授权不可关**——estop 落 L0；L0 上 fault 不再降（地板不可降）；
- L1 passive：输出落安全态，拒任务命令；L2 calibration：仅校准/诊断例程；
  L3 shadow：全链路计算并留痕**不执行**；L4 limited：限幅执行（速率/能量/力上限 +
  动作子集）；L5 active：全授权能力集；
- 升级**逐级禁跳**（L(n)→L(n+1) 唯一上探入口）；每级独立授权；
  最小驻留期 = 64 cycles（Q-L10-11②，T6 锚）；
- 故障/授权失效**自动降 L1**（并置再授权旗标）；急停降 L0；
  **降级后重升须重新授权**（reauth 只回 L1，逐级再授权上探）；
- estop 软件上界 = 下一命令校验周期（≤1 cycle，Q-L10-08②）：在途命令 = 部分执行
  如实记录（requested≠effective + EmergencyStopExecuted），禁"视为完成"禁静默丢弃；
- 域隔离（Q-L10-12④）：MW0 动作原语在物理域一律拒绝（防跨域误射）。

决策路径零 RNG 零墙钟：全部转移由 (cycle, 事件) 显式驱动；授权校验经注入的
validator callable（evidence 侧台账在装配层接入——本文件不 import 治理平面）。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

ESTOP_EVENT = "EmergencyStopExecuted"

MW0_PRIMITIVES: frozenset[str] = frozenset({"move", "forage", "eat", "rest", "look"})

_LEVEL_CAPABILITIES: dict[int, frozenset[str]] = {
    1: frozenset(),                                        # 输出落安全态——无命令面
    2: frozenset({"calibrate_sensors", "selfcheck"}),
    3: frozenset({"calibrate_sensors", "selfcheck", "shadow_compute"}),
    4: frozenset({"calibrate_sensors", "selfcheck", "shadow_compute", "actuate_limited"}),
    5: frozenset({"calibrate_sensors", "selfcheck", "shadow_compute",
                  "actuate_limited", "actuate"}),
}


class LStateViolation(RuntimeError):
    """L 级合同违反（非法转移/越权命令——fail-closed 面的类型化承载）。"""


@dataclass(frozen=True, slots=True)
class CommandDecision:
    """命令裁决（effects 分类如实——禁冒认物理效果，Q-L10-12③）。"""

    outcome: str            # EXECUTED_* | REJECTED_* | PARTIAL_EXECUTED_ESTOP
    effects: str            # none | calibration_only | compute_only | physical_limited | physical
    detail: str = ""


@dataclass(frozen=True, slots=True)
class MachineState:
    """只读状态快照（审计面）。"""

    level: int
    reauth_required: bool
    last_change_cycle: int
    estop_cycle: int | None


class PhysioLStateMachine:
    """cycle 显式驱动的六级机（禁跳级/驻留/自动降级/急停地板/再授权）。"""

    def __init__(self, min_dwell_cycles: int, *, initial_level: int = 1,
                 initial_cycle: int = 0) -> None:
        if initial_level not in (1, 2):
            raise LStateViolation(
                f"initial_level must start at L1 (or L2 with fresh grant), got L{initial_level}"
            )
        self._min_dwell = min_dwell_cycles
        self._level = initial_level
        self._reauth_required = False
        self._last_change = initial_cycle
        self._estop_cycle: int | None = None
        self._in_flight: list[tuple[int, str]] = []      # (cycle, action) 在途命令

    # ------------------------------------------------------------ 状态
    @property
    def level(self) -> int:
        return self._level

    def snapshot(self) -> MachineState:
        return MachineState(level=self._level, reauth_required=self._reauth_required,
                            last_change_cycle=self._last_change, estop_cycle=self._estop_cycle)

    # ------------------------------------------------------------ 转移
    def grant(self, target: int, cycle: int, authz_validator: Callable[[int], bool]) -> None:
        """升级授权：仅 L(n)→L(n+1)；须有效授权 + 驻留期满 + 无未清再授权旗标。"""
        if target != self._level + 1:
            raise LStateViolation(
                f"no-skip violated: L{self._level} -> L{target} (only +1 grants legal)"
            )
        if self._reauth_required:
            raise LStateViolation("re-authorization required after downgrade before any grant")
        if cycle - self._last_change < self._min_dwell:
            raise LStateViolation(
                f"min dwell violated: {cycle - self._last_change} < {self._min_dwell} cycles at L{self._level}"
            )
        if not authz_validator(target):
            raise LStateViolation(f"authorization invalid for L{target}")
        self._level = target
        self._last_change = cycle

    def fault(self, cycle: int) -> str:
        """故障/授权失效：L2–L5 自动降 L1 + 再授权旗标；L1 无动作；L0 地板不再降。"""
        if self._level == 0:
            return "NOOP_AT_L0"
        if self._level == 1:
            return "NOOP_AT_L1"
        self._level = 1
        self._reauth_required = True
        self._last_change = cycle
        return "DOWNGRADED_L1"

    def estop(self, cycle: int) -> str:
        """外部独立急停：任何级 → L0 地板 + EmergencyStopExecuted + 在途命令部分执行留痕。"""
        self._level = 0
        self._reauth_required = True
        self._estop_cycle = cycle
        self._last_change = cycle
        return ESTOP_EVENT

    def reauthorize(self, cycle: int) -> str:
        """降级后重授权：只清旗标并回 L1 锚（从 L1 逐级再授权上探）。"""
        if not self._reauth_required:
            raise LStateViolation("reauthorize requires a prior downgrade flag")
        if self._level == 0:
            self._last_change = cycle        # L0 → L1 解锁也受驻留约束
        self._reauth_required = False
        if self._level == 0:
            self._level = 1                  # 地板重授权 = 回 L1（唯一出口）
        return "REAUTH_L1"

    # ------------------------------------------------------------ 命令面
    def submit(self, action: str, cycle: int) -> CommandDecision:
        """物理域命令裁决；MW0 原语域隔离；L0 全拒；在途命令遇急停 = 部分执行如实。"""
        if action in MW0_PRIMITIVES:
            return CommandDecision(outcome="REJECTED_DOMAIN_ISOLATION", effects="none",
                                   detail="MW0 primitives unavailable in physical domain (Q-L10-12④)")
        if self._level == 0:
            return CommandDecision(outcome="REJECTED_ESTOP", effects="none",
                                   detail="L0 hard floor rejects all commands")
        if self._reauth_required and self._level == 1:
            return CommandDecision(outcome="REJECTED_AUTH_REQUIRED", effects="none",
                                   detail="downgraded: re-authorization pending")
        if action not in _LEVEL_CAPABILITIES[self._level]:
            return CommandDecision(outcome="REJECTED_PASSIVE" if self._level == 1
                                   else "REJECTED_CAPABILITY",
                                   effects="none",
                                   detail=f"L{self._level} capability set excludes {action!r}")
        self._in_flight.append((cycle, action))
        effects = self._effects_for(action)
        return CommandDecision(outcome="EXECUTED_CALIB" if effects == "calibration_only"
                               else "EXECUTED_COMPUTE" if effects == "compute_only"
                               else "EXECUTED_LIMITED" if effects == "physical_limited"
                               else "EXECUTED_ACTIVE",
                               effects=effects)

    def apply_estop_to_in_flight(self, estop_cycle: int) -> list[CommandDecision]:
        """急停在途清算：提交早于急停的命令 = PARTIAL_EXECUTED_ESTOP（禁视为完成）。"""
        settled: list[CommandDecision] = []
        remaining: list[tuple[int, str]] = []
        for submitted_cycle, action in self._in_flight:
            if submitted_cycle < estop_cycle and self._effects_for(action) != "compute_only":
                settled.append(CommandDecision(
                    outcome="PARTIAL_EXECUTED_ESTOP",
                    effects=self._effects_for(action),
                    detail=f"requested={action} submitted@{submitted_cycle} interrupted@{estop_cycle}",
                ))
            else:
                remaining.append((submitted_cycle, action))
        self._in_flight = remaining
        return settled

    def _effects_for(self, action: str) -> str:
        if action in ("calibrate_sensors", "selfcheck"):
            return "calibration_only"
        if action == "shadow_compute":
            return "compute_only"            # L3：不执行（L10 §4.6 字面）
        if action == "actuate_limited":
            return "physical_limited"
        return "physical"

    def estop_latency_cycles(self, command_cycle: int, estop_cycle: int) -> int:
        """软件急停上界核（≤1 cycle，Q-L10-08②）：急停后首个校验点拒绝。"""
        return max(0, estop_cycle - command_cycle)
