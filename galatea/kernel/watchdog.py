"""协作点超时看门狗（L00 §4.1/§6.2）。

协作式单线程（Q-T01 主体平面禁线程）：超时不能中断当前处理片，而是在
协作点（handler 返回后）由 check() 检出并注入 TimeoutEvent（类型化事件，
随该模块下一批投递）——这是 L00 §4.1 "超时由 watchdog 注入 TimeoutEvent"
的机械实现，禁改写为静默忽略。
"""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TimeoutEvent:
    """模块超时类型化事件（注入包队列；计数入指标）。"""

    module_id: str
    deadline_ns: int
    virtual_time_ns: int


class Watchdog:
    """登记各模块 deadline；协作点检查到期。

    每模块至多一个未决 deadline：重复登记抛 ValueError（既有行为文档化，
    ADR-G-0003 R9⑧；多 deadline 需求出现时经 L00 SPEC 修订）。
    """

    def __init__(self) -> None:
        self._deadlines: dict[str, int] = {}

    def register(self, module_id: str, deadline_ns: int) -> None:
        if module_id in self._deadlines:
            raise ValueError(f"deadline already registered for {module_id!r}")
        self._deadlines[module_id] = deadline_ns

    def check(self, module_id: str, virtual_time_ns: int) -> tuple[TimeoutEvent, ...]:
        """返回该模块已到期（deadline < 当前虚拟时间）的事件并清除登记。"""
        deadline = self._deadlines.get(module_id)
        if deadline is None or virtual_time_ns <= deadline:
            return ()
        del self._deadlines[module_id]
        return (TimeoutEvent(module_id=module_id, deadline_ns=deadline, virtual_time_ns=virtual_time_ns),)
