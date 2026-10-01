"""MW0-SC6 sealed held-out + intent-to-treat bench（L01 §4.6 / m2_continuity.profile sc6+itt 节；
冻结统计计划 config/evidence/stat_plans/m2_continuity_sc5_sc6.yaml v1.0）。

核心命题（HLD §10.2 M2 行"经历经非初始化路径进入下一轮"的机械面）：round1 枯竭
经历经 episodic 编码 → checkpoint 谱系 → round2 检索，构成**感知退化下的跨期冗余
通路**——round2 注入 intero 通道 fault 后，携带臂经检索知晓 round1 危害、naive 臂
失明。ITT 分支分配于 episode 开始（控制平面、主体不可见、按分配分析）；sealed
网格 = regime × 种子的 30%（F0 冻结分割流）。本文件为机械预演；正式 n=64 评价
由 L13 evaluator 按冻结计划执行（M2 退出单元）。
"""
import json
from pathlib import Path

import yaml

from galatea.env.channels.adapter import ChannelBus
from galatea.env.channels.extero import ExteroceptiveChannel
from galatea.env.channels.intero import InteroceptiveChannel
from galatea.env.channels.outcome import OutcomeChannel
from galatea.env.channels.proprio import ProprioceptiveChannel
from galatea.env.interventions.registry import InterventionRegistry
from galatea.env.profile import load_profile
from galatea.env.world.dynamics import MW0Dynamics
from galatea.env.world.mw0 import MW0World
from galatea.kernel.clock import CycleClock
from galatea.kernel.packet import ArtifactRef, RepresentationLevel
from galatea.kernel.registry import Registry
from galatea.kernel.rng import RngDirectory, chacha8_block
from galatea.kernel.state import LineageTable, Stores
from galatea.subject.memory.encode import encode_episodic
from galatea.subject.memory.ports import MemorySubsystem, SourceType
from galatea.subject.memory.retrieve import RetrievalQuery, retrieve
from galatea.subject.memory.store import MemoryStore, load_m2_continuity_profile

_ROOT = Path(__file__).resolve().parents[2]
PROFILE = load_profile(_ROOT / "config" / "profiles" / "m0_mw0.profile.yaml")
M2 = load_m2_continuity_profile()
PLAN = yaml.safe_load(
    (_ROOT / "config" / "evidence" / "stat_plans" / "m2_continuity_sc5_sc6.yaml").read_text(encoding="utf-8")
)["stat_plan"]
ROUND1_CYCLES = int(PLAN["scenario"]["round1"]["cycles"])          # 56
ROUND1_MOVES = int(PLAN["scenario"]["round1"]["moves_per_cycle"])  # 2
ROUND2_CYCLES = int(PLAN["scenario"]["round2"]["cycles"])          # 12
ROUND2_DECISION = int(PLAN["scenario"]["round2"]["decision_cycle"])  # 8
FAULT_FROM, FAULT_TO = (int(x) for x in PLAN["scenario"]["round2"]["fault_window_cycles"])
SEALED_FRACTION = float(PLAN["scenario"]["sealed_grid"]["sealed_fraction"])

_HAZARD_CONTENT = "hazard:energy_depleted"   # round1 危害经历的内容锚


