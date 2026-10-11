"""P4-α 冻结前可行性探针（硬机制第七次执行；Q-T02 激活）——永久回归测试。

层A（torch 机器面）：确定性配置生效 / 种子敏感性 / 冻结权重双跑 bit-exact / 权重篡改检出。
层B（真实数据流面）：真实 MW0+ChannelBus+sensorium 流（被动观测 + 评估侧脚本化动作驱动；
主体面仅 RECEIVED 形成帧——零真值坐标）→ 内感受能量变化率序列 → 线性 next-rate 递归预测器
全批量训练 → 学习会话录制/重放权重 bit-exact + held-out 显著优于持续基线 + 消融偏移可检出。

重算规格：ADR-G-0030 §探针规格（种子/脚本/窗口/超参/digest 式全成文，评审可独立重演）。
宪法语义（ADR-G-0029 §2）：给定权重的确定性——训练可复算（种子+数据 digest 锚定），
部署推理 bit-exact；本探针即该语义的机器面证明。
"""
import hashlib
import json
import tempfile
from pathlib import Path

import pytest
import torch

from galatea.env.channels.adapter import ChannelBus
from galatea.env.channels.extero import ExteroceptiveChannel
from galatea.env.channels.intero import InteroceptiveChannel
from galatea.env.channels.proprio import ProprioceptiveChannel
from galatea.env.interventions.registry import InterventionRegistry
from galatea.env.profile import load_profile
from galatea.env.world.dynamics import Command as DynCommand
from galatea.env.world.dynamics import MW0Dynamics
from galatea.env.world.mw0 import MW0World, Primitive
from galatea.kernel.clock import CycleClock
from galatea.kernel.packet import ArtifactRef
from galatea.kernel.registry import Registry
from galatea.kernel.rng import RngDirectory, chacha8_block
from galatea.kernel.state import Stores
from galatea.subject.sensorium.calibration import bind_calibration
from galatea.subject.sensorium.ingest import CARRIER_EXTERO, CARRIER_INTERO, CARRIER_PROPRIO
from galatea.subject.sensorium.ports import (
    ExtLocalObsFeatures,
    InteroSensations,
    load_c0_sensorium_profile,
)
from galatea.subject.sensorium.pipeline import SensoriumPipeline

_ROOT = Path(__file__).resolve().parents[2]
_PROFILE = load_profile(_ROOT / "config" / "profiles" / "m0_mw0.profile.yaml")
_C0 = load_c0_sensorium_profile()
_CALIBRATION = bind_calibration(
    _ROOT / "config" / "profiles" / "c0_sensorium.profile.yaml", _C0.calibration_version
)

#: 探针冻结常量（Q-G00-15 初值集：任意但先于结果钉死，全溯源 ADR-G-0030 §探针规格）
PROBE_MASTER_SEED = b"p4-alpha-probe"          # 流种子（Q-L13-12 同族）
PROBE_INIT_SEED = 20261011                     # 权重初始化种子
PROBE_CYCLES = 256                             # 流长度（= 一 regime 驻留窗，Q-L01-04）
PROBE_HELD_OUT = 64                            # held-out 尾窗（= T6 拍，Q-L00-01）
PROBE_RATE_LAGS = 12                           # 速率滞后窗 = 动作脚本周期（精确线性可递归阶）
PROBE_LR = 0.01                                # Adam 步长
PROBE_EPOCHS = 600
PROBE_WIN_DIM = 25                             # 5×5 外感受窗（Q-L01-01 冻结）
PROBE_MARGIN = 0.1                             # held-out 判据：model MSE < persist × 0.1（实测 0.008）
_CARRIER_OUTCOME = "channel.outcome.received.v1"


