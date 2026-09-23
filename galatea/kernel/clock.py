"""多速率虚拟时钟（L00 §4.2；Q-T12 CONFIRMED：virtual_time 是唯一时间源）。

纪律：墙钟只允许出现在 recorder manifest 独立字段（L13）；本模块是全系统
唯一时间源。cycle→墙钟绝对换算属 Q-G00-01（指针未启用），故虚拟纳秒与
cycle 同步单调（1 ns/cycle 恒等映射），不引入任何未裁决换算常数。
"""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VirtualTime:
    """逻辑时刻：cycle 号 + 单调不减虚拟纳秒。"""

    cycle_id: int
    virtual_time_ns: int


class CycleClock:
    """单调逻辑时钟。非负推进；无回拨；无墙钟。"""

    def __init__(self) -> None:
        self._cycle: int = 0

    def now(self) -> VirtualTime:
        return VirtualTime(cycle_id=self._cycle, virtual_time_ns=self._cycle)

    @property
    def cycle(self) -> int:
        return self._cycle

    def advance_to(self, cycle: int) -> VirtualTime:
        if cycle < self._cycle:
            raise ValueError(f"clock regression: {cycle} < {self._cycle}")
        self._cycle = cycle
        return self.now()

    def advance(self) -> VirtualTime:
        return self.advance_to(self._cycle + 1)
