"""recorder append-only 与四分区纪律（L13 §4.2/§7；Q-T06 Parquet 唯一承载）。

断言：分区 blob 内容寻址（同内容 = 同 digest 幂等；分叉 = RegistryCollision）；
关闭后写入拒绝；行 schema 逐行一致 fail-closed；墙钟仅 manifest 分区（Q-T12）。
"""
import json
from pathlib import Path

import pytest

from galatea.evidence.recorder.manifest import RunManifest
from galatea.evidence.recorder.replay import read_partition
from galatea.evidence.recorder.writer import AppendOnlyViolation, EvidenceWriter
from galatea.kernel.clock import CycleClock
from galatea.kernel.registry import Registry, RegistryCollision
from galatea.kernel.state import Stores


def _registry(tmp_path: Path) -> Registry:
    stores = Stores(tmp_path / "stores")
    return Registry(tmp_path / "registry", stores, CycleClock())


def _writer(tmp_path: Path) -> EvidenceWriter:
    return EvidenceWriter(_registry(tmp_path))


def test_partitions_immutable_after_close(tmp_path: Path) -> None:
    w = _writer(tmp_path)
    w.add_manifest(RunManifest.create("run-1", "aa" * 32, "B", (("m0_mw0", "d0"),), "spd", None))
    w.add("evidence", {"trial": "t1", "aware": True})
    w.add("trace", {"trial": "t1", "mode": "retrieved"})
    refs = w.close()
    assert set(refs) == {"manifest", "run_manifest", "evidence", "trace"}
    with pytest.raises(AppendOnlyViolation):
        w.add("evidence", {"trial": "t2", "aware": False})   # 关闭后写入 = 拒
    with pytest.raises(AppendOnlyViolation):
        w.close()                                             # 二次关闭 = 拒


def test_partition_blob_content_addressed_idempotent(tmp_path: Path) -> None:
    """同分区同内容重放 → 同 digest（append-only 的内容寻址承载）。"""
    rows = [{"trial": f"t{i}", "aware": i % 2 == 0} for i in range(8)]
    refs1 = _close_with_rows(tmp_path / "r1", rows)
    refs2 = _close_with_rows(tmp_path / "r2", rows)
    assert refs1["evidence"].digest == refs2["evidence"].digest
    # 内容分叉（同 kind 异内容）→ 不同 digest，互不覆盖：
    refs3 = _close_with_rows(tmp_path / "r3", rows[:-1])
    assert refs3["evidence"].digest != refs1["evidence"].digest


def _close_with_rows(base: Path, rows: list[dict[str, object]]) -> dict[str, object]:
    stores = Stores(base / "stores")
    try:
        w = EvidenceWriter(Registry(base / "registry", stores, CycleClock()))
        for row in rows:
            w.add("evidence", dict(row))
        return dict(w.close())
    finally:
        stores.close()


def test_row_schema_uniform_fail_closed(tmp_path: Path) -> None:
    w = _writer(tmp_path)
    w.add("metrics", {"n": 4, "carry": 4})
    with pytest.raises(AppendOnlyViolation):   # 键集漂移 = 行 schema 不一致（writer 强制）
        w.add("metrics", {"n": 4})
        w.close()


def test_unknown_partition_rejected(tmp_path: Path) -> None:
    w = _writer(tmp_path)
    with pytest.raises(AppendOnlyViolation):
        w.add("notebook_outputs", {"x": 1})   # 四分区之外无承载（禁 Notebook 当 claim）


def test_wall_clock_only_in_manifest_partition(tmp_path: Path) -> None:
    """Q-T12：墙钟只出现在 manifest 分区行；trace/metrics/evidence 无墙钟列。"""
    w = _writer(tmp_path)
    w.add_manifest(
        RunManifest.create("run-1", "aa" * 32, "B", (("m0_mw0", "d0"),), "spd", None)
    )
    w.add("trace", {"trial": "t1"})
    refs = w.close()
    stores = Stores(tmp_path / "stores")
    try:
        reg = Registry(tmp_path / "registry", stores, CycleClock())
        manifest_rows = read_partition(reg, refs["manifest"])
        trace_rows = read_partition(reg, refs["trace"])
    finally:
        stores.close()
    assert "wall_clock_utc" in manifest_rows[0]
    assert all("wall_clock_utc" not in row for row in trace_rows)
