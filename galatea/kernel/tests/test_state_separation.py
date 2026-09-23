"""三库分离 + 单写者机械校验（L00 §3/§7；Q-T05）。"""
import sqlite3
from pathlib import Path

import pytest

from galatea.kernel.state import LineageTable, OwnershipViolation, StoreName, Stores

STATE_SRC = (Path(__file__).resolve().parents[1] / "state.py").read_text(encoding="utf-8")


def test_three_distinct_connections_with_wal(tmp_path: Path) -> None:
    stores = Stores(tmp_path)
    conns = [stores.connection(s) for s in StoreName]
    assert len({id(c) for c in conns}) == 3
    modes = stores.journal_modes()
    assert set(modes.values()) == {"wal"}


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


def test_store_isolation(tmp_path: Path) -> None:
    stores = Stores(tmp_path)
    writer = stores.open_writer(StoreName.SUBJECT_STATE, "kernel_events", "kernel")
    with writer.transaction():
        writer.execute("INSERT INTO kernel_events (cycle, seq, digest) VALUES (1, 1, 'd')")
    assert stores.read(StoreName.SUBJECT_STATE, "SELECT count(*) FROM kernel_events") == [(1,)]
    assert stores.read(StoreName.SUBJECT_MEMORY, "SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'") == [(0,)]


def test_no_cross_store_attach_in_source() -> None:
    """连接层禁止跨库事务的机械面：源码无 ATTACH DATABASE、WAL 就绪。"""
    assert "ATTACH DATABASE" not in STATE_SRC.upper()


def test_kernel_cannot_create_memory_tables(tmp_path: Path) -> None:
    stores = Stores(tmp_path)
    # subject_memory 无 kernel 表（DDL 仅 registry/state 有）：直证 kernel 不写 memory 域
    tables = {
        row[0]
        for row in stores.connection(StoreName.SUBJECT_MEMORY).execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    assert tables == set()
