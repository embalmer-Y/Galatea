"""checkpoint 谱系 DAG 与 RNG 快照恢复（L00 §3/§4.3/§7）。"""
from pathlib import Path

import pytest

from galatea.kernel.rng import CounterStream, RngDirectory, reference_block_blake2s
from galatea.kernel.state import CheckpointFailure, CheckpointRecord, LineageTable, StoreName, Stores


def _record(cid: str, parent: str | None, branch: str = "B"):
    return CheckpointRecord(
        checkpoint_id=cid,
        parent_checkpoint_id=parent,
        branch_id=branch,
        virtual_time=len(cid),
        digest_state=f"state-{cid}",
        digest_memory=f"mem-{cid}",
        digest_registry_view=f"reg-{cid}",
        rng_snapshot=(("B", "m", "s", "aa", 1, 0),),
        profile_ref="f0_l00@v1",
        artifact_refs=(),
    )


def test_lineage_accepts_chain_rejects_missing_self_duplicate_and_cycle() -> None:
    lineage = LineageTable()
    root = _record("cp-1", None)
    child = _record("cp-2", "cp-1")
    lineage.add(root)
    lineage.add(child)
    assert [r.checkpoint_id for r in lineage.all()] == ["cp-1", "cp-2"]
    with pytest.raises(CheckpointFailure):
        lineage.add(_record("cp-3", "ghost"))  # 父缺失
    with pytest.raises(CheckpointFailure):
        lineage.add(_record("cp-4", "cp-4"))  # 自引
    with pytest.raises(CheckpointFailure):
        lineage.add(_record("cp-1", None))  # 重复 id
    # 环不可能经 add 产生（父必须先存在，祖先链在创建时即固定）；自引已被拒。
    # 三级链为合法路径的确认：
    lineage.add(_record("cp-3", "cp-2"))
    assert [r.checkpoint_id for r in lineage.all()] == ["cp-1", "cp-2", "cp-3"]


def test_stores_checkpoint_writes_and_digests_move(tmp_path: Path) -> None:
    stores = Stores(tmp_path)
    lineage = LineageTable()
    rng = RngDirectory(b"seed", reference_block_blake2s)
    cp1 = stores.checkpoint(
        checkpoint_id="cp-16", lineage=lineage, parent_checkpoint_id=None, branch_id="B",
        virtual_time=16, rng_directory=rng, profile_ref="f0_l00@v1",
    )
    # 状态推进后 digest 变化：
    w = stores.open_writer(StoreName.SUBJECT_STATE, "kernel_events", "kernel")
    with w.transaction():
        w.execute("INSERT INTO kernel_events (cycle, seq, digest) VALUES (17, 1, 'd')")
    cp2 = stores.checkpoint(
        checkpoint_id="cp-32", lineage=lineage, parent_checkpoint_id="cp-16", branch_id="B",
        virtual_time=32, rng_directory=rng, profile_ref="f0_l00@v1",
    )
    assert cp2.parent_checkpoint_id == "cp-16"
    assert cp2.digest_state != cp1.digest_state
    rows = stores.read(StoreName.SUBJECT_STATE, "SELECT checkpoint_id FROM kernel_checkpoints ORDER BY checkpoint_id")
    assert rows == [("cp-16",), ("cp-32",)]


def test_rng_snapshot_roundtrip(tmp_path: Path) -> None:
    stores = Stores(tmp_path)
    rng = RngDirectory(b"seed", reference_block_blake2s)
    stream = rng.stream("B", "m", "s")
    for _ in range(3):
        stream.next_uint64()
    cp = stores.checkpoint(
        checkpoint_id="cp", lineage=LineageTable(), parent_checkpoint_id=None, branch_id="B",
        virtual_time=1, rng_directory=rng, profile_ref="p",
    )
    (branch, module, name, key_hex, counter, offset) = cp.rng_snapshot[0]
    assert (branch, module, name) == ("B", "m", "s")
    restored = CounterStream.restore(key_hex, counter, offset, reference_block_blake2s)
    assert restored.next_uint64() == stream.next_uint64()
