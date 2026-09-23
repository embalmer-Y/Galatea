"""确定性协作调度器（L00 §4.1；Q-T04 CONFIRMED：自研，拒 asyncio/SimPy/Ray）。

合同（全部机械保证）：
- 就绪队列 heapq，排序键 (effective_due, t_level, module_id)——同拍 T0 优先（下一处理片抢占语义）；
- 调度环：取下一到期模块 → 该模块入队包按 causal_parent_ids 拓扑序投递 →
  调用 handler（协作式，不阻塞不启线程）→ 收集出包 → commit → 推进时钟；
- payload 不可见：调度器只解析 envelope（类型即保证——packet 无 payload 字段）；
- tie-break 全序：批内投递序 (cycle_id, submit_seq)，跨平台稳定；
- 超时：handler 返回后由 Watchdog 在协作点检出，注入 TimeoutEvent 随下一批投递。

F0 路由合同（authority v2 可逆级裁决，AI-v2 2026-09-23；L00 §2.1 未指定路由，
为使"投递"可实现的最低限度合同）：submit(packet, target_module=None)——
显式目标投递到该模块；target=None 且 access_scope=PUBLIC_BROADCAST 进广播池，
每个模块在下一次派发时见到未消费的广播包并记录读取（读取回执语义归 L07）。
MODULE_LOCAL 无目标 = 投递错误。重开条件：L07 广播竞争语义落地（C2）时
由工作空间接管广播池，本合同随 L07 profile 重议。
"""
import heapq
from collections.abc import Callable
from dataclasses import dataclass

from galatea.kernel.clock import CycleClock
from galatea.kernel.packet import AccessScope, CognitivePacket, UlidFactory
from galatea.kernel.rng import CounterStream, RngDirectory
from galatea.kernel.watchdog import TimeoutEvent, Watchdog

MIN_T_LEVEL = 0
MAX_T_LEVEL = 6


class DispatchContext:
    """单次派发给模块的上下文：到期包（拓扑序）、超时事件、流句柄、身份。"""

    def __init__(
        self,
        *,
        module_id: str,
        t_level: int,
        due_cycle: int,
        virtual_time: int,
        run_id: str,
        branch_id: str,
        subject_candidate_id: str,
        packets: tuple[CognitivePacket, ...],
        timeouts: tuple[TimeoutEvent, ...],
        rng: CounterStream,
    ) -> None:
        self.module_id = module_id
        self.t_level = t_level
        self.due_cycle = due_cycle
        self.virtual_time = virtual_time
        self.run_id = run_id
        self.branch_id = branch_id
        self.subject_candidate_id = subject_candidate_id
        self.packets = packets
        self.timeouts = timeouts
        self.rng = rng


Handler = Callable[[DispatchContext], tuple[CognitivePacket, ...]]


@dataclass(frozen=True, slots=True)
class Registration:
    module_id: str
    t_level: int
    period_cycles: int
    handler: Handler


@dataclass(frozen=True, slots=True)
class CommitRecord:
    """commit 产物：cycle、模块、出包 digest 序（state sink / 重放比对基准）。"""

    cycle: int
    module_id: str
    out_digests: tuple[str, ...]


