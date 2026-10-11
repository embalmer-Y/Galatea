"""权重工件面测试（Q-L13-20②：registry 内容寻址 + 谱系 + 篡改检出）。"""
import tempfile
from pathlib import Path

import torch

from galatea.kernel.clock import CycleClock
from galatea.kernel.registry import Registry
from galatea.kernel.state import Stores
from galatea.subject.brain.module import NeuralModule
from galatea.subject.brain.weights import (
    serialize_state_dict,
    store_weights,
    verify_weights,
    weights_blob_digest,
)


def _module(seed: int) -> NeuralModule:
    generator = torch.Generator().manual_seed(seed)
    linear = torch.nn.Linear(3, 2)
    with torch.no_grad():
        linear.weight.copy_(torch.randn(2, 3, generator=generator) * 0.01)
        linear.bias.zero_()
    return NeuralModule(linear, parent_digest="root")


def test_serialization_deterministic() -> None:
    """规范化序列化字节确定（同权重两次序列化逐字节相等）。"""
    state = _module(1).state_dict()
    blob_a = serialize_state_dict(state)
    blob_b = serialize_state_dict(_module(1).state_dict())
    assert blob_a == blob_b
    assert weights_blob_digest(state) == weights_blob_digest(_module(1).state_dict())


def test_store_verify_roundtrip_and_tamper() -> None:
    """registry 往返 + 回读核验；写入后改权重 → verify False（篡改检出）。"""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        stores = Stores(root / "stores")
        try:
            registry = Registry(root / "registry", stores, CycleClock())
            module = _module(2)
            ref = store_weights(registry, module, parent_digests=("data-digest", "init-digest"))
            assert ref.kind == "neural_weights"
            assert verify_weights(registry, ref, module) is True
            with torch.no_grad():
                module.module.bias.add_(0.5)
            assert verify_weights(registry, ref, module) is False, "改写后回读必须失配"
        finally:
            stores.close()


def test_lineage_required() -> None:
    """parent_digests 空 = 拒（权重工件必须携带谱系——Q-L13-20②）。"""
    import pytest

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        stores = Stores(root / "stores")
        try:
            registry = Registry(root / "registry", stores, CycleClock())
            with pytest.raises(ValueError, match="parent_digests"):
                store_weights(registry, _module(2), parent_digests=())
        finally:
            stores.close()
