"""I1 重放复算：recorder 数据 → 指标复算 digest bit-exact（L13 §4.8/§7；R0 硬前置）。

独立重算边界：recompute 只消费 DuckDB 读出的行，禁携带运行时内存对象。
"""
from pathlib import Path

import pytest

from galatea.evidence.recorder.replay import recompute_i1, read_partition
from galatea.evidence.recorder.writer import EvidenceWriter
from galatea.kernel.clock import CycleClock
from galatea.kernel.digest import content_digest
from galatea.kernel.registry import Registry, RegistryCollision
from galatea.kernel.state import Stores


def _evaluate_rows(n: int = 16) -> list[dict[str, object]]:
    return [
        {"pair_index": i, "cell_id": f"volatile:{i % 4}", "carry_aware": i % 3 != 0, "naive_aware": False}
        for i in range(n)
    ]


def _vector_digest(rows: list[dict[str, object]]) -> str:
    ordered = sorted(rows, key=lambda r: int(r["pair_index"]))
    return content_digest(
        {
            "carry": [bool(r["carry_aware"]) for r in ordered],
            "naive": [bool(r["naive_aware"]) for r in ordered],
        }
    )


def _write_run(tmp_path: Path, rows: list[dict[str, object]]) -> tuple[Registry, dict[str, object], str]:
    stores = Stores(tmp_path / "stores")
    try:
        registry = Registry(tmp_path / "registry", stores, CycleClock())
        writer = EvidenceWriter(registry)
        for row in rows:
            writer.add("evidence", dict(row))
        writer.add("metrics", {"n": len(rows), "vector_digest": _vector_digest(rows)})
        refs = writer.close()
        return registry, dict(refs), _vector_digest(rows)
    finally:
        stores.close()


def _recompute_metrics(partitions: dict[str, list[dict[str, object]]]) -> str:
    return _vector_digest(partitions["evidence"])


def test_i1_recompute_bit_exact(tmp_path: Path) -> None:
    rows = _evaluate_rows()
    registry, refs, expected = _write_run(tmp_path, rows)
    report = recompute_i1(registry, refs, _recompute_metrics, expected)  # type: ignore[arg-type]
    assert report.mode == "I1"
    assert report.match, report.diffs
    assert report.outputs_digest == expected
    assert report.diffs == ()


def test_i1_detects_metric_drift(tmp_path: Path) -> None:
    """复算输入与期望产出不符 → match=False + diffs 留痕（禁把 mismatch 当通过）。"""
    rows = _evaluate_rows()
    registry, refs, expected = _write_run(tmp_path, rows)
    drifted = [dict(r) for r in rows]
    drifted[0] = {**drifted[0], "carry_aware": True}   # 注入一处指标漂移
    report = recompute_i1(registry, refs, lambda p: _vector_digest(drifted), expected)  # type: ignore[arg-type]
    assert not report.match
    assert report.diffs


def test_i1_readback_equality_through_duckdb(tmp_path: Path) -> None:
    """DuckDB 读回的行与写入行逐字段相等（Parquet 承载无信息损失）。"""
    rows = _evaluate_rows(4)
    registry, refs, _ = _write_run(tmp_path, rows)
    stores = Stores(tmp_path / "stores")
    try:
        reg = Registry(tmp_path / "registry", stores, CycleClock())
        back = read_partition(reg, refs["evidence"])  # type: ignore[arg-type]
    finally:
        stores.close()
    assert len(back) == len(rows)
    for original, read_back in zip(rows, back):
        assert read_back["pair_index"] == original["pair_index"]
        assert read_back["carry_aware"] == original["carry_aware"]
        assert read_back["naive_aware"] == original["naive_aware"]
        assert read_back["cell_id"] == original["cell_id"]


def test_i1_registry_collision_detected(tmp_path: Path) -> None:
    """同 digest 路径内容分叉 → RegistryCollision（S0，fail closed）。"""
    registry, refs, _ = _write_run(tmp_path / "a", _evaluate_rows(4))
    stores = Stores(tmp_path / "a" / "stores")
    try:
        reg = Registry(tmp_path / "a" / "registry", stores, CycleClock())
        target = tmp_path / "a" / "registry" / refs["evidence"].digest[:2] / refs["evidence"].digest / "blob"
        blob = target.read_bytes()
        target.write_bytes(blob + b"tampered")
        with pytest.raises(RegistryCollision):
            read_partition(reg, refs["evidence"])  # type: ignore[arg-type]
    finally:
        stores.close()