def _probe_torch_config() -> dict[str, object]:
    """层A 前置：给定权重确定性配置（Q-T02③ 的 P4 激活形态；禁全局 RNG——种子经
    Generator 显式注入，Q-T11 主体平面纪律在训练面的对应物）。"""
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(1)
    return {
        "torch_version": torch.__version__,
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "num_threads": torch.get_num_threads(),
        "default_dtype": str(torch.get_default_dtype()),
    }


def _digest_tensor(t: torch.Tensor) -> str:
    return hashlib.sha256(t.detach().contiguous().numpy().tobytes()).hexdigest()


def _digest_params(state: dict[str, torch.Tensor]) -> dict[str, str]:
    return {k: _digest_tensor(v) for k, v in sorted(state.items())}


def _collect_stream() -> tuple[list[list[float]], list[float], str]:
    """真实 MW0 流 → (外感受窗 25 维序列, 内感受 energy 序列, 流 digest)。

    动作脚本 = 评估侧确定性驱动（C1 判据 3 同族外源面——主体面无任何命令信号）：
    周期 12 = [move, forage, move, move, forage, move×6, rest]，恒向 E。
    主体数据 = 仅 RECEIVED 渲染窗/内感受形成帧（传感器形成面，非世界真值）。
    """
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        stores = Stores(root / "stores")
        try:
            registry = Registry(root / "registry", stores, CycleClock())
            world = MW0World(_PROFILE.params, RngDirectory(PROBE_MASTER_SEED, chacha8_block),
                             branch_id="B")
            dynamics = MW0Dynamics(world, _PROFILE, RngDirectory(PROBE_MASTER_SEED, chacha8_block),
                                   branch_id="B")
            bus = ChannelBus(_PROFILE.params, registry,
                             RngDirectory(PROBE_MASTER_SEED, chacha8_block),
                             branch_id="B", interventions=InterventionRegistry())
            extero = ExteroceptiveChannel(bus, world)
            intero = InteroceptiveChannel(bus, world)
            proprio = ProprioceptiveChannel(bus, world)
            time_basis = {
                CARRIER_EXTERO: int(_PROFILE.params.channel_delay_cycles["exteroceptive"]),
                CARRIER_INTERO: int(_PROFILE.params.channel_delay_cycles["interoceptive"]),
                CARRIER_PROPRIO: int(_PROFILE.params.channel_delay_cycles["proprioceptive"]),
            }
            sensorium = SensoriumPipeline(_C0, _CALIBRATION, time_basis)
            windows: dict[int, list[float]] = {}
            energies: dict[int, float] = {}
            stream_bytes = bytearray()
            for cycle in range(PROBE_CYCLES):
                phase = cycle % 12
                if phase == 11:
                    prim, param = Primitive.REST, None
                elif phase in (1, 4):
                    prim, param = Primitive.FORAGE, None
                else:
                    prim, param = Primitive.MOVE, "E"
                dynamics.apply(DynCommand(primitive=prim, param=param,
                                          command_id=f"probe-{cycle}"),
                               InterventionRegistry(), cycle)
                events = dynamics.step()
                truth_ref = ArtifactRef(digest=world.state_digest(), kind="world_state_ref")
                extero.render_and_submit(cycle, truth_ref)
                intero.render_and_submit(cycle, truth_ref, events)
                proprio.render_and_submit(cycle, truth_ref)
                delivered = bus.deliver(cycle)
                packets: list[tuple[object, str]] = []
                for packet in delivered.packets:
                    if packet.content_type == _CARRIER_OUTCOME:
                        continue    # OUTCOME 不入 sensorium（Q-G00-12①）
                    blob = registry.get(packet.payload_ref).blob
                    packets.append((packet, blob.decode("utf-8")))
                out = sensorium.process_cycle(cycle, packets)  # type: ignore[arg-type]
                for frame in out.frames:
                    if isinstance(frame.features, ExtLocalObsFeatures):
                        flat = [v for row in frame.features.window for v in row]
                        windows[frame.effective_time] = flat
                    elif isinstance(frame.features, InteroSensations):
                        energies[frame.effective_time] = frame.features.energy_level
            # 流 digest = 数据身份锚（Q-L13-20②）：窗矩阵逐行 JSON 字节 + energy 序列
            for t in sorted(windows):
                stream_bytes += json.dumps(windows[t], sort_keys=True).encode("utf-8")
            stream_bytes += json.dumps([energies[t] for t in sorted(energies)],
                                       sort_keys=True).encode("utf-8")
            xs = [windows[t] for t in sorted(windows)]
            es = [energies[t] for t in sorted(energies)]
            return xs, es, hashlib.sha256(bytes(stream_bytes)).hexdigest()
        finally:
            stores.close()


