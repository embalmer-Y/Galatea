"""摊销推断入口（HLD §15.1 知觉行 v2 引入；Q-L04-12①）。

摊销推断 = 学习前向网络从观测史直接产出潜后验（单次前向，无逐样本迭代优化）
——本入口即 RSSM 后验编码器的 typed 访问面：filter 历史产出 (h, z) 滤波状态，
posterior 产出对角高斯 q(z_t | x_t, h_t)。迭代精化（多轮修正至收敛/预算）
属 P4-β 工作空间草稿板面，不在 P4-α 范围（HLD §15.5 阶段联动）。

确定性：后验只以均值点估计进入下游（Q-G00-14① 给定权重确定性）；同输入
同权重双跑逐位恒等（Q-L13-20③ 部署双跑 bit-exact 的推断面）。
"""
from __future__ import annotations

import torch

from galatea.subject.brain.module import configure_deterministic_torch
from galatea.subject.brain.ports import GaussianPosterior
from galatea.subject.brain.world_model import RSSMWorldModel


def filter_history(model: RSSMWorldModel, xs: list[torch.Tensor]) -> tuple[torch.Tensor, torch.Tensor]:
    """观测史 → 滤波状态 (h, z)（摊销推断的序贯承载——recurrence 即摊销缓存）。"""
    configure_deterministic_torch()
    return model.filter_state(xs)


def infer_posterior(model: RSSMWorldModel, x: torch.Tensor, h: torch.Tensor) -> GaussianPosterior:
    """单次前向 → 对角高斯后验 q(z | x, h)（摊销定义；零迭代）。"""
    configure_deterministic_torch()
    with torch.no_grad():
        mu, logvar = model.posterior_parameters(x, h)
    return GaussianPosterior(mean=tuple(float(v) for v in mu),
                             logvar=tuple(float(v) for v in logvar))
