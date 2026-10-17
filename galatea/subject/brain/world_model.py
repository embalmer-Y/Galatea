"""RSSM 式潜状态世界模型（Q-L04-12①；v1.2 训练过程修订——Q-L04-14）。

架构 = 确定性 recurrent 状态 h + 随机潜变量 z（对角高斯 q/p），小尺度 CPU 级：

    e_t = x_t − x̂_{t|t−1}                                        # 预测编码误差反馈
    h_t = tanh-core: GRUCell([x_t, e_t, z_{t-1}], h_{t-1})        # 确定性递归
    q(z_t) = N(μ_q([x_t, e_t, h_t]), σ_q²(·))                     # 摊销后验
    p(z_t) = N(μ_p(h_t), σ_p²(·))                                 # 学习先验
    x̂_{t+1} = W_dec·[h_t, z_t] + b_dec                           # 下一拍预测

**误差反馈（v1.2，Q-L04-14）**：递归核输入加入上拍预测残差 e_t——"惊讶度"
显式进入状态转移（HLD §15 预测误差最小化语义）。动机 = 研究单元误差解剖
（ADR-G-0032 §3）：观测流丢帧合并值使速率序列相位跳移，无误差反馈的递归核
需内部隐式计算残差才能重锁相位，训练段仅 3–7 个重锁样本不足以习得；显式
误差输入使合并值重锁成为一阶特征。imagination（无观测）中 e ≡ 0——无观测
即无惊讶，语义自洽。

**随机潜变量的确定性操作化**（给定权重确定性 Q-G00-14①；Q-L13-20④）：
训练目标 = 采样自由 ELBO——闭式 KL(q‖p) + 后验均值重构 MSE；z 以均值点估计
进入计算图，训练/推理零采样 RNG。β=1 即标准 ELBO 本身（恒等式非调节常数）。
logvar 夹持 ±10 = float32 溢出防护（工程护栏非语义参数）。

**训练过程（v1.2，Q-L04-14）**——研究单元 17 配置攻关的胜出组合（ADR-G-0032）：
1. 滑动窗口起点：epoch 轮换窗口起点 (0, 24, 48)（24 = 2× ADR-G-0030 §2 冻结
   动作脚本周期 12；起点集覆盖训练段三相位入口）——同一丢帧事件在三种相位
   上下文中出现，定向训练任意相位入口的锁相技能（误差解剖：可转化带 90–97%
   误差集中于相位失锁后的 rest 误预测）。
2. 内部验证早停：训练段末尾 val_window 拍不参与梯度的验证面（大误差事件
   留痕选择面），每 eval_every epochs 以原始域 held-out 同式比率筛选最优
   epoch 权重——对训练晚期灾难发散/欠拟合平台/过拟合三种失败模式统一免疫
   （仪表实证：recon 0.0106→3.29 的晚期爆炸被选择面截断）。
3. 全批量 Adam（无 minibatch 采样 RNG——确定性由构造成立；Q-L13-20③）。

转移语义继承 Q-L04-09：训练数据仅主体平面形成帧（禁信念内模拟隐藏真值过程）；
初始化 = 种子化 Generator 按推导式 Xavier σ（禁全局 RNG——Q-T11）；dec 锚序
保留研究配置初始化流的弃形绘制（v1.2 逐位锚，ADR-G-0032 §4.1）。
param_budget [1e4, 1e6] 构造期断言（profile 钉死）。
"""
from __future__ import annotations

import torch
from torch import nn

from galatea.subject.brain.error_stream import INPUT_DIM
from galatea.subject.brain.module import NeuralModule, configure_deterministic_torch
from galatea.subject.p4profile import P4AlphaBrainParams

_LOGVAR_CLAMP = 10.0     # float32 数值稳定性夹持（溢出防护非语义参数）
_WINDOW_STARTS = (0, 24, 48)   # 滑动窗口起点（24 = 2× 冻结脚本周期 12；Q-L04-14②）
_VAL_WINDOW_MAX = 48     # 内部验证窗（研究网格 {32,48,64} 实证最优；Q-L04-14③）
_EVAL_EVERY = 5          # 验证筛选周期（epochs/480 推导折中；Q-L04-14③）


