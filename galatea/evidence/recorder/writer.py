"""EvidenceWriter：四类分区 Parquet 落盘（L13 §4.2/§10 recorder/writer.py；Q-T06）。

纪律：
- Parquet 唯一证据承载；Polars 仅写侧（Q-T06）；
- append-only / content-addressed：分区 blob 经 kernel Registry 落盘（L00 §4.5
  registry/<sha256[:2]>/<sha256>/），落盘即记 digest；同内容重写 = 幂等（同 digest），
  内容分叉 = RegistryCollision（S0）；关闭后拒绝再写（修改 = 新记录 + revision 引用，
  本模块以"关闭后不可变"承载——revision 链归 C0+ 流式范围）；
- 嵌套值 JSON 字符串化（Parquet 列标量）；行 schema 必须逐行一致（fail closed）；
- 四分区：manifest / trace / metrics / evidence；manifest 行由 RunManifest 提供
  （墙钟仅此，Q-T12）。
"""
import io
import json
from typing import Any

import polars as pl

from galatea.kernel.packet import ArtifactRef
from galatea.kernel.registry import Registry
from galatea.kernel.digest import content_digest
from galatea.evidence.recorder.manifest import RunManifest

__all__ = ["EvidenceWriter", "AppendOnlyViolation", "PARTITIONS"]

PARTITIONS: tuple[str, ...] = ("manifest", "trace", "metrics", "evidence")


class AppendOnlyViolation(RuntimeError):
    """recorder 不可变性违规（L13 §6：S0——证据记录被原地修改/关闭后写入）。"""


class EvidenceWriter:
    """claim-relevant 运行的证据写入器（四分区；blob 入 content-addressed registry）。"""

    def __init__(self, registry: Registry) -> None:
        self._registry = registry
        self._rows: dict[str, list[dict[str, Any]]] = {name: [] for name in PARTITIONS}
        self._refs: dict[str, ArtifactRef] = {}
        self._closed = False

    def add(self, partition: str, row: dict[str, Any]) -> None:
        if self._closed:
            raise AppendOnlyViolation("writer is closed: post-close mutation rejected（append-only）")
        if partition not in self._rows:
            raise AppendOnlyViolation(f"unknown partition: {partition!r}（四分区之外无承载）")
        if not row:
            raise AppendOnlyViolation("empty row rejected")
        normalized = _scalars(row)
        existing = self._rows[partition]
        if existing and set(normalized) != set(existing[0]):
            raise AppendOnlyViolation(
                f"partition {partition!r} row schema drift: keys {sorted(normalized)} != {sorted(existing[0])}（fail closed）"
            )
        existing.append(normalized)

    def add_manifest(self, manifest: RunManifest) -> None:
        self.add("manifest", manifest.to_row())

    def close(self) -> dict[str, ArtifactRef]:
        """落盘：每分区序列化 Parquet → registry put（kind = evidence:<partition>）。

        幂等：同内容重放产生同 digest（重放评价的 blob 路径恒同）。空分区跳过。
        """
        if self._closed:
            raise AppendOnlyViolation("writer already closed")
        self._closed = True
        refs: dict[str, ArtifactRef] = {}
        partition_digests: dict[str, str] = {}
        for name in PARTITIONS:
            rows = self._rows[name]
            if not rows:
                continue
            frame = pl.DataFrame(rows, strict=False)
            buf = io.BytesIO()
            frame.write_parquet(buf)
            blob = buf.getvalue()
            ref = self._registry.put(blob, f"evidence:{name}")
            refs[name] = ref
            partition_digests[name] = ref.digest
        run_manifest = {
            "partitions": partition_digests,
            "row_counts": {name: len(self._rows[name]) for name in PARTITIONS},
        }
        refs["run_manifest"] = self._registry.put(
            json.dumps(run_manifest, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            "evidence:run_manifest",
        )
        self._refs = refs
        return dict(refs)


def _scalars(row: dict[str, Any]) -> dict[str, Any]:
    """嵌套值 → JSON 字符串；其余标量直传（Parquet 列类型一致性由全行键校验保证）。"""
    out: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            out[key] = value
        else:
            out[key] = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return out


def rows_digest(rows: list[dict[str, Any]]) -> str:
    """分区行集的 digest（I1 复算比对基料：行序敏感——append-only 语义）。"""
    return content_digest([_scalars(r) for r in rows])
