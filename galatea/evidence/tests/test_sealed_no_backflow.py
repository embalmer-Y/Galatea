"""sealed 不回流与命名空间纪律（L13 §4.3 no_backflow / isolation.namespace；Q-L13-02）。

判据：候选 data_scope digest 集 ∩ sealed digest 集 = ∅；非评价上下文读取 =
SealedContamination（S1）；命名空间只收 sealed: 前缀 kind；digest 入册可复算。
"""
import json
from pathlib import Path

import pytest

from galatea.evidence.evaluator.sealed import (
    GridCell,
    SealedContamination,
    SealedEvaluationToken,
    SealedNamespace,
    SplitResult,
    check_no_backflow,
    generate_split,
    load_split_policy,
)
from galatea.kernel.clock import CycleClock
from galatea.kernel.registry import Registry
from galatea.kernel.state import Stores

_ROOT = Path(__file__).resolve().parents[3]
MASTER_SEED = bytes.fromhex("aa" * 32)


def _make(tmp_path: Path, seeds: int = 8) -> tuple[SealedNamespace, SplitResult]:
    policy = load_split_policy(_ROOT)
    grid = tuple(
        GridCell(cell_id=f"{r}:{i}", regime=r, seed_index=i)
        for r in ("abundance", "scarcity", "volatile")
        for i in range(seeds)
    )
    result = generate_split(grid, MASTER_SEED, policy)
    stores = Stores(tmp_path / "stores")
    namespace = SealedNamespace(Registry(tmp_path / "registry", stores, CycleClock()), result.split_digest)
    return namespace, result


def test_no_backflow_detects_intersection() -> None:
    """候选 data_scope 含 sealed digest → 拒绝（promotion 第①步判据）。"""
    sealed_digests = {"d1", "d2", "d3"}
    check_no_backflow(frozenset({"x1", "x2"}), frozenset(sealed_digests))     # 无交集 → 通过
    with pytest.raises(SealedContamination):
        check_no_backflow(frozenset({"x1", "d2"}), frozenset(sealed_digests))  # 交集 = 污染


def test_namespace_put_kind_discipline(tmp_path: Path) -> None:
    namespace, result = _make(tmp_path)
    with pytest.raises(SealedContamination):
        namespace.put(b"internal-blob", "internal:training_set")     # 非 sealed 前缀 → 拒
    ref = namespace.put(b"sealed-grid-manifest", "sealed:split_manifest")
    assert namespace.data_digests == {ref.digest}                    # digest 入册（digest_recorded）


def test_namespace_get_requires_valid_token(tmp_path: Path) -> None:
    namespace, result = _make(tmp_path)
    ref = namespace.put(b"sealed-eval-blob", "sealed:eval_record")
    token = SealedEvaluationToken(result.split_digest, "promotion_gate_evaluation")
    entry = namespace.get(ref, token)                                # 合法评价上下文 → 可读
    assert entry.blob == b"sealed-eval-blob"
    with pytest.raises(SealedContamination):
        namespace.get(ref, result.internal.token)                    # internal token → 拒
    with pytest.raises(SealedContamination):
        namespace.get(ref, SealedEvaluationToken("other", "promotion_gate_evaluation"))
    with pytest.raises(SealedContamination):
        namespace.get(ref, "not-a-token")  # type: ignore[arg-type]


def test_namespace_rejects_foreign_kind_on_get(tmp_path: Path) -> None:
    """经裸 registry 塞入非 sealed kind，再经命名空间读取 → 检出。"""
    namespace, result = _make(tmp_path)
    stores = Stores(tmp_path / "stores2")   # 第二 registry 同目录结构——直接构造同库
    stores.close()
    raw = namespace._registry.put(b"raw", "internal:training_set")    # 绕过命名空间（模拟误用）
    token = SealedEvaluationToken(result.split_digest, "promotion_gate_evaluation")
    with pytest.raises(SealedContamination):
        namespace.get(raw, token)                                     # kind 纪律在读取侧仍强制


def test_split_manifest_registered_and_recomputable(tmp_path: Path) -> None:
    """分割 manifest（网格+种子+成员）入册；重放生成 → digest 恒等。"""
    namespace, result = _make(tmp_path)
    manifest = {
        "split_digest": result.split_digest,
        "sealed": [c.cell_id for c in result.sealed.cells],
        "internal": [c.cell_id for c in result.internal.cells],
    }
    ref = namespace.put(json.dumps(manifest, sort_keys=True).encode("utf-8"), "sealed:split_manifest")
    token = SealedEvaluationToken(result.split_digest, "promotion_gate_evaluation")
    loaded = json.loads(namespace.get(ref, token).blob.decode("utf-8"))
    assert loaded["split_digest"] == result.split_digest
    # 可复算：同种子重放分割 → 成员与 digest 全同
    policy = load_split_policy(_ROOT)
    grid = tuple(
        GridCell(cell_id=f"{r}:{i}", regime=r, seed_index=i)
        for r in ("abundance", "scarcity", "volatile")
        for i in range(8)
    )
    replay = generate_split(grid, MASTER_SEED, policy)
    assert replay.split_digest == result.split_digest
    assert [c.cell_id for c in replay.sealed.cells] == loaded["sealed"]


def test_retired_namespace_sealed_off(tmp_path: Path) -> None:
    namespace, result = _make(tmp_path)
    ref = namespace.put(b"blob", "sealed:eval_record")
    namespace.retire()
    token = SealedEvaluationToken(result.split_digest, "promotion_gate_evaluation")
    with pytest.raises(SealedContamination):
        namespace.get(ref, token)               # 轮换后读取 = 拒
    with pytest.raises(SealedContamination):
        namespace.put(b"more", "sealed:extra")  # 轮换后写入 = 拒