def _xavier_sigma(shape: tuple[int, ...]) -> float:
    """Glorot/Xavier 初始化尺度（推导式 √(2/(fan_in+fan_out))——零自由常数；偏置恒零）。

    探针线性模型的 0.01σ 锚不能平移到门控递归（冒烟实证：速率 ±0.03 量级输入 ×
    0.01σ → 门控前激活 ~1e-3，600 epochs 学不动，ratio 0.83–1.40 留痕）——
    门控递归需与输入量级匹配的推导式初始化（DEV_SPEC §5.2 推导链合法源）。
    """
    if len(shape) == 2:
        fan_in, fan_out = shape[1], shape[0]
    else:
        fan_in = fan_out = shape[0]
    return (2.0 / (fan_in + fan_out)) ** 0.5


class _RSSMCore(nn.Module):
    """torch 模块核（参数容器；无业务语义）。

    递归核 = GRUCell（RSSM 标准形——DeepMind RSSM h_t = GRU(·)；门控加性路径
    解决长序列 BPTT 梯度消失——vanilla tanh-RNN 在 190 步序列上冒烟实测梯度
    消失收敛至平凡零解 ratio≈1.0，留痕）。递归输入 = [x, e, z]（e = 预测误差
    反馈，宽度 = input_dim）；后验编码器输入 = [x, e, h]。参数以种子化
    Generator 按推导式 Xavier σ 初始化（禁全局 RNG——Q-T11）。

    dec 锚序（v1.2 逐位锚，ADR-G-0032 §4.1）：先按弃形 output=input_dim+1
    绘制再绘实际 output=input_dim——逐位复现研究胜出配置的初始化流（同一
    Generator 绘制序不改，已验证数字可继承）。
    """

    def __init__(self, input_dim: int, latent_dim: int, det_dim: int,
                 generator: torch.Generator) -> None:
        super().__init__()
        hidden = latent_dim                       # 隐层宽 = latent_dim（冻结值复用）
        self.cell = nn.GRUCell(input_dim * 2 + latent_dim, det_dim)
        self.enc_in = nn.Linear(input_dim * 2 + det_dim, hidden)
        self.enc_mu = nn.Linear(hidden, latent_dim)
        self.enc_logvar = nn.Linear(hidden, latent_dim)
        self.pri_in = nn.Linear(det_dim, hidden)
        self.pri_mu = nn.Linear(hidden, latent_dim)
        self.pri_logvar = nn.Linear(hidden, latent_dim)
        self.dec = nn.Linear(det_dim + latent_dim, input_dim)
        with torch.no_grad():
            # RNG 绘制序 = 研究配置逐位锚：cell/enc_*/pri_* 权重 → 弃形 dec 锚
            # (input_dim+1) → 实际 dec（ biases 零化不消耗 RNG——Q-T11 序列保真）
            for name, param in self.named_parameters():
                if name.startswith("dec."):
                    continue
                if name.endswith("bias"):
                    param.zero_()
                else:
                    param.copy_(torch.randn(
                        param.shape, generator=generator) * _xavier_sigma(tuple(param.shape)))
            anchor = nn.Linear(det_dim + latent_dim, input_dim + 1)   # 弃形锚（即弃）
            anchor.weight.copy_(torch.randn(
                anchor.weight.shape, generator=generator) * _xavier_sigma(
                    tuple(anchor.weight.shape)))
            anchor.bias.zero_()
            self.dec.weight.copy_(torch.randn(
                self.dec.weight.shape, generator=generator) * _xavier_sigma(
                    tuple(self.dec.weight.shape)))
            self.dec.bias.zero_()


