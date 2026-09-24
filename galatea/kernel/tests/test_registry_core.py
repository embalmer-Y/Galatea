"""registry 核心合同（L00 §4.5；文件补录 L00 §10，承 REV-0003 R6 先例——2026-09-25）。

覆盖：put/get 往返与幂等、索引对账补写（R5①）、ArtifactMissing（R9③）、
RegistryCollision、写面表级作用域（R9②的 registry 侧回归）。
"""
import hashlib
from pathlib import Path

import pytest

from galatea.kernel.clock import CycleClock
from galatea.kernel.packet import ArtifactRef
from galatea.kernel.registry import ArtifactMissing, Registry, RegistryCollision
from galatea.kernel.state import OwnershipViolation, StoreName, Stores


def _make(tmp_path: Path) -> tuple[Registry, Stores, CycleClock]:
    stores = Stores(tmp_path / "stores")
    clock = CycleClock()
    return Registry(tmp_path / "registry", stores, clock), stores, clock


def test_put_get_roundtrip_and_idempotent(tmp_path: Path) -> None:
    registry, stores, _ = _make(tmp_path)
    ref = registry.put(b"payload-alpha", "payload")
    entry = registry.get(ref)
    assert entry.blob == b"payload-alpha"
    assert entry.manifest["kind"] == "payload"
    again = registry.put(b"payload-alpha", "payload")
    assert again == ref
    rows = stores.read(StoreName.REGISTRY, "SELECT count(*) FROM artifacts WHERE digest = ?", (ref.digest,))
    assert rows == [(1,)]  # 幂等：索引不重复


def test_index_backfill_heals_missing_index(tmp_path: Path) -> None:
    """模拟"文件在、索引缺"中间态：删索引行 → 再 put → 索引自愈 + backfill_index 事件（R5①）。"""
    registry, stores, _ = _make(tmp_path)
    ref = registry.put(b"payload-beta", "payload")
    writer = stores.open_writer(StoreName.REGISTRY, "artifacts", "registry_builder")
    with writer.transaction():
        writer.execute("DELETE FROM artifacts WHERE digest = ?", (ref.digest,))
    assert stores.read(StoreName.REGISTRY, "SELECT count(*) FROM artifacts WHERE digest = ?", (ref.digest,)) == [(0,)]
    registry.put(b"payload-beta", "payload")  # 幂等分支触发补写
    assert stores.read(StoreName.REGISTRY, "SELECT count(*) FROM artifacts WHERE digest = ?", (ref.digest,)) == [(1,)]
    ops = [row[1] for row in stores.read(StoreName.REGISTRY, "SELECT seq, op FROM registry_events ORDER BY seq")]
    assert "backfill_index" in ops
    assert registry.index_digest() != ""  # checkpoint 的 registry_view 不再漏掉该工件


def test_get_missing_is_artifact_missing(tmp_path: Path) -> None:
    """缺件 → ArtifactMissing（区别于完整性破坏的 RegistryCollision，R9③）。"""
    registry, _, _ = _make(tmp_path)
    ghost = ArtifactRef(digest="a" * 64, kind="payload")
    with pytest.raises(ArtifactMissing):
        registry.get(ghost)


def test_get_tampered_blob_is_collision(tmp_path: Path) -> None:
    registry, _, _ = _make(tmp_path)
    ref = registry.put(b"payload-gamma", "payload")
    blob_path = tmp_path / "registry" / ref.digest[:2] / ref.digest / "blob"
    blob_path.write_bytes(b"tampered")
    with pytest.raises(RegistryCollision):
        registry.get(ref)


def test_put_detects_preexisting_content_mismatch(tmp_path: Path) -> None:
    registry, _, _ = _make(tmp_path)
    digest = hashlib.sha256(b"intended").hexdigest()
    target = tmp_path / "registry" / digest[:2] / digest
    target.mkdir(parents=True)
    (target / "blob").write_bytes(b"something-else")
    with pytest.raises(RegistryCollision):
        registry.put(b"intended", "payload")


def test_writer_handles_cannot_cross_tables(tmp_path: Path) -> None:
    """registry 侧回归：R9② 表级作用域在 put 用的三个句柄上生效。"""
    registry, stores, _ = _make(tmp_path)
    registry.put(b"x", "payload")
    wrong = stores.open_writer(StoreName.REGISTRY, "registry_events", "registry_builder")
    with pytest.raises(OwnershipViolation):
        wrong.execute("INSERT INTO artifacts (digest, kind, created_cycle, size, manifest_digest) VALUES ('d', 'k', 0, 0, 'm')")