def _rate_dataset(energies: list[float]) -> tuple[torch.Tensor, torch.Tensor]:
    """速率递归数据集：输入 = 12 滞后速率（最新在前），目标 = 下一速率。

    差分平稳化（电平漂移不进入输入分布）；周期脚本 ⇒ 精确线性可递归（存在解）。
    速率 = 形成面派生差分（Q-L02-05⑤——subject-plane，非世界真值）。
    """
    rates = [energies[i] - energies[i - 1] for i in range(1, len(energies))]
    rows, targets = [], []
    for i in range(PROBE_RATE_LAGS, len(rates) - 1):
        rows.append(list(reversed(rates[i - PROBE_RATE_LAGS:i])))
        targets.append(rates[i + 1])
    x = torch.tensor(rows, dtype=torch.float32)
    y = torch.tensor(targets, dtype=torch.float32).unsqueeze(1)
    return x, y


def _make_model(in_dim: int, out_dim: int, seed: int) -> torch.nn.Linear:
    """线性预测器（种子化 Generator 构造——禁全局 RNG；小尺度初值 0.01σ）。"""
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(1)
    g = torch.Generator().manual_seed(seed)
    model = torch.nn.Linear(in_dim, out_dim)
    with torch.no_grad():
        model.weight.copy_(torch.randn(out_dim, in_dim, generator=g) * 0.01)
        model.bias.zero_()
    return model


def _train(model: torch.nn.Linear, x: torch.Tensor, y: torch.Tensor) -> list[float]:
    """全批量 Adam（无 minibatch 采样 RNG——训练确定性由构造成立；Q-L13-20③）。"""
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(1)
    opt = torch.optim.Adam(model.parameters(), lr=PROBE_LR)
    losses: list[float] = []
    for _ in range(PROBE_EPOCHS):
        opt.zero_grad()
        loss = torch.mean((model(x) - y) ** 2)
        loss.backward()
        opt.step()
        losses.append(float(loss.detach()))
    return losses


def test_layer_a_frozen_weight_determinism() -> None:
    """层A：确定性配置 + 种子敏感性 + 冻结权重双跑 bit-exact + 权重篡改检出。"""
    cfg = _probe_torch_config()
    assert cfg["deterministic_algorithms"] is True
    assert cfg["num_threads"] == 1
    assert cfg["default_dtype"] == "torch.float32"

    m1 = _make_model(PROBE_RATE_LAGS, 1, PROBE_INIT_SEED)
    m2 = _make_model(PROBE_RATE_LAGS, 1, PROBE_INIT_SEED)
    m3 = _make_model(PROBE_RATE_LAGS, 1, PROBE_INIT_SEED + 1)
    d1, d2, d3 = (
        _digest_params(m1.state_dict()), _digest_params(m2.state_dict()),
        _digest_params(m3.state_dict()),
    )
    assert d1 == d2, "同种子初始化必须逐位恒等"
    assert d1 != d3, "异种子初始化必须不同（种子敏感性——否则确定性断言空转）"

    x = torch.randn(8, PROBE_RATE_LAGS, generator=torch.Generator().manual_seed(42))
    m1.eval()
    y1 = m1(x)
    y1_again = m1(x)
    assert y1.detach().numpy().tobytes() == y1_again.detach().numpy().tobytes(), (
        "冻结权重同输入双跑必须 bit-exact"
    )

    with torch.no_grad():
        m3.weight.add_(1e-3)   # 篡改一个权重
    assert _digest_params(m3.state_dict()) != d1, "权重篡改必须被 digest 检出"