class RSSMWorldModel(NeuralModule):
    """潜状态序列世界模型（P4-α 脑核；Q-L04-12① + Q-L04-14 v1.2）。"""

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

    @property
    def _device(self) -> torch.device:
        """状态张量设备面（权重所在设备；CPU 路径恒 cpu——既有逐位锚不变）。"""
        return next(self.module.parameters()).device

    @staticmethod
    def _kl_closed_form(mu_q: torch.Tensor, logvar_q: torch.Tensor,
                        mu_p: torch.Tensor, logvar_p: torch.Tensor) -> torch.Tensor:
        """闭式 KL(N(μq,σq²) ‖ N(μp,σp²))，逐元素均值（采样自由 ELBO 的 KL 项）。"""
        return 0.5 * torch.mean(
            logvar_p - logvar_q
            + (torch.exp(logvar_q) + (mu_q - mu_p) ** 2) / torch.exp(logvar_p)
            - 1.0)

    def step(self, x: torch.Tensor, h_prev: torch.Tensor, z_prev: torch.Tensor,
             x_prev: torch.Tensor | None = None
             ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor,
                        torch.Tensor, torch.Tensor]:
        """单步滤波：x_t ∈ R^in → (h_t, μq, logvar_q, μp, logvar_p, x̂_{t+1})。

        x_prev = 上拍预测 x̂_{t|t−1}（缺省 None → 误差反馈 e = 0——序列首拍/
        无上下文查询语义；Q-L04-14①）。z 以后验均值进入计算图（确定性点估计
        ——Q-G00-14①）。
        """
        core = self._core()
        e = x - x_prev if x_prev is not None else torch.zeros_like(x)
        h = core.cell(torch.cat([x, e, z_prev], dim=-1), h_prev)
        enc_hidden = torch.tanh(core.enc_in(torch.cat([x, e, h], dim=-1)))
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
        dev = self._device
        h = torch.zeros(self.det_dim, device=dev)
        z = torch.zeros(self.latent_dim, device=dev)
        x_prev = torch.zeros(self.input_dim, device=dev)  # 首拍 e = x₁（研究配置逐位锚）
        with torch.no_grad():
            for x in xs:
                h, mu_q, _lvq, _mu_p, _lvp, pred = self.step(x, h, z, x_prev)
                z = mu_q
                x_prev = pred                # 误差反馈 = x − x̂_{t|t−1}（上拍预测）
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
        dev = self._device
        h = torch.zeros(self.det_dim, device=dev)
        z = torch.zeros(self.latent_dim, device=dev)
        x_prev = torch.zeros(self.input_dim, device=dev)  # 首拍 e = x₁（研究配置逐位锚）
        preds: list[torch.Tensor] = []
        with torch.no_grad():
            for x in xs:
                h, _mu_q, _lvq, _mu_p, _lvp, x_pred = self.step(x, h, z, x_prev)
                z = _mu_q
                x_prev = x_pred              # 误差反馈 = x − x̂_{t|t−1}（上拍预测）
                preds.append(x_pred.detach())
        return preds

    def imagine(self, h: torch.Tensor, z: torch.Tensor, steps: int) -> list[torch.Tensor]:
        """想象推演（prior 驱动自反馈；从滤波状态 (h, z) 出发，预测长度 = steps）。

        h=1 预测与 filter_sequence 同式（后验 z；即 x̂_{t+1} = dec(h_t, z_t)）；
        h≥2 潜变量取先验均值 μ_p(h)、递归输入取上拍预测 x̂（自反馈）——想象中
        无外部观测 → 误差反馈 e ≡ 0（无观测即无惊讶，Q-L04-14① 语义）。
        训练未直接监督的路径，质量由评价 horizon 曲线如实报告（stat plan 冻结承载）。
        """
        if steps < 1:
            raise ValueError("imagine steps must be >= 1")
        core = self._core()
        with torch.no_grad():
            preds: list[torch.Tensor] = []
            x_prev = core.dec(torch.cat([h, z], dim=-1))
            preds.append(x_prev)
            for _ in range(steps - 1):
                e = torch.zeros_like(x_prev)
                h = core.cell(torch.cat([x_prev, e, z], dim=-1), h)
                z = core.pri_mu(torch.tanh(core.pri_in(h)))
                x_prev = core.dec(torch.cat([h, z], dim=-1))
                preds.append(x_prev)
        return preds

    # ---------------------------------------------------------------- 训练
    def train_on_sequence(self, xs: list[torch.Tensor], lr: float, epochs: int,
                          target_dims: tuple[int, ...] | None = None,
                          val_context: tuple[float, float] | None = None) -> list[float]:
        """全批量训练（采样自由 ELBO；无 minibatch 采样 RNG——Q-L13-20④）。

        损失 = 目标维重构 MSE + KL(q‖p)（β=1 标准 ELBO 恒等）；target_dims =
        目标维子集（None = 全维）。

        **v1.2 训练过程（Q-L04-14；val_context = (μ, σ) 归一化统计量时启用）**：
        - 滑动窗口起点：epoch 轮换 _WINDOW_STARTS（三相位入口——锁相技能定向，
          ADR-G-0032 §3 误差解剖驱动）；
        - 内部验证早停：训练段末尾 min(_VAL_WINDOW_MAX, len//2) 拍为选择面，
          每 _EVAL_EVERY epochs 以原始域 held-out 同式比率筛选最优 epoch 权重
          并在返回前加载（录制/重放合同：weights_after = 选择后快照，重放
          同过程逐位复现同一选择）。
        val_context 缺省 None = 遗留全序列单窗训练（无选择面）。
        返回逐 epoch 损失（窗口起点轮换使各拍损失对应不同段——录制面如实承载）。
        """
        configure_deterministic_torch()
        if len(xs) < 3:
            raise ValueError("train_on_sequence requires >= 3 frames")
        if target_dims is not None and not target_dims:
            raise ValueError("target_dims empty（禁空目标——训练信号必须存在）")
        optimizer = torch.optim.Adam(self._module.parameters(), lr=lr)
        mu, sd = val_context if val_context is not None else (0.0, 0.0)
        val_window = min(_VAL_WINDOW_MAX, len(xs) // 2) if val_context is not None else 0
        starts = tuple(s for s in _WINDOW_STARTS if s < len(xs) // 2) or (0,)
        eval_every = _EVAL_EVERY if epochs >= 100 else 1
        losses: list[float] = []
        best: tuple[float, dict[str, torch.Tensor]] | None = None
        for ep in range(epochs):
            seg = xs[starts[ep % len(starts)]:]
            optimizer.zero_grad()
            dev = self._device
            h = torch.zeros(self.det_dim, device=dev)
            z = torch.zeros(self.latent_dim, device=dev)
            x_prev = torch.zeros(self.input_dim, device=dev)  # 首拍 e = x₁（逐位锚）
            recon_acc = torch.zeros((), device=dev)
            kl_acc = torch.zeros((), device=dev)
            count = 0
            for t, x in enumerate(seg):
                h, mu_q, logvar_q, mu_p, logvar_p, x_pred = self.step(x, h, z, x_prev)
                z = mu_q
                if t + 1 < len(seg):
                    if target_dims is None:
                        recon_acc = recon_acc + torch.mean((x_pred - seg[t + 1]) ** 2)
                    else:
                        pred_slice = x_pred[list(target_dims)]
                        target_slice = seg[t + 1][list(target_dims)]
                        recon_acc = recon_acc + torch.mean((pred_slice - target_slice) ** 2)
                    kl_acc = kl_acc + self._kl_closed_form(mu_q, logvar_q, mu_p, logvar_p)
                    count += 1
                x_prev = x_pred              # 误差反馈 = x − x̂_{t|t−1}（上拍预测）
            loss = recon_acc / count + kl_acc / count
            loss.backward()  # pyright: ignore[reportUnknownMemberType] - torch stub 边界
            optimizer.step()  # pyright: ignore[reportUnknownMemberType] - torch stub 边界
            losses.append(float(loss.detach()))
            if val_context is not None and ((ep + 1) % eval_every == 0 or ep == epochs - 1):
                ratio = self._internal_val_ratio(xs, mu, sd, val_window)
                if best is None or ratio < best[0]:
                    best = (ratio, {k: v.detach().clone()
                                    for k, v in self._module.state_dict().items()})
        if best is not None:
            self._module.load_state_dict(best[1])
        return losses

    def _internal_val_ratio(self, xs: list[torch.Tensor], mu: float, sd: float,
                            val_window: int) -> float:
        """内部验证比率（原始域 held-out 同式：filter 预测 vs 持续基线）。

        与 runs_p4._heldout_ratio 逐位同式——denorm(y) = μ + σ·y（z-score 的
        逆变换精确恢复原始速率），故判据只需 (μ, σ) 与归一化序列即可在训练面
        内复算（ADR-G-0032 §4.2）。
        """
        sel_split = len(xs) - 1 - val_window
        preds = self.filter_sequence(xs)
        ms: list[float] = []
        ps: list[float] = []
        for i in range(sel_split, len(xs) - 1):
            actual = mu + sd * float(xs[i + 1][0])
            pred = float(preds[i][0]) * sd + mu
            ms.append((pred - actual) ** 2)
            ps.append(actual ** 2)
        persist = sum(ps) / len(ps)
        return (sum(ms) / len(ms)) / persist

    def posterior_parameters(self, x: torch.Tensor, h: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """摊销后验参数 (μ_q, logvar_q)（公开访问面——amortized 入口消费）。

        单点查询无差分上下文 → e = 0（step 同语义，Q-L04-14①）。
        """
        core = self._core()
        with torch.no_grad():
            e = torch.zeros_like(x)
            enc_hidden = torch.tanh(core.enc_in(torch.cat([x, e, h], dim=-1)))
            return core.enc_mu(enc_hidden), core.enc_logvar(enc_hidden)
