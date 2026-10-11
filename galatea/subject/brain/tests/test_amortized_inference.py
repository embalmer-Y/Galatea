"""摊销推断入口测试（单次前向后验；双跑逐位恒等）。"""
import torch

from galatea.subject.brain.amortized import filter_history, infer_posterior
from galatea.subject.brain.error_stream import INPUT_DIM
from galatea.subject.brain.world_model import RSSMWorldModel
from galatea.subject.p4profile import load_p4_alpha_profile

_PARAMS = load_p4_alpha_profile()


def _model() -> RSSMWorldModel:
    return RSSMWorldModel(_PARAMS, parent_digest="root", init_seed=3)


def _sequence(n: int) -> list[torch.Tensor]:
    generator = torch.Generator().manual_seed(99)
    return [torch.randn(INPUT_DIM, generator=generator) * 0.1 for _ in range(n)]


def test_posterior_shape_and_determinism() -> None:
    """后验维 = latent_dim；同输入双跑逐位恒等（摊销定义——零迭代单前向）。"""
    model = _model()
    xs = _sequence(6)
    h, _z = filter_history(model, xs)
    x = torch.randn(INPUT_DIM, generator=torch.Generator().manual_seed(1)) * 0.1
    post1 = infer_posterior(model, x, h)
    post2 = infer_posterior(model, x, h)
    assert post1 == post2
    assert len(post1.mean) == _PARAMS.latent_dim
    assert len(post1.logvar) == _PARAMS.latent_dim


def test_posterior_tracks_input() -> None:
    """异输入 → 异后验（摊销推断对观测连贯响应——非恒等映射）。"""
    model = _model()
    xs = _sequence(6)
    h, _z = filter_history(model, xs)
    x_a = _sequence(1)[0]
    x_b = _sequence(1)[0] + 0.5
    post_a = infer_posterior(model, x_a, h)
    post_b = infer_posterior(model, x_b, h)
    assert post_a != post_b


def test_filter_history_state_shapes() -> None:
    """滤波状态形状 = (det_dim, latent_dim)。"""
    model = _model()
    h, z = filter_history(model, _sequence(4))
    assert h.shape == (model.det_dim,)
    assert z.shape == (model.latent_dim,)
