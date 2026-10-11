"""权重工件面（Q-L13-20②：权重 = 工件——state_dict 入 kernel registry 内容寻址）。

规范化序列化 = 逐键（排序）"key|dtype|shape|原始小端字节" 拼接——字节级确定，
digest 跨运行/跨进程恒等（同一权重 → 同一 blob → 同一 registry 地址）。
parent_digests 携带谱系（数据 digest + 初始化谱系），L11 promotion 纪律同构。
"""
from __future__ import annotations

import hashlib

import torch

from galatea.kernel.packet import ArtifactRef
from galatea.kernel.registry import Registry
from galatea.subject.brain.module import NeuralModule


def serialize_state_dict(state: dict[str, torch.Tensor]) -> bytes:
    """规范化字节序列化（排序键；dtype/shape 头 + 小端原始字节）。"""
    chunks: list[bytes] = []
    for key in sorted(state):
        tensor = state[key].detach().contiguous()
        header = f"{key}|{tensor.dtype}|{tuple(tensor.shape)}|".encode("utf-8")
        chunks.append(header + tensor.numpy().tobytes())
    return b"\n".join(chunks)


def weights_blob_digest(state: dict[str, torch.Tensor]) -> str:
    """权重 blob 的 sha256（与 serialize_state_dict 字节一致——工件身份）。"""
    return hashlib.sha256(serialize_state_dict(state)).hexdigest()


def store_weights(registry: Registry, module: NeuralModule,
                  parent_digests: tuple[str, ...]) -> ArtifactRef:
    """state_dict → registry 内容寻址工件（kind=neural_weights；谱系强制）。"""
    if not parent_digests:
        raise ValueError("parent_digests required（权重工件必须携带谱系——Q-L13-20②）")
    blob = serialize_state_dict(module.state_dict())
    return registry.put(blob, kind="neural_weights", parent_digests=parent_digests)


def verify_weights(registry: Registry, ref: ArtifactRef, module: NeuralModule) -> bool:
    """工件回读核验（blob 字节全等——回读 ≠ 写入态即篡改/漂移检出）。"""
    entry = registry.get(ref)
    return entry.blob == serialize_state_dict(module.state_dict())
