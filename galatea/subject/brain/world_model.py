"""RSSM 式潜状态世界模型（Q-L04-12①；HLD §15.1 世界/自我模型行 v2 引入）。

架构 = 确定性 recurrent 状态 h + 随机潜变量 z（对角高斯 q/p），小尺度 CPU 级：

    h_t = tanh(W_xh·x_t + W_hh·h_{t-1} + W_zh·z_{t-1} + b_h)     # 确定性递归
    q(z_t) = N(μ_q(x_t, h_t), σ_q²(x_t, h_t))                    # 摊销后验
    p(z_t) = N(μ_p(h_t), σ_p²(h_t))                              # 学习先验
    x̂_{t+1} = W_dec·[h_t, z_t] + b_dec                           # 下一拍预测

**随机潜变量的确定性操作化**（给定权重确定性 Q-G00-14①；Q-L13-20④）：
训练目标 = 采样自由 ELBO——闭式 KL(q‖p) + 后验均值重构 MSE；z 以均值点估计
进入计算图，训练/推理零采样 RNG（全批量，无 minibatch 采样——确定性由构造
成立）。随机性存在于变分分布结构中，计算路径逐位确定。β=1 即标准 ELBO 本身
（恒等式非调节常数）。logvar 夹持 ±10 = float32 溢出防护（工程护栏非语义参数）。

转移语义继承 Q-L04-09：训练数据仅主体平面形成帧（禁信念内模拟隐藏真值过程）；
隐层宽 = latent_dim（profile 冻结值复用，零新自由常数）；初始化 0.01σ = 探针
同式（ADR-G-0030 §2 锚）。param_budget [1e4, 1e6] 构造期断言（profile 钉死）。
"""
from __future__ import annotations

import torch
from torch import nn

from galatea.subject.brain.error_stream import INPUT_DIM
from galatea.subject.brain.module import NeuralModule, configure_deterministic_torch
from galatea.subject.p4profile import P4AlphaBrainParams

_LOGVAR_CLAMP = 10.0     # float32 数值稳定性夹持（溢出防护非语义参数）
_INIT_SIGMA = 0.01       # 探针同式（ADR-G-0030 §2：种子化 Generator 初始化 0.01σ）


class _RSSMCore(nn.Module):
    """torch 模块核（参数容器；无业务语义）。"""

    def __init__(self, input_dim: int, latent_dim: int, det_dim: int,
                 generator: torch.Generator) -> None:
        super().__init__()
        hidden = latent_dim                       # 隐层宽 = latent_dim（冻结值复用）
        self.cell_x = nn.Linear(input_dim, det_dim, bias=False)
        self.cell_h = nn.Linear(det_dim, det_dim, bias=False)
        self.cell_z = nn.Linear(latent_dim, det_dim, bias=False)
        self.cell_b = nn.Parameter(torch.zeros(det_dim))
        self.enc_in = nn.Linear(input_dim + det_dim, hidden)
        self.enc_mu = nn.Linear(hidden, latent_dim)
        self.enc_logvar = nn.Linear(hidden, latent_dim)
        self.pri_in = nn.Linear(det_dim, hidden)
        self.pri_mu = nn.Linear(hidden, latent_dim)
        self.pri_logvar = nn.Linear(hidden, latent_dim)
        self.dec = nn.Linear(det_dim + latent_dim, input_dim)
        for param in self.parameters():
            with torch.no_grad():
                param.copy_(torch.randn(param.shape, generator=generator) * _INIT_SIGMA)
        nn.init.zeros_(self.cell_b)