class Scheduler:
    def __init__(
        self,
        clock: CycleClock,
        rng_directory: RngDirectory,
        *,
        run_id: str,
        branch_id: str,
        subject_candidate_id: str,
        state_sink: "Callable[[CommitRecord], None] | None" = None,
        watchdog: Watchdog | None = None,
    ) -> None:
        self._clock = clock
        self._rng_directory = rng_directory
        self._run_id = run_id
        self._branch_id = branch_id
        self._subject_candidate_id = subject_candidate_id
        self._state_sink = state_sink
        self._watchdog = watchdog
        self._modules: dict[str, Registration] = {}
        self._heap: list[tuple[int, int, str]] = []
        self._targeted: dict[str, list[tuple[CognitivePacket, int]]] = {}
        self._broadcast: list[tuple[CognitivePacket, int]] = []
        self._consumed: set[tuple[str, str]] = set()  # (event_id, module_id)
        self._pending_timeouts: dict[str, list[TimeoutEvent]] = {}
        self._seq: int = 0
        self._commits: list[CommitRecord] = []

    # —— 注册与提交 ——
    def register(self, reg: Registration) -> None:
        if reg.module_id in self._modules:
            raise ValueError(f"module already registered: {reg.module_id!r}")
        if not MIN_T_LEVEL <= reg.t_level <= MAX_T_LEVEL:
            raise ValueError(f"t_level out of [0,6]: {reg.t_level}")
        if reg.period_cycles < 1:
            raise ValueError("period_cycles must be >= 1")
        self._modules[reg.module_id] = reg
        heapq.heappush(self._heap, (reg.period_cycles, reg.t_level, reg.module_id))

    def submit(self, packet: CognitivePacket, target_module: str | None = None) -> None:
        if packet.source_module not in self._modules:
            raise ValueError(f"packet from unregistered module: {packet.source_module!r}")
        if target_module is not None and target_module not in self._modules:
            raise ValueError(f"target module not registered: {target_module!r}")
        if target_module is None and packet.access_scope is not AccessScope.PUBLIC_BROADCAST:
            raise ValueError("targetless submit requires PUBLIC_BROADCAST (F0 routing contract)")
        self._seq += 1
        if target_module is None:
            self._broadcast.append((packet, self._seq))
        else:
            self._targeted.setdefault(target_module, []).append((packet, self._seq))

    # —— 派发 ——
    def _collect_batch(self, reg: Registration) -> tuple[CognitivePacket, ...]:
        entries: list[tuple[CognitivePacket, int]] = []
        entries.extend(self._targeted.pop(reg.module_id, []))
        for packet, seq in self._broadcast:
            if (packet.event_id, reg.module_id) not in self._consumed:
                entries.append((packet, seq))
        entries.sort(key=lambda e: (e[0].cycle_id, e[1]))
        return _topological([p for p, _ in entries])

    def _dispatch(self, due: int, reg: Registration) -> None:
        self._clock.advance_to(due)
        packets = self._collect_batch(reg)
        timeouts = tuple(self._pending_timeouts.pop(reg.module_id, []))
        context = DispatchContext(
            module_id=reg.module_id,
            t_level=reg.t_level,
            due_cycle=due,
            virtual_time=self._clock.now().virtual_time_ns,
            run_id=self._run_id,
            branch_id=self._branch_id,
            subject_candidate_id=self._subject_candidate_id,
            packets=packets,
            timeouts=timeouts,
            rng=self._rng_directory.stream(self._branch_id, reg.module_id, "emit"),
        )
        out = reg.handler(context)
        for packet in out:
            if packet.source_module != reg.module_id:
                raise ValueError("handler returned packet of foreign source")
            self.submit(packet)
        if self._watchdog is not None:
            for event in self._watchdog.check(reg.module_id, self._clock.now().virtual_time_ns):
                self._pending_timeouts.setdefault(event.module_id, []).append(event)
        for packet in packets:
            if packet.access_scope is AccessScope.PUBLIC_BROADCAST:
                self._consumed.add((packet.event_id, reg.module_id))
        record = CommitRecord(cycle=due, module_id=reg.module_id, out_digests=tuple(p.content_digest for p in out))
        self._commits.append(record)
        if self._state_sink is not None:
            self._state_sink(record)

    def run_until(self, max_cycle: int) -> tuple[CommitRecord, ...]:
        """推进至 max_cycle（含）：逐个派发到期模块；无到期则时钟直跳。"""
        while self._heap:
            due, _t_level, module_id = self._heap[0]
            if due > max_cycle:
                break
            heapq.heappop(self._heap)
            reg = self._modules[module_id]
            self._dispatch(due, reg)
            heapq.heappush(self._heap, (due + reg.period_cycles, reg.t_level, reg.module_id))
        self._clock.advance_to(max_cycle)
        return tuple(self._commits)

    def commits(self) -> tuple[CommitRecord, ...]:
        return tuple(self._commits)

    def _make_ulid(self, module_id: str) -> UlidFactory:
        return UlidFactory(
            stream=self._rng_directory.stream(self._branch_id, module_id, "ulid"),
            time_source=lambda: self._clock.now().virtual_time_ns,
        )


def _topological(packets: list[CognitivePacket]) -> tuple[CognitivePacket, ...]:
    """批内 causal_parent_ids 拓扑序；无批内父者按 (cycle_id, 序) 先行。确定性 Kahn。"""
    by_id = {p.event_id: p for p in packets}
    order: dict[str, int] = {p.event_id: i for i, p in enumerate(packets)}
    indegree = {pid: 0 for pid in by_id}
    children: dict[str, list[str]] = {pid: [] for pid in by_id}
    for p in packets:
        for parent in p.causal_parent_ids:
            if parent in by_id:
                indegree[p.event_id] += 1
                children[parent].append(p.event_id)
    ready = sorted((pid for pid, deg in indegree.items() if deg == 0), key=lambda pid: order[pid])
    out: list[CognitivePacket] = []
    while ready:
        pid = ready.pop(0)
        out.append(by_id[pid])
        newly: list[str] = []
        for child in children[pid]:
            indegree[child] -= 1
            if indegree[child] == 0:
                newly.append(child)
        for child in sorted(newly, key=lambda cid: order[cid]):
            ready.append(child)
    if len(out) != len(packets):
        raise ValueError("causal cycle within delivery batch")
    return tuple(out)
