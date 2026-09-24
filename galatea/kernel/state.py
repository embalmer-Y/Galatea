"""三库分离 + 单写者 + checkpoint 谱系（L00 §3；Q-T05 CONFIRMED：SQLite 三库、WAL）。

纪律：三个物理库各自独立连接；连接层无跨库事务（无跨库附接、无多库 commit API）；
每表唯一写者（OWNERSHIP 机械校验，越权 = OwnershipViolation，S1 级）；
subject_memory 的写者位预留给 L06（memory），orchestrator 及其余模块被拒。
"""
import enum
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from galatea.kernel.digest import content_digest
from galatea.kernel.rng import RngDirectory


class StoreName(enum.StrEnum):
    SUBJECT_STATE = "subject_state"
    SUBJECT_MEMORY = "subject_memory"
    REGISTRY = "registry"


class OwnershipViolation(PermissionError):
    """非唯一写者企图写表（L00 §3：未授权写入 = S1 缺陷）。"""


class CheckpointFailure(RuntimeError):
    """checkpoint 写失败/谱系违规（L00 §6.2：停止 claim-relevant 运行）。"""


@dataclass(frozen=True, slots=True)
class CheckpointRecord:
    """谱系 DAG 节点（L00 §3）。clone ≠ identity（D-12）由 branch 谱系表达。"""

    checkpoint_id: str
    parent_checkpoint_id: str | None
    branch_id: str
    virtual_time: int
    digest_state: str
    digest_memory: str
    digest_registry_view: str
    rng_snapshot: tuple[tuple[str, str, str, str, int, int], ...]
    profile_ref: str
    artifact_refs: tuple[str, ...]


class WriterHandle:
    """单表唯一写者句柄：事务作用域限于本库；execute 仅限本表 SQL（运行时加固，ADR-G-0003 R9②）。"""

    def __init__(self, connection: sqlite3.Connection, store: StoreName, table: str, writer: str) -> None:
        self._connection = connection
        self.store = store
        self.table = table
        self.writer = writer

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        if self.table not in sql:
            raise OwnershipViolation(
                f"writer bound to table {self.table!r} cannot execute statements touching other tables"
            )
        self._connection.execute(sql, params)

    @contextmanager
    def transaction(self) -> "Generator[WriterHandle, None, None]":
        try:
            yield self
            self._connection.commit()
        except BaseException:
            self._connection.rollback()
            raise


class LineageTable:
    """checkpoint 谱系：DAG 校验（父存在、无自引、无环、无重复 id）。"""

    def __init__(self) -> None:
        self._records: dict[str, CheckpointRecord] = {}

    def add(self, record: CheckpointRecord) -> None:
        if record.checkpoint_id in self._records:
            raise CheckpointFailure(f"duplicate checkpoint_id: {record.checkpoint_id}")
        parent = record.parent_checkpoint_id
        if parent is not None:
            if parent == record.checkpoint_id:
                raise CheckpointFailure("self-parent checkpoint")
            if parent not in self._records:
                raise CheckpointFailure(f"missing parent: {parent}")
            seen: set[str] = set()
            cursor: str | None = parent
            while cursor is not None:
                if cursor == record.checkpoint_id or cursor in seen:
                    raise CheckpointFailure("lineage cycle detected")
                seen.add(cursor)
                cursor = self._records[cursor].parent_checkpoint_id
        self._records[record.checkpoint_id] = record

    def get(self, checkpoint_id: str) -> CheckpointRecord:
        try:
            return self._records[checkpoint_id]
        except KeyError:
            raise CheckpointFailure(f"unknown checkpoint: {checkpoint_id}") from None

    def all(self) -> tuple[CheckpointRecord, ...]:
        return tuple(self._records[cid] for cid in sorted(self._records))


# 唯一写者登记（frozen profile 的机械对应物；新表须先在此登记，open_writer 才放行）
_OWNERSHIP: dict[tuple[StoreName, str], str] = {
    (StoreName.SUBJECT_STATE, "kernel_events"): "kernel",
    (StoreName.SUBJECT_STATE, "kernel_checkpoints"): "kernel",
    (StoreName.SUBJECT_STATE, "kernel_unknowns"): "kernel",
    (StoreName.SUBJECT_MEMORY, "episodes"): "memory",  # L06（未来）；其余一律拒
    (StoreName.REGISTRY, "artifacts"): "registry_builder",
    (StoreName.REGISTRY, "artifact_parents"): "registry_builder",
    (StoreName.REGISTRY, "registry_events"): "registry_builder",
}

