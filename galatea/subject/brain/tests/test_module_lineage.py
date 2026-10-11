"""NeuralModule 谱系测试（Q-T02①/Q-L13-20②：state_dict + digest + parent_digest）。"""
import torch

from galatea.subject.brain.module import (
    NeuralModule,
    aggregate_digest,
    configure_deterministic_torch,
    per_key_digests,
)
from galatea.subject.p4profile import load_p4_alpha_profile


def _linear(seed: int) -> torch.nn.Linear:
    configure_deterministic_torch()
    generator = torch.Generator().manual_seed(seed)
    module = torch.nn.Linear(4, 2)
    with torch.no_grad():
        module.weight.copy_(torch.randn(2, 4, generator=generator) * 0.01)
        module.bias.zero_()
    return module


def test_deterministic_config_enforced() -> None:
    """构造期确定性配置（Q-L13-20③：单线程 + deterministic + float32）。"""
    configure_deterministic_torch()
    assert torch.get_num_threads() == 1
    assert torch.are_deterministic_algorithms_enabled()
    assert torch.get_default_dtype() is torch.float32


def test_digest_stable_and_tamper_detected() -> None:
    """digest 稳定 + 篡改检出（探针层A④ 同式）。"""
    module = NeuralModule(_linear(11), parent_digest="root")
    d1 = module.digest()
    d2 = module.digest()
    assert d1 == d2 and len(d1) == 64
    per_key = module.per_key()
    assert set(per_key) == {"bias", "weight"}
    with torch.no_grad():
        module.module.weight.add_(1e-3)
    assert module.digest() != d1, "权重篡改必须被 digest 检出"


def test_parent_digest_required() -> None:
    """parent_digest 缺失 = 拒（谱系断裂禁 None；根以 "root" 显式声明）。"""
    try:
        NeuralModule(_linear(11), parent_digest="")
    except ValueError as error:
        assert "parent_digest" in str(error)
    else:
        raise AssertionError("empty parent_digest must be rejected")


def test_seed_sensitivity_and_aggregate() -> None:
    """同种子逐位恒等 / 异种子必不同（种子敏感性——否则断言空转）；聚合式稳定。"""
    d_same = per_key_digests(_linear(5).state_dict()) == per_key_digests(_linear(5).state_dict())
    d_diff = per_key_digests(_linear(5).state_dict()) != per_key_digests(_linear(6).state_dict())
    assert d_same and d_diff
    assert aggregate_digest(per_key_digests(_linear(5).state_dict())) == (
        NeuralModule(_linear(5), "root").digest())


def test_load_state_shape_guard() -> None:
    """录入 shape 不符 = 拒（谱系工件面录入合同）。"""
    module = NeuralModule(_linear(11), parent_digest="root")
    bad = dict(module.state_dict())
    bad["weight"] = torch.zeros(3, 4)
    try:
        module.load_state(bad)
    except ValueError as error:
        assert "shape mismatch" in str(error)
    else:
        raise AssertionError("shape mismatch must be rejected")


def test_profile_param_budget_loaded() -> None:
    """profile 预算链路可用（world_model 构造期断言的参数源）。"""
    params = load_p4_alpha_profile()
    assert params.param_budget_min == 10000 and params.param_budget_max == 1000000