class RSSMWorldModel(NeuralModule):
    """潜状态序列世界模型（P4-α 脑核；Q-L04-12①）。"""

    def __init__(self, params: P4AlphaBrainParams, parent_digest: str, init_seed: int,
                 input_dim: int = INPUT_DIM) -> None:
        configure_deterministic_torch()
        generator = torch.Generator().manual_seed(init_seed)
        core = _RSSMCore(input_dim, params.latent_dim, params.deterministic_state_dim, generator)
        super().__init__(core, parent_digest)
        self.input_dim = input_dim
        self.latent_dim = params.latent_dim
        self.det_dim = params.deterministic_state_dim
        count = self.param_count()
        if not params.param_budget_min <= count <= params.param_budget_max:
            raise ValueError(
                f"param count {count} out of frozen budget [{params.param_budget_min}, "
                f"{params.param_budget_max}]（Q-L04-12① CPU 级预算，构造期断言）")

    # ---------------------------------------------------------------- 单步
    def _core(self) -> _RSSMCore:
        core = self.module
        if not isinstance(core, _RSSMCore):      # pragma: no cover - 类型守卫
            raise TypeError("core module type drift")
        return core

    @staticmethod
    def _kl_closed_form(mu_q: torch.Tensor, logvar_q: torch.Tensor,
                        mu_p: torch.Tensor, logvar_p: torch.Tensor) -> torch.Tensor:
        """闭式 KL(N(μq,σq²) ‖ N(μp,σp²))，逐元素均值（采样自由 ELBO 的 KL 项）。"""
        return 0.5 * torch.mean(
            logvar_p - logvar_q
            + (torch.exp(logvar_q) + (mu_q - mu_p) ** 2) / torch.exp(logvar_p)
            - 1.0)

    def step(self, x: torch.Tensor, h_prev: torch.Tensor, z_prev: torch.Tensor
             ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor,
                        torch.Tensor, torch.Tensor]:
        """单步滤波：x_t ∈ R^in → (h_t, μq, logvar_q, μp, logvar_p, x̂_{t+1})。

        z 以后验均值进入计算图（确定性点估计——Q-G00-14① 操作化）。
        """
        core = self._core()
        h = torch.tanh(core.cell_x(x) + core.cell_h(h_prev) + core.cell_z(z_prev) + core.cell_b)
        enc_hidden = torch.tanh(core.enc_in(torch.cat([x, h], dim=-1)))
        mu_q = core.enc_mu(enc_hidden)
        logvar_q = torch.clamp(core.enc_logvar(enc_hidden), -_LOGVAR_CLAMP, _LOGVAR_CLAMP)
        pri_hidden = torch.tanh(core.pri_in(h))
        mu_p = core.pri_mu(pri_hidden)
        logvar_p = torch.clamp(core.pri_logvar(pri_hidden), -_LOGVAR_CLAMP, _LOGVAR_CLAMP)
        z = mu_q
        x_pred = core.dec(torch.cat([h, z], dim=-1))
        return h, mu_q, logvar_q, mu_p, logvar_p, x_pred

    # ---------------------------------------------------------------- 序列
    def filter_state(self, xs: list[torch.Tensor]) -> tuple[torch.Tensor, torch.Tensor]:
        """在线滤波至末拍状态 (h, z)（逐拍摄入真实形成帧——部署语义）。"""
        if not xs:
            raise ValueError("filter_state requires >= 1 frame")
        h = torch.zeros(self.det_dim)
        z = torch.zeros(self.latent_dim)
        with torch.no_grad():
            for x in xs:
                h, mu_q, _lvq, _mu_p, _lvp, _pred = self.step(x, h, z)
                z = mu_q
        return h, z

    def filter_sequence(self, xs: list[torch.Tensor]) -> list[torch.Tensor]:
        """在线滤波：逐拍摄入真实形成帧，输出各拍对下一拍的预测 x̂_{t+1}。

        返回长度 = len(xs)（preds[t] = 给定 x_{≤t} 对 x_{t+1} 的预测；首拍预测
        基于零初始状态——前文缺席由状态初始化承载，末条 = 序列外推预测）；
        部署语义 = 常驻主体逐拍预测（评价协议在线滤波形式，stat plan 冻结承载）；
        推理路径 no_grad（预测张量不携带梯度——部署面与训练面分离）。
        """
        if len(xs) < 1:
            raise ValueError("filter_sequence requires >= 1 frame")
        h = torch.zeros(self.det_dim)
        z = torch.zeros(self.latent_dim)
        preds: list[torch.Tensor] = []
        with torch.no_grad():
            for x in xs:
                h, _mu_q, _lvq, _mu_p, _lvp, x_pred = self.step(x, h, z)
                z = _mu_q
                preds.append(x_pred.detach())
        return preds

    def imagine(self, h: torch.Tensor, z: torch.Tensor, steps: int) -> list[torch.Tensor]:
        """想象推演（prior 驱动自反馈；从滤波状态 (h, z) 出发，预测长度 = steps）。

        h=1 预测与 filter_sequence 同式（后验 z；即 x̂_{t+1} = dec(h_t, z_t)）；
        h≥2 潜变量取先验均值 μ_p(h)、递归输入取上拍预测 x̂（自反馈）——训练未
        直接监督的路径，质量由评价 horizon 曲线如实报告（stat plan 冻结承载）。
        """
        if steps < 1:
            raise ValueError("imagine steps must be >= 1")
        core = self._core()
        with torch.no_grad():
            preds: list[torch.Tensor] = []
            x_prev = core.dec(torch.cat([h, z], dim=-1))
            preds.append(x_prev)
            for _ in range(steps - 1):
                # h ← f(h, z_prev, x̂_prev)（递归输入 = 上拍预测——自反馈）；
                # z ← 先验均值 μ_p(h)（无观测——imagination 的 RSSM 标准形）
                h = torch.tanh(core.cell_x(x_prev) + core.cell_h(h)
                               + core.cell_z(z) + core.cell_b)
                z = core.pri_mu(torch.tanh(core.pri_in(h)))
                x_prev = core.dec(torch.cat([h, z], dim=-1))
                preds.append(x_prev)
        return preds

    # ---------------------------------------------------------------- 训练
    def train_on_sequence(self, xs: list[torch.Tensor], lr: float, epochs: int) -> list[float]:
        """全批量训练（采样自由 ELBO；无 minibatch 采样 RNG——Q-L13-20④）。

        损失 = 下一拍重构 MSE + KL(q‖p)（β=1 标准 ELBO 恒等）；返回逐 epoch 损失。
        """
        configure_deterministic_torch()
        if len(xs) < 3:
            raise ValueError("train_on_sequence requires >= 3 frames")
        optimizer = torch.optim.Adam(self._module.parameters(), lr=lr)
        losses: list[float] = []
        for _ in range(epochs):
            optimizer.zero_grad()
            h = torch.zeros(self.det_dim)
            z = torch.zeros(self.latent_dim)
            recon_acc = torch.zeros(())
            kl_acc = torch.zeros(())
            count = 0
            for t, x in enumerate(xs):
                h, mu_q, logvar_q, mu_p, logvar_p, x_pred = self.step(x, h, z)
                z = mu_q
                if t + 1 < len(xs):
                    recon_acc = recon_acc + torch.mean((x_pred - xs[t + 1]) ** 2)
                    kl_acc = kl_acc + self._kl_closed_form(mu_q, logvar_q, mu_p, logvar_p)
                    count += 1
            loss = recon_acc / count + kl_acc / count
            loss.backward()  # pyright: ignore[reportUnknownMemberType] - torch stub 边界
            optimizer.step()  # pyright: ignore[reportUnknownMemberType] - torch stub 边界
            losses.append(float(loss.detach()))
        return losses

    def posterior_parameters(self, x: torch.Tensor, h: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """摊销后验参数 (μ_q, logvar_q)（公开访问面——amortized 入口消费）。"""
        core = self._core()
        with torch.no_grad():
            enc_hidden = torch.tanh(core.enc_in(torch.cat([x, h], dim=-1)))
            return core.enc_mu(enc_hidden), core.enc_logvar(enc_hidden)
