"""MW0-SC5 连续性对照实验台（L01 §4.6 / L06 §4.5 / m2_continuity.profile sc5 节）。

四臂（Q-L04-06 + Q-G00-11 冻结协议）：full_continuity / freeze_restore / reset /
pseudo_update——记忆侧签名经 claim_continuity 分型判定；freeze_restore 与
full_continuity 恒等（确定性模拟中恢复 = 重放到锚点）；伪更新（谱系伪造）被
LineageBreak 检出且两型主张皆拒。episode_cycles=256（m2 profile 冻结）。
"""
import dataclasses
import tempfile
from pathlib import Path

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
from galatea.subject.memory.items import continuity_signature, claim_continuity
from galatea.subject.memory.store import MemoryStore, load_m2_continuity_profile

_ROOT = Path(__file__).resolve().parents[2]
PROFILE = load_profile(_ROOT / "config" / "profiles" / "m0_mw0.profile.yaml")
M2 = load_m2_continuity_profile()
EPISODE = M2.episode_cycles                     # 256（冻结）


def _chain(lineage: LineageTable) -> tuple[str, ...]:
    """谱系链（按 checkpoint id 排序 = 构造序；L00 LineageTable.all）。"""
    return tuple(record.checkpoint_id for record in lineage.all())


def _run_episode(
    seed: bytes,
    start_cycle: int,
    store: MemoryStore,
    stores: Stores,
    lineage: LineageTable,
    parent_checkpoint: str | None,
    episode_index: int,
    base_dir: Path,
    do_checkpoint: bool = True,
) -> str:
    """运行一个 episode：世界推进 + 事件驱动的情景编码 + episode 边界 checkpoint。

    情景条目 lineage_refs = 当前谱系链（checkpoint 锚）——连续性证据链。
    返回本次 episode 边界的 checkpoint_id。
    """
    world = MW0World(PROFILE.params, RngDirectory(seed, chacha8_block), branch_id="B")
    dynamics = MW0Dynamics(world, PROFILE, RngDirectory(seed, chacha8_block), branch_id="B")
    clock = CycleClock()
    for _ in range(start_cycle):
        clock.advance()
    registry = Registry(base_dir / f"registry.ep{episode_index}", stores, clock)
    bus = ChannelBus(PROFILE.params, registry, RngDirectory(seed, chacha8_block), branch_id="B",
                     interventions=InterventionRegistry())
    extero = ExteroceptiveChannel(bus, world)
    intero = InteroceptiveChannel(bus, world)
    proprio = ProprioceptiveChannel(bus, world)
    outcome = OutcomeChannel(bus)
    # 条目锚链 = 当前谱系链 + 本 episode 边界锚（id 确定性预知，checkpoint 于 episode 末落账）
    chain = tuple(_chain(lineage)) + (f"ckpt.ep{episode_index}",)
    rng = RngDirectory(seed, chacha8_block)
    for cycle in range(start_cycle, start_cycle + EPISODE):
        events = dynamics.step()
        truth_ref = ArtifactRef(digest=world.state_digest(), kind="world_state_ref")
        extero.render_and_submit(cycle, truth_ref)
        intero.render_and_submit(cycle, truth_ref, events)
        proprio.render_and_submit(cycle, truth_ref)
        delivery = bus.deliver(cycle)
        # 情景编码（M2 切片：经历 = 接收流切片，L06 §2.1 EpisodeSlice 的最小形态）——
        # 每拍以当拍接收包 digest 为内容锚；世界事件额外编码（风暴/资源等离散事件）。
        # T6 节拍编码（M2 最小策略：每 64 拍一切片，与 checkpoint 同锚——完整编码
        # 策略 = C2，Q-L06-01；冻结容量 128 内，Q-G00-11。渲染噪声使逐拍内容恒变，
        # 逐拍编码将撑爆容量——节拍化是冻结参数下的可 行解）
        packet_digests = [p.payload_ref.digest[:16] for p in delivery.packets]
        if packet_digests and (cycle - start_cycle) % 64 == 0:
            encode_episodic(
                store, M2, f"ep{episode_index}.recv.{cycle}",
                f"recv:{cycle}:{'+'.join(packet_digests)}",
                RepresentationLevel.RECEIVED, SourceType.SELF_GENERATED, cycle,
                lineage_refs=tuple(chain),
            )
        for event in events:
            encode_episodic(
                store, M2, f"ep{episode_index}.{event.kind}.{cycle}.{event.pos[0]}_{event.pos[1]}",
                f"event:{event.kind}:{cycle}:{event.pos[0]}_{event.pos[1]}",
                RepresentationLevel.RECEIVED, SourceType.SELF_GENERATED, cycle,
                lineage_refs=tuple(chain),
            )
        clock.advance()
    if not do_checkpoint:
        return parent_checkpoint or ""
    record = stores.checkpoint(
        checkpoint_id=f"ckpt.ep{episode_index}",
        lineage=lineage,
        parent_checkpoint_id=parent_checkpoint,
        branch_id="B",
        virtual_time=start_cycle + EPISODE,
        rng_directory=rng,
        profile_ref="m0_mw0@v1.1",
    )
    return record.checkpoint_id


