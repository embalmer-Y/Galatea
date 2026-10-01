"""I1 重放复算（L13 §4.8/§10 recorder/replay.py；Q-T06 DuckDB 只读复算）。

I1 = 同环境独立重算：recorder 数据（registry 内容寻址 Parquet 分区）→ 指标复算 →
digest bit-exact。读路径：registry.get（blob/manifest 双重校验）→ 临时文件 →
DuckDB 内存连接 read_parquet（对数据文件只读）→ 行集 → 复算 digest 比对。
I2/I3 归 E1/H1（不同实现/新环境独立）；本模块承载 R0 硬前置的 I1。
"""
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import duckdb

from galatea.kernel.digest import content_digest
from galatea.kernel.packet import ArtifactRef
from galatea.kernel.registry import Registry

__all__ = ["RecomputeReport", "read_partition", "recompute_i1"]


@dataclass(frozen=True, slots=True)
class RecomputeReport:
    """复算报告（L13 §2.2 evd.recompute_report）。"""

    mode: str                    # "I1" | "I2" | "I3"
    inputs_digest: str           # 复算输入（分区 blob digest 集）的身份
    outputs_digest: str          # 复算产出的 digest
    match: bool
    diffs: tuple[str, ...]


def read_partition(registry: Registry, ref: ArtifactRef) -> list[dict[str, Any]]:
    """只读取回分区行：registry 完整性校验 → DuckDB read_parquet → 行 dict 列表。"""
    entry = registry.get(ref)   # blob digest 不符 = RegistryCollision（S0）；缺件 = ArtifactMissing
    fd, path = tempfile.mkstemp(suffix=".parquet")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(entry.blob)
        con = duckdb.connect()   # 内存连接：不建库文件，对 parquet 只读
        try:
            cursor = con.execute("SELECT * FROM read_parquet(?)", [str(path)])
            columns = [str(d[0]) for d in cursor.description]
            rows = cursor.fetchall()
        finally:
            con.close()
    finally:
        os.unlink(path)
    return [dict(zip(columns, row)) for row in rows]


def recompute_i1(
    registry: Registry,
    refs: dict[str, ArtifactRef],
    recompute: Callable[[dict[str, list[dict[str, Any]]]], str],
    expected_outputs_digest: str,
) -> RecomputeReport:
    """I1 驱动：读全部分区 → 独立复算 → outputs digest 与期望 bit-exact 比对。

    recompute 只消费 recorder 读出的行（禁携带运行时内存对象——独立重算的边界）。
    """
    partition_names = sorted(name for name in refs if name != "run_manifest")
    partitions: dict[str, list[dict[str, Any]]] = {
        name: read_partition(registry, refs[name]) for name in partition_names
    }
    inputs_digest = content_digest({name: refs[name].digest for name in partition_names})
    outputs_digest = recompute(partitions)
    match = outputs_digest == expected_outputs_digest
    diffs: tuple[str, ...] = ()
    if not match:
        diffs = (f"outputs digest mismatch: recomputed={outputs_digest} expected={expected_outputs_digest}",)
    return RecomputeReport(
        mode="I1", inputs_digest=inputs_digest, outputs_digest=outputs_digest, match=match, diffs=diffs
    )