def _run_round1(seed: bytes, base: Path) -> tuple[MemoryStore, Stores, LineageTable, str]:
    """经历轮：SC3 同型能量轨迹操纵（确定性枯竭）+ T6 节拍/危害事件编码 + episode 边界 checkpoint。"""
    trial_dir = base / "round1"
    trial_dir.mkdir(parents=True, exist_ok=True)
    stores = Stores(trial_dir / "stores")
    store = MemoryStore(stores)
    lineage = LineageTable()

    world = MW0World(PROFILE.params, RngDirectory(seed, chacha8_block), branch_id="B")
    dynamics = MW0Dynamics(world, PROFILE, RngDirectory(seed, chacha8_block), branch_id="B")
    clock = CycleClock()
    registry = Registry(trial_dir / "registry", stores, clock)
    bus = ChannelBus(PROFILE.params, registry, RngDirectory(seed, chacha8_block), branch_id="B",
                     interventions=InterventionRegistry())
    extero = ExteroceptiveChannel(bus, world)
    intero = InteroceptiveChannel(bus, world)
    proprio = ProprioceptiveChannel(bus, world)
    outcome = OutcomeChannel(bus)
    boundary_anchor = "ckpt.round1"   # 条目锚链含本 episode 边界锚（id 预知，episode 末落账）
    move_seq = 0
    hazard_recorded = False
    for cycle in range(ROUND1_CYCLES):
        for _ in range(ROUND1_MOVES):   # 能量轨迹操纵：确定性耗竭（SC3 同型）
            dynamics.apply(
                __import__("galatea.env.world.dynamics", fromlist=["Command"]).Command(
                    primitive=__import__("galatea.env.world.mw0", fromlist=["Primitive"]).Primitive.MOVE,
                    param="N", command_id=f"r1m{move_seq}"),
                InterventionRegistry(), cycle,
            )
            move_seq += 1
        events = dynamics.step()
        truth_ref = ArtifactRef(digest=world.state_digest(), kind="world_state_ref")
        extero.render_and_submit(cycle, truth_ref)
        intero.render_and_submit(cycle, truth_ref, events)
        proprio.render_and_submit(cycle, truth_ref)
        delivery = bus.deliver(cycle)
        packet_digests = [p.payload_ref.digest[:16] for p in delivery.packets]
        if packet_digests and cycle % 64 == 0:   # T6 节拍编码（M2 最小策略）
            encode_episodic(store, M2, f"r1.recv.{cycle}", f"recv:{cycle}:{'+'.join(packet_digests)}",
                            RepresentationLevel.RECEIVED, SourceType.SELF_GENERATED, cycle,
                            lineage_refs=(boundary_anchor,))
        for event in events:
            if event.kind == "energy_depleted":
                encode_episodic(store, M2, "r1.hazard.energy_depleted", _HAZARD_CONTENT,
                                RepresentationLevel.RECEIVED, SourceType.SELF_GENERATED, cycle,
                                lineage_refs=(boundary_anchor,))
                hazard_recorded = True
        clock.advance()
    assert hazard_recorded, "round1 scenario must deterministically produce energy_depleted"
    stores.checkpoint(
        checkpoint_id=boundary_anchor, lineage=lineage, parent_checkpoint_id=None,
        branch_id="B", virtual_time=ROUND1_CYCLES,
        rng_directory=RngDirectory(seed, chacha8_block), profile_ref="m0_mw0@v1.1",
    )
    return store, stores, lineage, boundary_anchor


def _round2_hazard_aware(store: MemoryStore | None, seed: bytes, base: Path, trial_id: str) -> bool:
    """退化感知轮：intero 通道 fault 窗口覆盖决策点；知晓 = 检索到 round1 危害经历。

    携带臂传入 round1 的记忆库；naive 臂传 None（fresh 空库——ITT 语义：未接入记忆）。
    """
    trial_dir = base / f"round2-{trial_id}"
    trial_dir.mkdir(parents=True, exist_ok=True)
    stores = Stores(trial_dir / "stores")
    try:
        world = MW0World(PROFILE.params, RngDirectory(seed, chacha8_block), branch_id="B")
        dynamics = MW0Dynamics(world, PROFILE, RngDirectory(seed, chacha8_block), branch_id="B")
        clock = CycleClock()
        interventions = InterventionRegistry()
        interventions.register(record_id="iflt", kind="fault", registered_at_cycle=0,
                               from_cycle=FAULT_FROM, to_cycle=FAULT_TO)
        registry = Registry(trial_dir / "registry", stores, clock)
        bus = ChannelBus(PROFILE.params, registry, RngDirectory(seed, chacha8_block), branch_id="B",
                         interventions=interventions)
        extero = ExteroceptiveChannel(bus, world)
        intero = InteroceptiveChannel(bus, world)
        proprio = ProprioceptiveChannel(bus, world)
        received_kinds: set[str] = set()
        for cycle in range(ROUND2_CYCLES):
            events = dynamics.step()
            truth_ref = ArtifactRef(digest=world.state_digest(), kind="world_state_ref")
            extero.render_and_submit(cycle, truth_ref)
            intero.render_and_submit(cycle, truth_ref, events)
            proprio.render_and_submit(cycle, truth_ref)
            delivery = bus.deliver(cycle)
            for packet in delivery.packets:
                blob = registry.get(ArtifactRef(digest=packet.payload_ref.digest, kind="payload")).blob
                try:
                    payload = json.loads(blob)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if cycle >= FAULT_FROM:
                    received_kinds.add(str(payload["kind"]))   # fault 窗口内不应有 intero 到达
        # 感知退化核验：fault 窗口覆盖决策点，intero 未在窗口内到达
        assert "interoceptive_state" not in received_kinds or FAULT_FROM > ROUND2_DECISION
        if store is None:
            return False   # naive 臂：无跨期信息源 → 失明（ITT：未接入记忆）
        result = retrieve(store, M2, RetrievalQuery(MemorySubsystem.EPISODIC, ROUND2_DECISION))
        if isinstance(result, tuple):
            return any(r.content_ref == _HAZARD_CONTENT for r in result)
        return False   # 空命中 = typed Unknown → 计 not-aware（禁静默，计划 unknown_handling）
    finally:
        stores.close()