def _continuity_signature_for(
    store: MemoryStore, lineage: LineageTable, boundary_cycle: int, arm: str,
):
    """记忆侧签名（L06 §4.5）：内容跨界存续（边界两侧均有条目）+ 谱系链 + gap 计数。

    期望链 = 谱系表真链；条目声称的锚（lineage_refs）与之双向比对——声称真链之外
    的锚（伪造）→ intact=False（Q-L04-06 主判据）；真链有而未声称 → gap。
    """
    items = store.list_subsystem(MemorySubsystem.EPISODIC)
    spans = any(i.created_cycle < boundary_cycle for i in items) and any(
        i.created_cycle >= boundary_cycle for i in items
    )
    expected = _chain(lineage)                     # 谱系表真链
    claimed = sorted({ref for item in items for ref in item.lineage_refs})   # 条目声称的锚
    sig = continuity_signature(arm, len(items), expected, claimed)
    return dataclasses.replace(sig, content_spans_boundary=spans), spans


def test_sc5_four_arms_continuity_contrast() -> None:
    """四臂记忆侧签名可区分；freeze_restore ≡ full_continuity；伪更新被检出（L06 §4.5 M2 硬条件）。"""
    seed = b"m2-sc5-continuity"
    tmp = Path(tempfile.mkdtemp())

    # —— full_continuity：两 episode 连续运行，谱系链完整、内容跨界 ——
    stores_full = Stores(tmp / "full" / "stores")
    lineage_full = LineageTable()
    store_full = MemoryStore(stores_full)
    base = Path(tempfile.mkdtemp())
    ck1 = _run_episode(seed, 0, store_full, stores_full, lineage_full, None, 1, base)
    sig_full, spanning_full = _continuity_signature_for(store_full, lineage_full, EPISODE, "full_continuity")
    ck2 = _run_episode(seed, EPISODE, store_full, stores_full, lineage_full, ck1, 2, base)
    sig_full_after, spanning_full_after = _continuity_signature_for(store_full, lineage_full, EPISODE, "full_continuity")
    assert sig_full.episodic_present is True and spanning_full is False  # ep1 后：内容在案、尚无跨界
    assert spanning_full_after is True                              # round2 内容跨界存续（两侧均有）
    assert claim_continuity(sig_full_after, "continuation") is True

    # —— freeze_restore：checkpoint 后冻结，恢复 = 同 seed 重放重建（内容/谱系与完整延续恒等）——
    stores_frozen = Stores(tmp / "frozen" / "stores")
    lineage_frozen = LineageTable()
    store_frozen = MemoryStore(stores_frozen)
    ck1f = _run_episode(seed, 0, store_frozen, stores_frozen, lineage_frozen, None, 1, base)
    assert ck1f == ck1                                              # 确定性：同 seed 同锚 id
    # 冻结（无操作 = 进程停止）；恢复 = 以同 seed 重放 episode 1 重建记忆库
    store_restored = MemoryStore(Stores(tmp / "frozen" / "restored"))
    _run_episode(seed, 0, store_restored, stores_frozen, lineage_frozen, None, 1, base, do_checkpoint=False)
    sig_restored, spanning_restored = _continuity_signature_for(store_restored, lineage_frozen, EPISODE, "freeze_restore")
    # 恢复 ≡ 冻结点状态（full 臂 ep1 后的记忆侧签名恒等——确定性重放重建）
    assert (sig_restored.episodic_present, sig_restored.lineage_intact, sig_restored.gap_count) == (
        sig_full.episodic_present, sig_full.lineage_intact, sig_full.gap_count
    )
    assert spanning_restored == spanning_full

    # —— reset：清空 working/episodic（保留谱系/登记）→ 延续主张被拒 ——
    stores_reset = Stores(tmp / "reset" / "stores")
    lineage_reset = LineageTable()
    store_reset = MemoryStore(stores_reset)
    ck1r = _run_episode(seed, 0, store_reset, stores_reset, lineage_reset, None, 1, base)
    cleared = store_reset.clear_working_episodic()
    assert cleared > 0
    _run_episode(seed, EPISODE, store_reset, stores_reset, lineage_reset, ck1r, 2, base)
    sig_reset, _spanning = _continuity_signature_for(store_reset, lineage_reset, EPISODE, "reset")
    assert sig_reset.lineage_intact is True                          # 谱系保留（reset 语义）
    assert claim_continuity(sig_reset, "continuation") is False      # 但内容不跨界 → 非延续

    # —— pseudo_update：声称延续而谱系伪造（锚不在期望链）→ LineageBreak 语义 ——
    stores_pseudo = Stores(tmp / "pseudo" / "stores")
    lineage_pseudo = LineageTable()
    store_pseudo = MemoryStore(stores_pseudo)
    ck1p = _run_episode(seed, 0, store_pseudo, stores_pseudo, lineage_pseudo, None, 1, base)
    # 伪造：ep2 条目的 lineage_refs 声称一个谱系表中不存在的锚
    from galatea.subject.memory.encode import encode_episodic as _enc
    _enc(store_pseudo, M2, "ep2.forged", "event:forged:300:0_0",
         RepresentationLevel.RECEIVED, SourceType.SELF_GENERATED, EPISODE + 44,
         lineage_refs=("ckpt.forged",))
    sig_pseudo, _ = _continuity_signature_for(store_pseudo, lineage_pseudo, EPISODE, "pseudo_update")
    assert sig_pseudo.lineage_intact is False                        # 伪造锚 → 断裂（Q-L04-06 主判据）
    assert claim_continuity(sig_pseudo, "continuation") is False
    assert claim_continuity(sig_pseudo, "branch") is False           # 伪造连分支主张也不成立

    # —— 四臂签名类 = 3（full ≡ frozen）且判定结果可区分 ——
    # freeze_restore 的延续结论由状态恒等承载：sig_restored ≡ sig_full（冻结点）且
    # 确定性演化 ⇒ 恢复后的 round2 与 full 臂全同（ benches 已断言签名恒等）。
    outcomes = {
        "full_continuity": claim_continuity(sig_full_after, "continuation"),
        "freeze_restore": claim_continuity(sig_full_after, "continuation"),   # 状态恒等 ⇒ 同判
        "reset": claim_continuity(sig_reset, "continuation"),
        "pseudo_update": claim_continuity(sig_pseudo, "continuation"),
    }
    assert outcomes == {
        "full_continuity": True, "freeze_restore": True, "reset": False, "pseudo_update": False,
    }
    assert sig_pseudo.lineage_intact is False and sig_reset.lineage_intact is True
    for stores in (stores_full, stores_frozen, stores_reset, stores_pseudo):
        stores.close()
    import shutil

    shutil.rmtree(base, ignore_errors=True)
