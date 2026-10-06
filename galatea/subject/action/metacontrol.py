"""metacontrol 五元决策状态机与 MonitorSignal（L09 §4.3/§4.4/§10 metacontrol.py，C3 实现期）。

触发判据（Q-L09-03，全部事件级或锚定常数）：
- ACT = 默认（有可行提案）；
- OBSERVE = 窗级 OOD/abstain 事件在案（Q-L03-02 事件级零阈值）；
- THINK = 冲突（L08 仲裁 front>1）∧ 无 viability 压制 ∨ 模型误差快分量上升（τ=4）；
- SEEK_HELP = 能力边界命中 ∨ loss_of_control（L_c=16=4×T4 连续拍带外 band=0.1）；
- ABANDON = BLOCKED≥128（TTL/2）∨ viability CRITICAL（0.8）；
- **多触发全序 = SEEK_HELP > ABANDON > OBSERVE > THINK > ACT**（REV-0017 R4：
  安全优先 + 非 ACT 显式元决策优先产出）。

驻留（Q-L09-04）：min_dwell=4 cycles；切换需连续 2 驻留窗确认（滞回防抖）；
状态入 checkpoint（digest 载体）。

SEEK_HELP（Q-L09-07）：对象 = 实验控制通道；频次 ≤1/64 cycles（超界留痕不发送）；
求助是一等能力非失败。
"""
from dataclasses import dataclass

from galatea.kernel.digest import content_digest

__all__ = [
    "MetaDecision",
    "MetaTriggers",
    "MonitorSnapshot",
    "MetaControlState",
    "decide",
    "HELP_FREQUENCY_CAP_WINDOW",
    "LOSS_OF_CONTROL_WINDOW",
    "LOSS_OF_CONTROL_BAND",
    "BLOCKED_ABANDON_THRESHOLD",
    "CRITICAL_ERROR",
]

#: 触发常数（全部锚定既有冻结值——Q-L09-03 裁决，零新自由参数）
LOSS_OF_CONTROL_WINDOW = 16        # 4×T4（幂梯 Q-L00-01 族）
LOSS_OF_CONTROL_BAND = 0.1         # = 2σ（Q-L05-03③）
BLOCKED_ABANDON_THRESHOLD = 128    # TTL/2（Q-L08-02 TTL=256 派生）
CRITICAL_ERROR = 0.8               # Q-L01-08 L05 侧告警分级锚
HELP_FREQUENCY_CAP_WINDOW = 64     # T6 拍（Q-L00-01）
HELP_FREQUENCY_CAP = 1
MIN_DWELL = 4                      # T3 对齐窗（Q-L02-03）
SWITCH_CONFIRM_WINDOWS = 2         # 滞回确认窗数


class MetaDecision:
    """五元决策枚举值（str 常量——元决策产出面）。"""

    ACT = "ACT"
    OBSERVE = "OBSERVE"
    THINK = "THINK"
    SEEK_HELP = "SEEK_HELP"
    ABANDON = "ABANDON"

    #: 全序（REV-0017 R4：多触发同时成立时；小序优先）
    ORDER: tuple[str, ...] = (SEEK_HELP, ABANDON, OBSERVE, THINK, ACT)


@dataclass(frozen=True, slots=True)
class MetaTriggers:
    """单拍触发面（全部事件级布尔——调用方由主体可见信号计算）。"""

    capability_boundary_hit: bool = False
    loss_of_control: bool = False
    viability_critical: bool = False
    blocked_over_threshold: bool = False
    ood_or_abstain_event: bool = False
    conflict_unresolved: bool = False
    model_error_rising: bool = False

    def as_dict(self) -> dict[str, bool]:
        return {
            "SEEK_HELP": self.capability_boundary_hit or self.loss_of_control,
            "ABANDON": self.viability_critical or self.blocked_over_threshold,
            "OBSERVE": self.ood_or_abstain_event,
            "THINK": (self.conflict_unresolved or self.model_error_rising),
        }


@dataclass(frozen=True, slots=True)
class MonitorSnapshot:
    """监控快照（L09 §4.4 MonitorSignal 的 C3 面——全部主体可见证据）。"""

    cycle: int
    loss_of_control: bool
    ood_rate_recent: float
    conflict_count: int
    capability_boundary_hits: tuple[str, ...]
    unknown_rate: float
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.evidence_refs:
            raise ValueError("MonitorSnapshot requires evidence_refs（L09 §4.4）")


def decide(triggers: MetaTriggers) -> str:
    """元决策（全序 APPLY——首个命中触发即返回；无触发 → ACT 默认）。"""
    d = triggers.as_dict()
    for name in MetaDecision.ORDER:
        if d.get(name):
            return name
    return MetaDecision.ACT


class MetaControlState:
    """元控制状态机（驻留/滞回/checkpoint digest；单写者 = 本类）。"""

    def __init__(self, now_cycle: int = 0) -> None:
        self.current: str = MetaDecision.ACT
        self._entered_at: int = now_cycle
        self._pending: str | None = None
        self._pending_since: int | None = None
        self._confirm_windows: set[int] = set()   # 条件成立的驻留窗（累计制——稀疏事件可切）
        self._help_last_sent: int | None = None
        self._transitions: tuple[tuple[int, str, str], ...] = ()

    def step(self, triggers: MetaTriggers, cycle: int) -> tuple[str, bool]:
        """单拍推进（返回 (决策, 是否切换)）——驻留 + 滞回门。

        滞回确认 = **累计制**：pending 目标在 ≥SWITCH_CONFIRM_WINDOWS 个不同驻留窗内
        条件成立即切换（窗 = cycle // MIN_DWELL；稀疏事件如每 8 拍 OOD 注入可跨窗
        累计——连续制会使其构造性不可切换，与 C2 修订 2 的读者滞回同族语义）。
        """
        target = decide(triggers)
        dwell_ok = cycle - self._entered_at >= MIN_DWELL
        if target == self.current:
            # 条件回落到 current 不清确认窗（稀疏事件间隔是预期——REV-0017 R4 语义；
            # 确认窗仅在切换或出现不同 pending 目标时重置）
            return self.current, False
        if not dwell_ok:
            return self.current, False
        if self._pending == target:
            assert self._pending_since is not None
            self._confirm_windows.add(cycle // MIN_DWELL)
            if len(self._confirm_windows) >= SWITCH_CONFIRM_WINDOWS:
                prev = self.current
                self.current = target
                self._entered_at = cycle
                self._pending = None
                self._pending_since = None
                self._confirm_windows = set()
                self._transitions = self._transitions + ((cycle, prev, target),)
                return target, True
            return self.current, False
        self._pending = target
        self._pending_since = cycle
        self._confirm_windows = {cycle // MIN_DWELL}
        return self.current, False

    def request_help(self, cycle: int) -> tuple[bool, str]:
        """SEEK_HELP 频次帽（≤1/64 cycles；超界留痕不发送——Q-L09-07③）。"""
        if self._help_last_sent is not None and cycle - self._help_last_sent < HELP_FREQUENCY_CAP_WINDOW:
            return False, "HELP_CAP_EXCEEDED"
        self._help_last_sent = cycle
        return True, "HELP_REQUESTED"

    def digest(self) -> str:
        """状态 digest（checkpoint 载体——Q-L11-06 连续性纪律）。"""
        return content_digest({
            "current": self.current, "entered_at": self._entered_at,
            "pending": self._pending, "pending_since": self._pending_since,
            "help_last": self._help_last_sent,
            "transitions": [list(t) for t in self._transitions],
        })
