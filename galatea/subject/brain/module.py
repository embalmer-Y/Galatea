"""NeuralModule 基类（Q-T02①② 的 P4 操作化；Q-L13-20②③）。

统一接口 = state_dict + digest + parent_digest 谱系：
- digest 为规范化聚合（逐键 sha256 → 排序行 sha256）——篡改检出（探针层A④ 同式）；
- parent_digest 缺失 = 谱系断裂（L11 LineageMissing 同族纪律，S2）——根模块以
  parent_digest="root" 显式声明，禁 None；
- 构造期确定性配置强制：单线程 + use_deterministic_algorithms + float32
  （Q-L13-20③ 探针配置即生产配置）；禁自持 RNG/时钟——随机性只经调用方
  显式传入的 torch.Generator（Q-T11 主体平面纪律在训练面的对应物）。
"""
from __future__ import annotations

import hashlib

import torch

_ROOT_PARENT_DIGEST = "root"


def configure_deterministic_torch() -> None:
    """给定权重确定性机器面配置（Q-L13-20③；幂等）。"""
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(1)


def _tensor_digest(t: torch.Tensor) -> str:
    return hashlib.sha256(t.detach().contiguous().numpy().tobytes()).hexdigest()


def per_key_digests(state: dict[str, torch.Tensor]) -> dict[str, str]:
    """逐键 sha256（权重身份的最细粒度；篡改检出粒度）。"""
    return {k: _tensor_digest(v) for k, v in sorted(state.items())}


def aggregate_digest(per_key: dict[str, str]) -> str:
    """聚合 digest = 排序 "k=hex" 行的 sha256（谱系/manifest 锚形式）。"""
    payload = "".join(f"{k}={per_key[k]}\n" for k in sorted(per_key)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class NeuralModule:
    """神经模块基类（state_dict + digest + parent_digest 谱系；Q-T02①）。"""

    def __init__(self, module: torch.nn.Module, parent_digest: str) -> None:
        configure_deterministic_torch()
        if not parent_digest:
            raise ValueError("parent_digest missing（谱系断裂 = LineageMissing 同族，禁 None）")
        self._module = module
        self.parent_digest = parent_digest

    @property
    def module(self) -> torch.nn.Module:
        return self._module

    def state_dict(self) -> dict[str, torch.Tensor]:
        return {k: v.detach().clone() for k, v in self._module.state_dict().items()}

    def digest(self) -> str:
        """聚合权重 digest（aggregate_digest ∘ per_key_digests）。"""
        return aggregate_digest(per_key_digests(self._module.state_dict()))

    def per_key(self) -> dict[str, str]:
        return per_key_digests(self._module.state_dict())

    def param_count(self) -> int:
        return sum(p.numel() for p in self._module.parameters())

    def load_state(self, state: dict[str, torch.Tensor]) -> None:
        """加载权重（录入前 shape 全等校验——谱系工件面录入合同）。"""
        current = self._module.state_dict()
        for key, value in current.items():
            if key not in state:
                raise ValueError(f"state key missing: {key}")
            if tuple(state[key].shape) != tuple(value.shape):
                raise ValueError(
                    f"state shape mismatch for {key}: {tuple(state[key].shape)} vs {tuple(value.shape)}")
        self._module.load_state_dict(state)

    @staticmethod
    def root_parent_digest() -> str:
        return _ROOT_PARENT_DIGEST
