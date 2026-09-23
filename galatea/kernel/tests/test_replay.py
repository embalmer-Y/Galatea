"""确定性重放（ReplayTest，L00 §7：同 (profile, seed, digests) ⇒ bit-exact）+ F0 路由合同。"""
from dataclasses import dataclass
from pathlib import Path

import pytest

from galatea.kernel.clock import CycleClock
from galatea.kernel.packet import (
    AccessScope,
    ArtifactRef,
    CognitivePacket,
    Provenance,
    RepresentationLevel,
    UlidFactory,
    make_packet,
)
from galatea.kernel.registry import Registry
from galatea.kernel.rng import CounterStream, RngDirectory, reference_block_blake2s
from galatea.kernel.scheduler import DispatchContext, Registration, Scheduler
from galatea.kernel.state import LineageTable, Stores
from galatea.kernel.unknown import Unknown, UnknownReason

Out = tuple[CognitivePacket, ...]


@dataclass
class WorldResult:
    id_log: list[tuple[int, str, tuple[str, ...]]]
    registry_digest: str
    checkpoints: list[str]
    out_digests: list[tuple[str, ...]]


def run_world(seed: bytes, tmp: Path, payload_byte: int) -> WorldResult:
    """payload_byte=-1 → payload 内容来自流；≥0 → 恒定字节（供 leakage 变体）。"""
    stores = Stores(tmp / "stores")
    clock = CycleClock()
    rng_dir = RngDirectory(seed, reference_block_blake2s)
    registry = Registry(tmp / "registry", stores, clock)
    lineage = LineageTable()
    id_log: list[tuple[int, str, tuple[str, ...]]] = []

    def emit(
        ctx: DispatchContext, rng: CounterStream, content_type: str, level: RepresentationLevel,
        confidence: object, parents: tuple[str, ...], nbytes: int,
    ) -> CognitivePacket:
        raw = rng.next_bytes(nbytes) if payload_byte < 0 else bytes([payload_byte]) * nbytes
        ref = registry.put(raw, "payload")
        ulid = UlidFactory(rng_dir.stream(ctx.branch_id, ctx.module_id, "ulid"), lambda: ctx.virtual_time)
        return make_packet(
            event_id=ulid.new(),
            subject_candidate_id=ctx.subject_candidate_id,
            run_id=ctx.run_id,
            branch_id=ctx.branch_id,
            activity_window_id="W",
            cycle_id=ctx.due_cycle,
            virtual_time=ctx.virtual_time,
            source_module=ctx.module_id,
            content_type=content_type,
            representation_level=level,
            schema_version="v1",
            payload_ref=ArtifactRef(digest=ref.digest, kind="payload"),
            confidence=confidence,  # type: ignore[arg-type]
            provenance=Provenance(source_events=parents),
            causal_parent_ids=parents,
            access_scope=AccessScope.PUBLIC_BROADCAST,
        )

    def sense_handler(ctx: DispatchContext) -> Out:
        rng = rng_dir.stream(ctx.branch_id, "sense", "emit")
        packet = emit(ctx, rng, "test.signal.v1", RepresentationLevel.RECEIVED, rng.next_float01(), (), 8)
        id_log.append((ctx.due_cycle, "sense", (packet.event_id,)))
        return (packet,)

    seen: list[str] = []

    def workspace_handler(ctx: DispatchContext) -> Out:
        seen.extend(p.event_id for p in ctx.packets)
        parents = tuple(p.event_id for p in ctx.packets[:1])
        if not parents:
            return ()
        rng = rng_dir.stream(ctx.branch_id, "workspace", "emit")
        packet = emit(ctx, rng, "test.perceived.v1", RepresentationLevel.PERCEIVED, 0.5, parents, 4)
        id_log.append((ctx.due_cycle, "workspace", (packet.event_id,)))
        return (packet,)

    def act_handler(ctx: DispatchContext) -> Out:
        parents = tuple(seen[-3:])
        rng = rng_dir.stream(ctx.branch_id, "act", "emit")
        unknown = Unknown(
            reason=UnknownReason.ATTRIBUTION_UNRESOLVED, evidence_refs=parents,
            detail=None, detected_by="act", virtual_time=ctx.virtual_time,
        )
        packet = emit(ctx, rng, "test.intention.v1", RepresentationLevel.PREDICTED, unknown, parents, 6)
        id_log.append((ctx.due_cycle, "act", (packet.event_id,)))
        return (packet,)

    sched = Scheduler(clock, rng_dir, run_id="R", branch_id="B", subject_candidate_id="S")
    sched.register(Registration("sense", 1, 1, sense_handler))
    sched.register(Registration("workspace", 3, 2, workspace_handler))
    sched.register(Registration("act", 4, 4, act_handler))

    checkpoints: list[str] = []
    out_digests: list[tuple[str, ...]] = []
    for cycle in range(16, 65, 16):
        commits = sched.run_until(cycle)
        out_digests = [c.out_digests for c in commits]
        record = stores.checkpoint(
            checkpoint_id=f"cp-{cycle}",
            lineage=lineage,
            parent_checkpoint_id=checkpoints[-1] if checkpoints else None,
            branch_id="B",
            virtual_time=cycle,
            rng_directory=rng_dir,
            profile_ref="f0_l00@v1",
            registry_view_digest=registry.index_digest(),
        )
        checkpoints.append(record.checkpoint_id)
    return WorldResult(id_log=id_log, registry_digest=registry.index_digest(), checkpoints=checkpoints, out_digests=out_digests)


