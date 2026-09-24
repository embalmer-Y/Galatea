"""调度 tie-break 全序、T0 抢占与超时注入（L00 §4.1/§6.2；Q-T04）。"""
from collections.abc import Callable

import pytest

from galatea.kernel.clock import CycleClock
from galatea.kernel.packet import CognitivePacket
from galatea.kernel.rng import RngDirectory, reference_block_blake2s
from galatea.kernel.scheduler import DispatchContext, Registration, Scheduler
from galatea.kernel.watchdog import Watchdog

Out = tuple[CognitivePacket, ...]
RegFactory = Callable[[str, int, int], Registration]


def _build(
    log: list[str], watchdog: Watchdog | None = None
) -> tuple[Scheduler, RegFactory]:
    clock = CycleClock()
    rng = RngDirectory(b"seed", reference_block_blake2s)

    def handler(ctx: DispatchContext) -> Out:
        log.append(f"{ctx.due_cycle}:{ctx.module_id}")
        return ()

    sched = Scheduler(clock, rng, run_id="R", branch_id="B", subject_candidate_id="S", watchdog=watchdog)

    def mk(mid: str, t: int, p: int) -> Registration:
        return Registration(module_id=mid, t_level=t, period_cycles=p, handler=handler)

    return sched, mk


def test_same_due_ordered_by_t_level_then_module_id() -> None:
    log: list[str] = []
    sched, mk = _build(log)
    # 注册序故意逆序：派发序必须仍按 (due, t_level, module_id) 全序
    sched.register(mk("bb", 2, 1))
    sched.register(mk("aa", 2, 1))
    sched.register(mk("t0", 0, 1))
    sched.run_until(3)
    assert log == ["1:t0", "1:aa", "1:bb", "2:t0", "2:aa", "2:bb", "3:t0", "3:aa", "3:bb"]


def test_t0_preempts_at_same_cycle() -> None:
    log: list[str] = []
    sched, mk = _build(log)
    sched.register(mk("slow", 2, 2))   # 到期 2,4,6,8…
    sched.register(mk("t0mod", 0, 4))  # 到期 4,8…
    sched.run_until(8)
    # cycle 4 与 cycle 8 双到期：T0 抢占（t0mod 先于 slow）
    assert log == ["2:slow", "4:t0mod", "4:slow", "6:slow", "8:t0mod", "8:slow"]


def test_timeout_injected_at_cooperation_point() -> None:
    log: list[str] = []
    seen_timeouts: list[int] = []
    wd = Watchdog()
    wd.register("slow", deadline_ns=5)

    clock = CycleClock()
    rng = RngDirectory(b"seed", reference_block_blake2s)
    sched = Scheduler(clock, rng, run_id="R", branch_id="B", subject_candidate_id="S", watchdog=wd)

    def slow_handler(ctx: DispatchContext) -> Out:
        seen_timeouts.append(len(ctx.timeouts))
        log.append(f"{ctx.due_cycle}:slow")
        return ()

    sched.register(Registration(module_id="slow", t_level=2, period_cycles=2, handler=slow_handler))
    sched.run_until(8)
    # cycle 2,4 未超时；cycle 6 时 6>5 超时在协作点被检出；cycle 8 的批收到 1 条 TimeoutEvent
    assert log == ["2:slow", "4:slow", "6:slow", "8:slow"]
    assert seen_timeouts == [0, 0, 0, 1]


def test_registration_validation() -> None:
    log: list[str] = []
    sched, mk = _build(log)
    sched.register(mk("m", 2, 1))
    with pytest.raises(ValueError):
        sched.register(mk("m", 2, 1))  # 重复注册
    with pytest.raises(ValueError):
        sched.register(mk("m2", 7, 1))  # t_level 越界
    with pytest.raises(ValueError):
        sched.register(mk("m3", 2, 0))  # period 非法


def test_broadcast_pool_pruned_after_full_consumption() -> None:
    """广播池剪枝（R9⑤）：全部模块消费后包退出池，长跑内存有界。"""
    from galatea.kernel.packet import AccessScope, ArtifactRef, RepresentationLevel, UlidFactory, make_packet

    log: list[str] = []
    sched, mk = _build(log)

    def emitter(ctx: DispatchContext) -> Out:
        ulid = UlidFactory(sched._rng_directory.stream("B", "em", "ulid"), lambda: ctx.virtual_time)  # noqa: SLF001
        packet = make_packet(
            event_id=ulid.new(), subject_candidate_id="S", run_id="R", branch_id="B",
            activity_window_id="W", cycle_id=ctx.due_cycle, virtual_time=ctx.virtual_time,
            source_module="em", content_type="t.v1", representation_level=RepresentationLevel.PREDICTED,
            schema_version="v1", payload_ref=ArtifactRef(digest="0" * 64, kind="payload"),
            confidence=0.5, access_scope=AccessScope.PUBLIC_BROADCAST,
        )
        sched.submit(packet)
        return ()

    clock = CycleClock()
    rng = RngDirectory(b"seed", reference_block_blake2s)
    sched = Scheduler(clock, rng, run_id="R", branch_id="B", subject_candidate_id="S")

    def emit_handler(ctx: DispatchContext) -> Out:
        if ctx.due_cycle <= 62:  # 停发两拍：末包可被全员消费并剪除
            return emitter(ctx)
        return ()

    def sink(ctx: DispatchContext) -> Out:
        log.append(f"{ctx.due_cycle}:{ctx.module_id}:{len(ctx.packets)}")
        return ()

    sched.register(Registration("em", 1, 1, emit_handler))
    sched.register(Registration("s1", 2, 1, sink))
    sched.register(Registration("s2", 2, 2, sink))
    sched.run_until(65)  # 末包（cycle 64）需发射者下拍消费后方可剪除
    assert sched._broadcast == []  # noqa: SLF001  全部消费后池已剪空
    assert len(sched._consumed) == 0  # noqa: SLF001
