"""PhysIO 环境面（P1；env 侧——主体平面不可见原始物理量，L10 §4.6）。

纪律：
- 桥/状态机/能力面全部**非学习、非语义**（HLD §8 PhysIO 合同）；
- P06：本包禁依赖主体平面（import-linter 强制；被禁目标 = galatea.subject 模块）；
- 确定性：决策路径零 RNG 零墙钟（采样时间戳是数据不是决策）；
- typed loader fail-closed（INC-11）：profile 缺键即拒，禁运行时发明默认值。
"""
from __future__ import annotations

from galatea.env.physio.bridge import BridgeDelivery, PhysioBridge, TelemetryRecord
from galatea.env.physio.capability import CapabilityDecision, check_capability
from galatea.env.physio.hwmon import HwmonResolutionError, HwmonResolver
from galatea.env.physio.lstate import (
    ESTOP_EVENT,
    MW0_PRIMITIVES,
    CommandDecision,
    LStateViolation,
    MachineState,
    PhysioLStateMachine,
)
from galatea.env.physio.ports import (
    P1PhysioProfile,
    ProfileViolation,
    TelemetrySource,
    load_p1_physio_profile,
)

__all__ = [
    "BridgeDelivery",
    "CapabilityDecision",
    "CommandDecision",
    "ESTOP_EVENT",
    "HwmonResolutionError",
    "HwmonResolver",
    "LStateViolation",
    "MW0_PRIMITIVES",
    "MachineState",
    "P1PhysioProfile",
    "PhysioBridge",
    "PhysioLStateMachine",
    "ProfileViolation",
    "TelemetryRecord",
    "TelemetrySource",
    "check_capability",
    "load_p1_physio_profile",
]