_KERNEL_TABLE_DDL = {
    StoreName.SUBJECT_STATE: (
        "CREATE TABLE IF NOT EXISTS kernel_events (cycle INTEGER, seq INTEGER, digest TEXT, PRIMARY KEY (cycle, seq))",
        "CREATE TABLE IF NOT EXISTS kernel_checkpoints (checkpoint_id TEXT PRIMARY KEY, record_digest TEXT)",
        "CREATE TABLE IF NOT EXISTS kernel_unknowns (entry_id INTEGER PRIMARY KEY, reason TEXT, digest TEXT)",
    ),
    StoreName.SUBJECT_MEMORY: (),  # L06 所有；kernel 不建表
    StoreName.REGISTRY: (
        "CREATE TABLE IF NOT EXISTS artifacts (digest TEXT PRIMARY KEY, kind TEXT, created_cycle INTEGER, size INTEGER, manifest_digest TEXT)",
        "CREATE TABLE IF NOT EXISTS artifact_parents (digest TEXT, parent_digest TEXT, PRIMARY KEY (digest, parent_digest))",
        "CREATE TABLE IF NOT EXISTS registry_events (seq INTEGER PRIMARY KEY, op TEXT, digest TEXT, cycle INTEGER)",
    ),
}


class Stores:
    """三库连接协议：三连接物理分离；无跨库事务；单写者机械校验。"""

    def __init__(self, root: Path, wal: bool = True) -> None:
        self._root = root
        self._connections: dict[StoreName, sqlite3.Connection] = {}
        for store in StoreName:
            path = root / f"{store.value}.db"
            root.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(path))
            if wal and path.name != ":memory:":
                conn.execute("PRAGMA journal_mode=WAL")
            for ddl in _KERNEL_TABLE_DDL[store]:
                conn.execute(ddl)
            conn.commit()
            self._connections[store] = conn

    def _select_only(self, sql: str) -> None:
        """读面运行时加固（ADR-G-0003 R9②）：读 API 仅接受 SELECT，杜绝裸连接写。"""
        if not sql.lstrip().upper().startswith("SELECT"):
            raise OwnershipViolation("read surface is SELECT-only（写必须经 open_writer 单写者句柄）")

    def connection(self, store: StoreName) -> sqlite3.Connection:
        """只读用途的原始连接（写必须走 open_writer）。"""
        return self._connections[store]

    def open_writer(self, store: StoreName, table: str, writer_module: str) -> WriterHandle:
        owner = _OWNERSHIP.get((store, table))
        if owner is None:
            raise OwnershipViolation(f"unregistered table: {store.value}.{table}")
        if owner != writer_module:
            raise OwnershipViolation(
                f"{writer_module!r} is not the single writer of {store.value}.{table} (owner={owner!r})"
            )
        return WriterHandle(self._connections[store], store, table, writer_module)

    def read(self, store: StoreName, sql: str, params: tuple[object, ...] = ()) -> list[tuple[object, ...]]:
        self._select_only(sql)
        return list(self._connections[store].execute(sql, params).fetchall())

    def journal_modes(self) -> dict[StoreName, str]:
        out: dict[StoreName, str] = {}
        for store, conn in self._connections.items():
            row = conn.execute("PRAGMA journal_mode").fetchone()
            out[store] = str(row[0]) if row is not None else "unknown"
        return out

    def checkpoint(
        self,
        *,
        checkpoint_id: str,
        lineage: LineageTable,
        parent_checkpoint_id: str | None,
        branch_id: str,
        virtual_time: int,
        rng_directory: RngDirectory,
        profile_ref: str,
        artifact_refs: tuple[str, ...] = (),
        registry_view_digest: str = "",
    ) -> CheckpointRecord:
        """内核所有：原子构造谱系节点（校验失败即抛，不写半截）。"""
        state_rows = self.read(StoreName.SUBJECT_STATE, "SELECT cycle, seq, digest FROM kernel_events ORDER BY cycle, seq")
        memory_rows = self.read(StoreName.SUBJECT_MEMORY, "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        record = CheckpointRecord(
            checkpoint_id=checkpoint_id,
            parent_checkpoint_id=parent_checkpoint_id,
            branch_id=branch_id,
            virtual_time=virtual_time,
            digest_state=content_digest([list(r) for r in state_rows]),
            digest_memory=content_digest([list(r) for r in memory_rows]),
            digest_registry_view=registry_view_digest,
            rng_snapshot=rng_directory.snapshot(),
            profile_ref=profile_ref,
            artifact_refs=artifact_refs,
        )
        lineage.add(record)
        writer = self.open_writer(StoreName.SUBJECT_STATE, "kernel_checkpoints", "kernel")
        with writer.transaction():
            writer.execute(
                "INSERT OR REPLACE INTO kernel_checkpoints (checkpoint_id, record_digest) VALUES (?, ?)",
                (record.checkpoint_id, content_digest(record)),
            )
        return record
