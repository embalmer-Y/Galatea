"""三库分离 + 单写者机械校验（L00 §3/§7；Q-T05）。含运行时加固测试（ADR-G-0003 R9②）。"""
import re
from pathlib import Path

import pytest

from galatea.kernel.state import LineageTable, OwnershipViolation, StoreName, Stores

STATE_SRC = (Path(__file__).resolve().parents[1] / "state.py").read_text(encoding="utf-8")


def test_three_stores_distinct_files_with_wal(tmp_path: Path) -> None:
    stores = Stores(tmp_path)
    modes = stores.journal_modes()
    assert set(modes.values()) == {"wal"}
    for store in StoreName:
        assert (tmp_path / f"{store.value}.db").exists()


def test_single_writer_enforced(tmp_path: Path) -> None:
    stores = Stores(tmp_path)
    writer = stores.open_writer(StoreName.SUBJECT_STATE, "kernel_events", "kernel")  # 合法
    with writer.transaction():
        writer.execute("INSERT INTO kernel_events (cycle, seq, digest) VALUES (1, 1, 'd')")
    with pytest.raises(OwnershipViolation):
        stores.open_writer(StoreName.SUBJECT_STATE, "kernel_events", "orchestrator")
    with pytest.raises(OwnershipViolation):
        stores.open_writer(StoreName.SUBJECT_STATE, "no_such_table", "kernel")
    with pytest.raises(OwnershipViolation):
        stores.open_writer(StoreName.SUBJECT_MEMORY, "episodes", "orchestrator")  # L06 专属


def test_writer_handle_is_table_scoped(tmp_path: Path) -> None:
    """写句柄仅限绑定表（R9②：跨表语句即拒）。"""
    stores = Stores(tmp_path)
    writer = stores.open_writer(StoreName.SUBJECT_STATE, "kernel_events", "kernel")
    with pytest.raises(OwnershipViolation):
        writer.execute("INSERT INTO kernel_unknowns (entry_id, reason, digest) VALUES (1, 'X', 'd')")
    with pytest.raises(OwnershipViolation):
        writer.execute("DELETE FROM kernel_checkpoints")


def test_read_surface_is_select_only(tmp_path: Path) -> None:
    """读面仅 SELECT（R9②：读 API 无写通道）。"""
    stores = Stores(tmp_path)
    with pytest.raises(OwnershipViolation):
        stores.read(StoreName.SUBJECT_STATE, "INSERT INTO kernel_events (cycle, seq, digest) VALUES (1, 1, 'd')")
    with pytest.raises(OwnershipViolation):
        stores.read(StoreName.SUBJECT_STATE, "UPDATE kernel_events SET digest = 'x'")


def test_store_isolation(tmp_path: Path) -> None:
    stores = Stores(tmp_path)
    writer = stores.open_writer(StoreName.SUBJECT_STATE, "kernel_events", "kernel")
    with writer.transaction():
        writer.execute("INSERT INTO kernel_events (cycle, seq, digest) VALUES (1, 1, 'd')")
    assert stores.read(StoreName.SUBJECT_STATE, "SELECT count(*) FROM kernel_events") == [(1,)]
    assert stores.read(StoreName.SUBJECT_MEMORY, "SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'") == [(0,)]


def test_no_cross_store_attach_in_source() -> None:
    """连接层禁止跨库事务的机械面：源码无任何 ATTACH 形态（R9⑥：含 ATTACH .. AS ..）。"""
    assert re.search(r"\bATTACH\b", STATE_SRC, re.IGNORECASE) is None


def test_kernel_cannot_create_memory_tables(tmp_path: Path) -> None:
    stores = Stores(tmp_path)
    tables = {
        row[0]
        for row in stores.read(
            StoreName.SUBJECT_MEMORY,
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'",
        )
    }
    assert tables == set()


def test_lineage_dag_still_validated(tmp_path: Path) -> None:
    """加固后 checkpoint 谱系行为不变（回归）。"""
    from galatea.kernel.rng import RngDirectory, reference_block_blake2s
    from galatea.kernel.state import CheckpointFailure, CheckpointRecord

    stores = Stores(tmp_path)
    lineage = LineageTable()
    record = stores.checkpoint(
        checkpoint_id="cp-1", lineage=lineage, parent_checkpoint_id=None, branch_id="B",
        virtual_time=1, profile_ref="p",
        rng_directory=RngDirectory(b"s", reference_block_blake2s),
    )
    assert record.checkpoint_id == "cp-1"
    orphan = CheckpointRecord(
        checkpoint_id="cp-2", parent_checkpoint_id="ghost", branch_id="B", virtual_time=2,
        digest_state="s", digest_memory="m", digest_registry_view="r",
        rng_snapshot=(), profile_ref="p", artifact_refs=(),
    )
    with pytest.raises(CheckpointFailure):
        lineage.add(orphan)