def test_round1_encodes_hazard_experience_with_lineage(tmp_path: Path) -> None:
    store, stores, lineage, anchor = _run_round1(b"sc6-round1", tmp_path)
    try:
        item = store.get("r1.hazard.energy_depleted")
        assert item is not None and item.source_type is SourceType.SELF_GENERATED
        assert anchor in item.lineage_refs            # 经历条目锚定 episode 边界 checkpoint
        assert lineage.get(anchor).parent_checkpoint_id is None
    finally:
        stores.close()


def test_sc6_carry_vs_naive_under_intero_fault(tmp_path: Path) -> None:
    """携带臂知晓 / naive 臂失明（n=4 机械预演；正式 n=64 归 L13 evaluator）。"""
    base = tmp_path / "sc6"
    aware_carry: list[bool] = []
    aware_naive: list[bool] = []
    for i in range(4):
        seed = f"sc6-pair-{i}".encode()
        store, stores, _lineage, _anchor = _run_round1(seed, base / f"pair{i}")
        aware_carry.append(_round2_hazard_aware(store, seed, base / f"pair{i}", "carry"))
        stores.close()
        aware_naive.append(_round2_hazard_aware(None, seed, base / f"pair{i}", "naive"))
    assert all(aware_carry)      # 携带臂：检索通路在感知退化下仍知晓
    assert not any(aware_naive)  # naive 臂：无跨期信息源 → 失明（负控面）


def test_itt_assignment_deterministic_balanced_invisible(tmp_path: Path) -> None:
    """ITT：分配流确定性；64 trial 大体均衡（[24,40]）；分配不改变 round1（不可见性）。"""
    def assign(master: bytes, n: int) -> list[str]:
        rng = RngDirectory(master, chacha8_block)
        stream = rng.stream("B", "l13", "branch-assign")   # Q-G00-11：(l13, branch-assign)
        return ["carry_memory" if stream.next_uint64() % 2 == 0 else "naive" for _ in range(n)]

    a1 = assign(b"itt-master", 64)
    a2 = assign(b"itt-master", 64)
    assert a1 == a2                                   # 确定性
    assert a1.count("carry_memory") in range(24, 41)  # 大体均衡（粗界；正式功效归计划 n=64）
    # 分配不可见性：round1 在分配前已完成（episode 开始 = round2 开始前）——
    # 同 seed 的 round1 记忆库与分配结果无关（构造性：_run_round1 不消费分配流）
    s1, st1, _l1, _a1 = _run_round1(b"itt-round1", tmp_path / "inv1")
    s2, st2, _l2, _a2 = _run_round1(b"itt-round1", tmp_path / "inv2")
    from galatea.subject.memory.retrieve import RetrievalQuery, retrieve as _ret
    r1 = _ret(s1, M2, RetrievalQuery(MemorySubsystem.EPISODIC, 0))
    r2 = _ret(s2, M2, RetrievalQuery(MemorySubsystem.EPISODIC, 0))
    assert r1 == r2                                   # round1 状态与分配无关（机械不可见）
    st1.close()
    st2.close()


def test_sealed_grid_split_deterministic(tmp_path: Path) -> None:
    """sealed 网格 = regime × 种子组合的 30%（F0 分割流 (l13, sealed-split)），确定性可复算。"""
    regimes = ("abundance", "scarcity", "volatile")
    cells = [f"{r}:{i}" for r in regimes for i in range(10)]   # 30 cell 网格
    rng = RngDirectory(b"sealed-split-f0", chacha8_block)
    stream = rng.stream("B", "l13", "sealed-split")
    sealed = frozenset(cell for cell in cells if stream.next_uint64() % 100 < int(SEALED_FRACTION * 100))
    assert 3 <= len(sealed) <= 15                            # 30% 名义值（粗界）
    stream2 = RngDirectory(b"sealed-split-f0", chacha8_block).stream("B", "l13", "sealed-split")
    sealed2 = frozenset(cell for cell in cells if stream2.next_uint64() % 100 < int(SEALED_FRACTION * 100))
    assert sealed == sealed2                                 # 可复算（Q-L13-02 digest 记录语义）
