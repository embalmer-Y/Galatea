"""RSSM 世界模型确定性测试（Q-L04-12①/Q-L13-20③④：双跑 bit-exact + 重放恒等）。"""
import torch

from galatea.subject.brain.error_stream import INPUT_DIM
from galatea.subject.brain.world_model import RSSMWorldModel
from galatea.subject.p4profile import load_p4_alpha_profile

_PARAMS = load_p4_alpha_profile()


def _make(seed: int) -> RSSMWorldModel:
    return RSSMWorldModel(_PARAMS, parent_digest="root", init_seed=seed)


def _synthetic_sequence(n: int, dim: int) -> list[torch.Tensor]:
    generator = torch.Generator().manual_seed(123)
    return [torch.randn(dim, generator=generator) * 0.1 for _ in range(n)]


def test_param_budget_asserted() -> None:
    """参数预算 [1e4, 1e6] 构造期断言（profile 钉死；超界构造即拒）。"""
    model = _make(1)
    assert _PARAMS.param_budget_min <= model.param_count() <= _PARAMS.param_budget_max


def test_seed_sensitivity_initialization() -> None:
    """同种子初始化逐位恒等 / 异种子必不同（种子敏感性——反空转）。"""
    d1 = _make(7).digest()
    d2 = _make(7).digest()
    d3 = _make(8).digest()
    assert d1 == d2
    assert d1 != d3


def test_filter_double_run_bit_exact() -> None:
    """冻结权重同输入双跑 bit-exact（Q-L13-20③ 部署机械判据）。"""
    model = _make(7)
    xs = _synthetic_sequence(12, INPUT_DIM)
    preds1 = model.filter_sequence(xs)
    preds2 = model.filter_sequence(xs)
    assert len(preds1) == len(xs)
    for p1, p2 in zip(preds1, preds2):
        assert p1.numpy().tobytes() == p2.numpy().tobytes()


def test_training_replay_weights_bit_exact() -> None:
    """训练重放：同种子同数据 → 末权重逐位恒等（Q-L13-20① 宪法语义核心）。"""
    xs = _synthetic_sequence(24, INPUT_DIM)
    model_a = _make(7)
    losses_a = model_a.train_on_sequence(xs, lr=0.01, epochs=30)
    model_b = _make(7)
    losses_b = model_b.train_on_sequence(xs, lr=0.01, epochs=30)
    assert model_a.digest() == model_b.digest(), "重放末权重必须逐位恒等"
    assert losses_a[-1] == losses_b[-1], "重放损失曲线末位必须恒等"


def test_training_loss_decreases_and_seed_matters() -> None:
    """训练损失必须下降（学习发生）+ 异初始化种子产生不同权重（学习非恒等映射）。"""
    xs = _synthetic_sequence(40, INPUT_DIM)
    model = _make(7)
    losses = model.train_on_sequence(xs, lr=0.01, epochs=40)
    assert losses[-1] < losses[0], f"loss must decrease: {losses[0]} -> {losses[-1]}"
    other = _make(8)
    other.train_on_sequence(xs, lr=0.01, epochs=40)
    assert other.digest() != model.digest()


def test_imagine_consistent_with_filter_and_deterministic() -> None:
    """想象 h=1 预测与滤波末拍预测同式恒等；双跑 bit-exact；长度 = steps。"""
    xs = _synthetic_sequence(10, INPUT_DIM)
    model = _make(7)
    model.train_on_sequence(xs, lr=0.01, epochs=5)
    preds = model.filter_sequence(xs)
    h, z = model.filter_state(xs)
    imagined = model.imagine(h, z, steps=4)
    assert len(imagined) == 4
    assert imagined[0].numpy().tobytes() == preds[-1].numpy().tobytes(), (
        "h=1 想象预测必须与滤波末拍预测同式恒等（同一 dec(h_t, z_t) 面）")
    again = model.imagine(h, z, steps=4)
    for p1, p2 in zip(imagined, again):
        assert p1.numpy().tobytes() == p2.numpy().tobytes()


def test_sequence_length_guards() -> None:
    """序列下限守卫（禁伪造零预测/空训练）。"""
    model = _make(7)
    for method in ("filter_state", "filter_sequence", "train_on_sequence"):
        try:
            if method == "filter_state":
                model.filter_state([])
            elif method == "filter_sequence":
                model.filter_sequence([])
            else:
                model.train_on_sequence([], lr=0.01, epochs=1)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{method} must reject empty sequence")
    try:
        model.imagine(torch.zeros(model.det_dim), torch.zeros(model.latent_dim), steps=0)
    except ValueError:
        pass
    else:
        raise AssertionError("imagine steps=0 must be rejected")