def test_layer_b_learning_session_record_replay() -> None:
    """层B：真实流 → 学习会话录制/重放 bit-exact + held-out 优于持续基线 + 消融偏移。"""
    xs_raw, energies, stream_digest = _collect_stream()
    assert len(xs_raw) >= PROBE_CYCLES - PROBE_HELD_OUT, (
        f"形成窗覆盖不足：{len(xs_raw)}"
    )
    for row in xs_raw:
        assert all(0.0 <= v <= 1.0 + 1e-6 for v in row), "窗值有界（渲染观测，非真值坐标）"
    assert 0.0 < min(energies) <= max(energies) <= 1.0, "energy 域 [0,1]"

    x, y = _rate_dataset(energies)
    n_train = len(x) - PROBE_HELD_OUT
    x_train, y_train = x[:n_train], y[:n_train]
    x_hold, y_hold = x[n_train:], y[n_train:]
    persist_mse = float(torch.mean(y_hold ** 2))   # 持续基线：预测下一速率 = 0（无变化）

    # —— 学习会话录制（Q-L13-20②）：种子 + 数据 digest + 权重前后 digest + 损失曲线 ——
    model = _make_model(PROBE_RATE_LAGS, 1, PROBE_INIT_SEED)
    weights_before = _digest_params(model.state_dict())
    losses = _train(model, x_train, y_train)
    session = {
        "master_seed": PROBE_MASTER_SEED.hex(),
        "init_seed": PROBE_INIT_SEED,
        "stream_digest": stream_digest,
        "weights_before": weights_before,
        "weights_after": _digest_params(model.state_dict()),
        "loss_first": losses[0],
        "loss_last": losses[-1],
        "lr": PROBE_LR,
        "epochs": PROBE_EPOCHS,
    }
    assert session["loss_last"] < session["loss_first"], "训练损失必须下降（学习发生）"

    # —— 重放：同录制种子 + 同数据 → 权重逐位恒等（训练可复算，宪法语义核心） ——
    replay_model = _make_model(PROBE_RATE_LAGS, 1, PROBE_INIT_SEED)
    assert _digest_params(replay_model.state_dict()) == weights_before, "重放初始化必须命中录制锚"
    replay_losses = _train(replay_model, x_train, y_train)
    assert _digest_params(replay_model.state_dict()) == session["weights_after"], (
        "重放训练末权重必须与录制逐位恒等"
    )
    assert replay_losses[-1] == losses[-1], "重放损失曲线必须逐位恒等"

    # —— held-out：模型预测显著优于持续基线（学习真实、可失败；实测比 ≈0.008） ——
    model.eval()
    with torch.no_grad():
        preds = model(x_hold)
        preds_again = model(x_hold)
    assert preds.detach().numpy().tobytes() == preds_again.detach().numpy().tobytes(), (
        "冻结推理双跑必须 bit-exact"
    )
    mse_model = float(torch.mean((preds - y_hold) ** 2))
    assert mse_model < persist_mse * PROBE_MARGIN, (
        f"held-out 必须优于持续基线×{PROBE_MARGIN}：model={mse_model:.8f} "
        f"persist={persist_mse:.8f}"
    )

    # —— 消融偏移（选择性）：模型输出与持续基线输出必须可检出地不同 ——
    offset = float(torch.mean(torch.abs(preds)))
    assert offset > 1e-4, f"消融偏移必须可检出：mean|pred−persist|={offset:.8f}"

    # —— 流 digest 非空（数据身份锚，Q-L13-20②） ——
    assert len(stream_digest) == 64 and stream_digest != "0" * 64
