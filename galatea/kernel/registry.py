"""content-addressed registry 核心（L00 §4.5；Q-T09 CONFIRMED：自研 ~500 行、拒网络源）。

布局：registry/<sha256[:2]>/<sha256>/（manifest.json + blob）；索引 registry.db
（经 Stores 单写者句柄落账）。put 幂等（同 digest 同内容）；幂等分支带**索引对账
补写**（ADR-G-0003 R5①：文件在、索引缺的中间态自愈）；blob 与 manifest 不符 →
RegistryCollision（fail closed，S0）；get 引用缺件 → ArtifactMissing（R9③）。
治理（promotion/sealed）在 L13，本模块只做存取与 digest 完整性。
"""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from galatea.kernel.clock import CycleClock
from galatea.kernel.digest import blob_digest, content_digest
from galatea.kernel.packet import ArtifactRef
from galatea.kernel.state import StoreName, Stores, WriterHandle


class RegistryCollision(RuntimeError):
    """同 digest 路径下内容与 manifest 不符（完整性破坏，S0）。"""


class ArtifactMissing(KeyError):
    """get 引用不存在的 artifact（区别于内容完整性破坏；ADR-G-0003 R9③）。"""

    def __init__(self, digest: str) -> None:
        super().__init__(f"missing artifact: {digest}")
        self.digest = digest


@dataclass(frozen=True, slots=True)
class RegistryEntry:
    manifest: dict[str, object]
    blob: bytes


class Registry:
    """只增不改的内容寻址存储；get 只读。"""

    def __init__(self, root: Path, stores: Stores, clock: CycleClock) -> None:
        self._root = root
        self._stores = stores
        self._clock = clock
        # 事件序号从 DB 恢复（多 Registry 实例共享同一 registry 库时续接——
        # M2 SC5 重放场景暴露：实例内重置会撞 PRIMARY KEY）
        row = stores.read(StoreName.REGISTRY, "SELECT COALESCE(MAX(seq), 0) FROM registry_events")
        self._event_seq = int(cast(int, row[0][0]))

    # —— 内部 ——
    def _dir(self, digest: str) -> Path:
        return self._root / digest[:2] / digest

    def _record_event(self, writer: WriterHandle, op: str, digest: str) -> None:
        self._event_seq += 1
        writer.execute(
            "INSERT INTO registry_events (seq, op, digest, cycle) VALUES (?, ?, ?, ?)",
            (self._event_seq, op, digest, self._clock.cycle),
        )

    def _ensure_indexed(self, digest: str) -> None:
        """幂等分支的索引对账补写（ADR-G-0003 R5①：文件在、索引缺的中间态自愈）。"""
        if self._stores.read(StoreName.REGISTRY, "SELECT digest FROM artifacts WHERE digest = ?", (digest,)):
            return
        manifest = cast(
            "dict[str, Any]",
            json.loads((self._dir(digest) / "manifest.json").read_bytes().decode("utf-8")),
        )
        writer = self._stores.open_writer(StoreName.REGISTRY, "artifacts", "registry_builder")
        parents = self._stores.open_writer(StoreName.REGISTRY, "artifact_parents", "registry_builder")
        events = self._stores.open_writer(StoreName.REGISTRY, "registry_events", "registry_builder")
        with writer.transaction():
            writer.execute(
                "INSERT OR IGNORE INTO artifacts (digest, kind, created_cycle, size, manifest_digest) VALUES (?, ?, ?, ?, ?)",
                (
                    digest,
                    str(manifest["kind"]),
                    int(cast("int", manifest["created_cycle"])),
                    int(cast("int", manifest["size"])),
                    content_digest(manifest),
                ),
            )
            for parent in cast("list[str]", manifest.get("parent_digests", [])):
                parents.execute(
                    "INSERT OR IGNORE INTO artifact_parents (digest, parent_digest) VALUES (?, ?)",
                    (digest, parent),
                )
            self._record_event(events, "backfill_index", digest)

    def put(self, blob: bytes, kind: str, parent_digests: tuple[str, ...] = ()) -> ArtifactRef:
        """幂等写入：同 digest 同内容直接返回（并补齐缺失索引）；目录存在但内容不符 → RegistryCollision。"""
        if not kind:
            raise ValueError("kind must be non-empty")
        digest = blob_digest(blob)
        target = self._dir(digest)
        manifest = {
            "kind": kind,
            "digest": digest,
            "size": len(blob),
            "created_cycle": self._clock.cycle,
            "parent_digests": list(parent_digests),
        }
        manifest_digest = content_digest(manifest)
        if target.exists():
            existing = (target / "blob").read_bytes()
            if blob_digest(existing) != digest:
                raise RegistryCollision(f"content mismatch under {digest}")
            self._ensure_indexed(digest)
        else:
            target.mkdir(parents=True)
            (target / "manifest.json").write_bytes(
                json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
            )
            (target / "blob").write_bytes(blob)
            writer = self._stores.open_writer(StoreName.REGISTRY, "artifacts", "registry_builder")
            parents = self._stores.open_writer(StoreName.REGISTRY, "artifact_parents", "registry_builder")
            events = self._stores.open_writer(StoreName.REGISTRY, "registry_events", "registry_builder")
            with writer.transaction():
                writer.execute(
                    "INSERT OR IGNORE INTO artifacts (digest, kind, created_cycle, size, manifest_digest) VALUES (?, ?, ?, ?, ?)",
                    (digest, kind, self._clock.cycle, len(blob), manifest_digest),
                )
                for parent in parent_digests:
                    parents.execute(
                        "INSERT OR IGNORE INTO artifact_parents (digest, parent_digest) VALUES (?, ?)",
                        (digest, parent),
                    )
                self._record_event(events, "put", digest)
        return ArtifactRef(digest=digest, kind=kind)

    def get(self, ref: ArtifactRef) -> RegistryEntry:
        """只读取回：blob 与 manifest digest 双重校验，不符即 RegistryCollision；缺件 → ArtifactMissing。"""
        target = self._dir(ref.digest)
        manifest_path = target / "manifest.json"
        blob_path = target / "blob"
        if not manifest_path.exists() or not blob_path.exists():
            raise ArtifactMissing(ref.digest)
        manifest: dict[str, object] = json.loads(manifest_path.read_bytes().decode("utf-8"))
        blob = blob_path.read_bytes()
        if blob_digest(blob) != ref.digest:
            raise RegistryCollision(f"blob digest mismatch for {ref.digest}")
        if manifest.get("digest") != ref.digest:
            raise RegistryCollision(f"manifest digest mismatch for {ref.digest}")
        return RegistryEntry(manifest=manifest, blob=blob)

    def index_digest(self) -> str:
        """索引视图 digest（checkpoint 的 registry_view 用）。"""
        rows = self._stores.read(
            StoreName.REGISTRY, "SELECT digest, kind, created_cycle, size, manifest_digest FROM artifacts ORDER BY digest"
        )
        return content_digest([list(r) for r in rows])

    def events(self) -> tuple[tuple[object, ...], ...]:
        return tuple(self._stores.read(StoreName.REGISTRY, "SELECT seq, op, digest, cycle FROM registry_events ORDER BY seq"))