def test_same_seed_bit_exact(tmp_path: Path) -> None:
    r1 = run_world(b"seed-A", tmp_path / "a1", payload_byte=-1)
    r2 = run_world(b"seed-A", tmp_path / "a2", payload_byte=-1)
    assert r1.id_log == r2.id_log
    assert r1.registry_digest == r2.registry_digest
    assert r1.checkpoints == r2.checkpoints
    assert r1.out_digests == r2.out_digests


def test_different_seed_diverges(tmp_path: Path) -> None:
    r1 = run_world(b"seed-A", tmp_path / "a", payload_byte=-1)
    r3 = run_world(b"seed-B", tmp_path / "b", payload_byte=-1)
    assert r1.out_digests != r3.out_digests
    assert r1.registry_digest != r3.registry_digest


def test_targeted_routing(tmp_path: Path) -> None:
    """F0 路由合同：显式目标只达目标模块。"""
    received = {"dst": 0, "other": 0}
    clock = CycleClock()
    rng_dir = RngDirectory(b"seed", reference_block_blake2s)
    sched = Scheduler(clock, rng_dir, run_id="R", branch_id="B", subject_candidate_id="S")

    def src_handler(ctx: DispatchContext) -> Out:
        ulid = UlidFactory(rng_dir.stream("B", "src", "ulid"), lambda: ctx.virtual_time)
        packet = make_packet(
            event_id=ulid.new(), subject_candidate_id="S", run_id="R", branch_id="B",
            activity_window_id="W", cycle_id=ctx.due_cycle, virtual_time=ctx.virtual_time,
            source_module="src", content_type="test.t.v1",
            representation_level=RepresentationLevel.PREDICTED, schema_version="v1",
            payload_ref=ArtifactRef(digest="0" * 64, kind="payload"), confidence=0.5,
            causal_parent_ids=(), access_scope=AccessScope.MODULE_LOCAL,
        )
        sched.submit(packet, target_module="dst")
        return ()

    def note(ctx: DispatchContext) -> Out:
        received[ctx.module_id] += len(ctx.packets)
        return ()

    sched.register(Registration("src", 1, 1, src_handler))
    sched.register(Registration("dst", 2, 1, note))
    sched.register(Registration("other", 2, 1, note))
    sched.run_until(1)  # cycle 1：src(t1) 先于 dst(t2) 派发，定向包当拍到达
    assert received == {"dst": 1, "other": 0}


def test_targetless_requires_broadcast(tmp_path: Path) -> None:
    clock = CycleClock()
    rng_dir = RngDirectory(b"seed", reference_block_blake2s)
    sched = Scheduler(clock, rng_dir, run_id="R", branch_id="B", subject_candidate_id="S")
    sched.register(Registration("m", 1, 1, lambda ctx: ()))
    packet = make_packet(
        event_id="E", subject_candidate_id="S", run_id="R", branch_id="B", activity_window_id="W",
        cycle_id=1, virtual_time=1, source_module="m", content_type="t.v1",
        representation_level=RepresentationLevel.PREDICTED, schema_version="v1",
        payload_ref=ArtifactRef(digest="0" * 64, kind="payload"), confidence=0.5,
        access_scope=AccessScope.MODULE_LOCAL,
    )
    with pytest.raises(ValueError):
        sched.submit(packet, target_module=None)
