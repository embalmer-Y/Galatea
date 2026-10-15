"""P4-α sealed 评价 runner（stat plan p4_alpha 冻结承载；顺延终止条款第八次执行）。

**评价任务 = 探针冻结任务形**（ADR-G-0030 §2 速率递归——判据锚 0.0083 的承载面，
like-for-like）：INTERO energy 序列（形成面）→ 速率 = 相邻差分 → RSSM（一维速率
输入，recurrence 承载滞后结构）预测下一速率；held-out = 末 64 对（探针协议）。
**表格基线 = 线性 12 滞后模型**（ADR-G-0030 §2 冻结形本尊）——Q-L04-12③"神经 vs
表格/持续基线的 held-out 配对比较"的直接承载。

**实现期发现链（冒烟诊断，全部留痕）**：
1. 统一误差流跳行会把跨 gap 差当一拍速率（比率 0.73 vs 锚 0.0083）→ 任务序列 =
   纯 INTERO 序列（探针逐位同式复现锚 0.0082583424，本机 0.0082583353 = 已登记
   torch 跨机漂移）；统一流保留为架构面（单元测试覆盖）。
2. vanilla tanh-RNN 190 步 BPTT 梯度消失 → GRUCell（RSSM 标准形）。
3. 全维目标被窗 25 维稀释 → 任务面以速率递归承载（探针任务同源）。
4. 0.01σ 线性锚不可平移门控递归 → Xavier 推导式初始化（DEV_SPEC §5.2 推导链）。
5. 探针 lr=0.01 对 38k 参数 GRU 过热（发散留痕）→ Adam 库规范默认 1e-3
   （profile v1.1 运行前修订）。
6. 输入/目标 z-score 标准化（训练段统计量派生——held-out 不用统计量防泄漏）。

确定性：cell 主种子 = sha256("p4.alpha|{i}" + master_seed_bytes)（stat plan
seed_derivation）；init = profile 探针锚 20261011 全 cell 固定（去除初始化方差，
like-for-like）；全程无全局 RNG。
"""
from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch

from galatea.subject.brain.recorder import record_training_session, replay_training_session
from galatea.subject.brain.world_model import RSSMWorldModel
from galatea.subject.p4profile import P4AlphaBrainParams, load_p4_alpha_profile
from galatea.subject.sensorium.ports import SensoryFrame

_ROOT = Path(__file__).resolve().parents[3]
_MASTER_SEED = b"p4-alpha-sealed"          # stat plan seed_derivation（Q-L13-12④ 任意先钉）
_LABEL = "p4.alpha"
_CYCLES = 256                              # = 一 regime 驻留窗（Q-L01-04；探针同款）
_HOLDOUT = 64                              # T6 拍（Q-L00-01；探针同款）
_RATE_LAGS = 12                            # 表格基线滞后窗 = 动作脚本周期（探针冻结）
_TABLE_LR = 0.01                           # 表格基线 lr（ADR-G-0030 §2 冻结形原值）
_TABLE_EPOCHS = 600
_HORIZONS = 8                              # rollout 深度冻结上界（Q-L04-01）
_REPO = Path(__file__).resolve().parents[3]
_P1_HOLDOUT = 16                           # p1 域描述性 held-out 尾（65 cycles 语料）


def cell_master_seed(index: int) -> bytes:
    """cell 主种子（世界流身份；stat plan trial_seed 同式 sha256 派生）。"""
    return hashlib.sha256(f"{_LABEL}|{index}".encode("utf-8") + _MASTER_SEED).digest()


def _median(values: tuple[float, ...]) -> float:
    """排序统计量中位数（REV-0028 R1：剔除场景下必须以 n_completed 取索引——
    62 元素列表按 n_cells=64 索引取 sorted[32] 曾致 descriptive 中位数失实 0.302
    vs 真值 0.189，五处文本传播，S1 教训）。"""
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        raise ValueError("median of empty sequence")
    mid = n // 2
    return ordered[mid] if n % 2 == 1 else (ordered[mid - 1] + ordered[mid]) / 2.0


# ---------------------------------------------------------------- 流采集
def collect_stream_vectors(master_seed: bytes, cycles: int | None = None
                           ) -> tuple[list[tuple[int, tuple[float, ...]]],
                                      list[tuple[int, float]], str, str]:
    """MW0 冻结流 → (统一误差流向量行, INTERO 任务序列, 统一流 digest, 任务 digest)。

    动作脚本 = 评估侧确定性驱动（主体面零命令信号——探针同款周期 12 恒向 E）。
    双面返回：统一误差流向量（架构面——基三模态合同，缺席拍跳过）+ INTERO
    energy 序列（任务面——判据锚 ADR-G-0030 §2 的速率递归以此序列承载，与探针
    _rate_dataset 逐位同式：统一流跳行会把跨 gap 差当一拍速率——发现 1 留痕）。
    """
    cycles = _CYCLES if cycles is None else cycles
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
    from galatea.subject.sensorium.pipeline import SensoriumPipeline
    from galatea.subject.sensorium.ports import (
        InteroSensations,
        load_c0_sensorium_profile,
    )

    profile = load_profile(_ROOT / "config" / "profiles" / "m0_mw0.profile.yaml")
    c0 = load_c0_sensorium_profile()
    calibration = bind_calibration(_ROOT / "config" / "profiles" / "c0_sensorium.profile.yaml",
                                   c0.calibration_version)
    carrier_outcome = "channel.outcome.received.v1"

    with tempfile.TemporaryDirectory() as td:
        stores = Stores(Path(td) / "stores")
        try:
            registry = Registry(Path(td) / "registry", stores, CycleClock())
            world = MW0World(profile.params, RngDirectory(master_seed, chacha8_block),
                             branch_id="B")
            dynamics = MW0Dynamics(world, profile, RngDirectory(master_seed, chacha8_block),
                                   branch_id="B")
            bus = ChannelBus(profile.params, registry, RngDirectory(master_seed, chacha8_block),
                             branch_id="B", interventions=InterventionRegistry())
            extero = ExteroceptiveChannel(bus, world)
            intero = InteroceptiveChannel(bus, world)
            proprio = ProprioceptiveChannel(bus, world)
            time_basis = {
                CARRIER_EXTERO: int(profile.params.channel_delay_cycles["exteroceptive"]),
                CARRIER_INTERO: int(profile.params.channel_delay_cycles["interoceptive"]),
                CARRIER_PROPRIO: int(profile.params.channel_delay_cycles["proprioceptive"]),
            }
            sensorium = SensoriumPipeline(c0, calibration, time_basis)
            frames_by_cycle: dict[int, list[SensoryFrame]] = {}
            for cycle in range(cycles):
                phase = cycle % 12
                if phase == 11:
                    prim, param = Primitive.REST, None
                elif phase in (1, 4):
                    prim, param = Primitive.FORAGE, None
                else:
                    prim, param = Primitive.MOVE, "E"
                dynamics.apply(DynCommand(primitive=prim, param=param,
                                          command_id=f"p4-{cycle}"),
                               InterventionRegistry(), cycle)
                events = dynamics.step()
                truth_ref = ArtifactRef(digest=world.state_digest(), kind="world_state_ref")
                extero.render_and_submit(cycle, truth_ref)
                intero.render_and_submit(cycle, truth_ref, events)
                proprio.render_and_submit(cycle, truth_ref)
                delivered = bus.deliver(cycle)
                packets: list[tuple[object, str]] = []
                for packet in delivered.packets:
                    if packet.content_type == carrier_outcome:
                        continue                    # OUTCOME 不入 sensorium（Q-G00-12①）
                    blob = registry.get(packet.payload_ref).blob
                    packets.append((packet, blob.decode("utf-8")))
                out = sensorium.process_cycle(cycle, packets)  # type: ignore[arg-type]
                for frame in out.frames:
                    frames_by_cycle.setdefault(frame.effective_time, []).append(frame)
            rows: list[tuple[int, tuple[float, ...]]] = []
            intero_series: list[tuple[int, float]] = []
            for t in sorted(frames_by_cycle):
                try:
                    rows.append(_build_stream_vector(frames_by_cycle[t]))
                except ValueError:
                    pass                            # 架构面合同拍照实跳过（任务面不受影响）
                for frame in frames_by_cycle[t]:
                    features = frame.features
                    if isinstance(features, InteroSensations):
                        intero_series.append((frame.effective_time,
                                              float(features.energy_level)))
            intero_series.sort(key=lambda pair: pair[0])
            stream_bytes = b"".join(
                json.dumps([t, list(v)], sort_keys=True).encode("utf-8") for t, v in rows)
            task_bytes = b"".join(
                json.dumps([t, e], sort_keys=True).encode("utf-8") for t, e in intero_series)
            return (rows, intero_series, hashlib.sha256(stream_bytes).hexdigest(),
                    hashlib.sha256(task_bytes).hexdigest())
        finally:
            stores.close()


def _build_stream_vector(frames: list[SensoryFrame]) -> tuple[int, tuple[float, ...]]:
    """委托 subject 平面统一误差流（架构面——单一事实源，合同在 subject/brain）。"""
    from galatea.subject.brain.error_stream import build_stream_vector
    return build_stream_vector(frames)


# ---------------------------------------------------------------- p1 语料域
def p1_rate_series() -> tuple[list[float], str]:
    """p1 sealed 语料 → (formed energy 速率序列, 任务 digest)（未改动 c0 形成面——Q-L01-10）。

    p1 语料仅含 INTERO 单模态帧（真实遥测合同三键）——session-2 双源义务
    （Q-L04-12②）以此真实速率序列承载（与 MW0 会话同一任务形）；判据不触及
    该域质量（描述性另报）。
    """
    from galatea.env.physio.bridge import CARRIER_INTERO_CONTENT_TYPE
    from galatea.env.physio.ports import load_p1_physio_profile
    from galatea.evidence.control.runs_p1 import load_corpus, packet_for, rebuild_deliveries
    from galatea.subject.sensorium.calibration import bind_calibration
    from galatea.subject.sensorium.ingest import CARRIER_EXTERO, CARRIER_INTERO, CARRIER_PROPRIO
    from galatea.subject.sensorium.pipeline import SensoriumPipeline
    from galatea.subject.sensorium.ports import (
        InteroSensations,
        load_c0_sensorium_profile,
    )

    profile = load_p1_physio_profile(_ROOT / "config/profiles/p1_physio.profile.yaml")
    corpus = load_corpus(_ROOT / "evidence" / "p1_physio_sealed" / "corpus.jsonl")
    if not corpus.stream_sha256_verified:
        raise ValueError("p1 sealed corpus digest verification failed")
    c0 = load_c0_sensorium_profile(_ROOT / "config/profiles/c0_sensorium.profile.yaml")
    pipeline = SensoriumPipeline(c0, bind_calibration(
        _ROOT / "config/profiles/c0_sensorium.profile.yaml", c0.calibration_version),
        {CARRIER_EXTERO: _m0_delay("exteroceptive"),
         CARRIER_INTERO: _m0_delay("interoceptive"),
         CARRIER_PROPRIO: _m0_delay("proprioceptive")})
    rebuilt = rebuild_deliveries(corpus, profile)
    levels: list[tuple[int, float]] = []
    for record_cycle, (payload_text, _digest) in enumerate(rebuilt):
        packet, text = packet_for(payload_text, record_cycle,
                                   CARRIER_INTERO_CONTENT_TYPE, "env.physio.bridge")
        out = pipeline.process_cycle(record_cycle, [(packet, text)])
        for frame in out.frames:
            if isinstance(frame.features, InteroSensations):
                levels.append((frame.effective_time, frame.features.energy_level))
    levels.sort(key=lambda pair: pair[0])
    rates = [levels[i][1] - levels[i - 1][1] for i in range(1, len(levels))]
    stream_bytes = b"".join(json.dumps(r, sort_keys=True).encode("utf-8") for r in rates)
    return rates, hashlib.sha256(stream_bytes).hexdigest()


def _m0_delay(name: str) -> int:
    import yaml
    m0 = yaml.safe_load((_ROOT / "config/profiles/m0_mw0.profile.yaml").read_text(encoding="utf-8"))
    return int(m0["channels"]["delay_cycles"][name])


# ---------------------------------------------------------------- 任务面
def task_rates(intero_series: list[tuple[int, float]]) -> list[float]:
    """速率 = INTERO 能量相邻差分（形成面派生差分 Q-L02-05⑤ 的任务承载形——探针同式）。"""
    es = [e for _t, e in intero_series]
    return [es[i] - es[i - 1] for i in range(1, len(es))]


def table_baseline_ratio(rates: list[float]) -> float:
    """线性 12 滞后表格基线 held-out 比率（ADR-G-0030 §2 冻结形原值——init 20261011/0.01/600）。"""
    lag = _RATE_LAGS
    xr = [list(reversed(rates[i - lag:i])) for i in range(lag, len(rates) - 1)]
    yr = [rates[i + 1] for i in range(lag, len(rates) - 1)]
    x = torch.tensor(xr, dtype=torch.float32)
    y = torch.tensor(yr, dtype=torch.float32).unsqueeze(1)
    n = len(x) - _HOLDOUT
    generator = torch.Generator().manual_seed(params_table_init_seed())
    model = torch.nn.Linear(lag, 1)
    with torch.no_grad():
        model.weight.copy_(torch.randn(1, lag, generator=generator) * 0.01)
        model.bias.zero_()
    optimizer = torch.optim.Adam(model.parameters(), lr=_TABLE_LR)
    for _ in range(_TABLE_EPOCHS):
        optimizer.zero_grad()
        loss = torch.mean((model(x[:n]) - y[:n]) ** 2)
        loss.backward()  # pyright: ignore[reportUnknownMemberType] - torch stub 边界
        optimizer.step()  # pyright: ignore[reportUnknownMemberType] - torch stub 边界
    with torch.no_grad():
        mse = float(torch.mean((model(x[n:]) - y[n:]) ** 2))
    persist = float(torch.mean(y[n:] ** 2))
    return mse / persist


def params_table_init_seed() -> int:
    """表格基线初始化种子 = 探针锚（ADR-G-0030 §2 冻结形——profile probe_anchors.init_seed）。"""
    return load_p4_alpha_profile(_ROOT / "config/profiles/p4_alpha_brain.profile.yaml").init_seed


def _zscore(rates: list[float], n_train: int) -> tuple[list[float], float, float]:
    """z-score（训练段统计量派生——held-out 不用统计量，防泄漏；发现 6）。"""
    train = rates[:n_train + 1]
    mu = sum(train) / len(train)
    var = sum((r - mu) ** 2 for r in train) / len(train)
    sd = var ** 0.5 if var > 0 else 1.0
    return [(r - mu) / sd for r in rates], mu, sd


def _predict_next_rates(model: RSSMWorldModel, norm_rates: list[float],
                        mu: float, sd: float) -> list[float]:
    """在线滤波逐拍预测下一速率（反标准化回原始域——train 统计量；误差反馈
    递归的 x_prev 逐拍线程——Q-L04-14①，与研究 harness filter_preds 逐位同式）。"""
    with torch.no_grad():
        h = torch.zeros(model.det_dim)
        z = torch.zeros(model.latent_dim)
        x_prev = torch.zeros(1)              # 首拍 e = x₁（研究配置逐位锚）
        preds: list[float] = []
        for r in norm_rates:
            x = torch.tensor([r], dtype=torch.float32)
            h, _mq, _lq, _mp, _lp, x_pred = model.step(x, h, z, x_prev)
            z = _mq
            x_prev = x_pred              # 误差反馈 = x − x̂_{t|t−1}（上拍预测）
            preds.append(float(x_pred[0]) * sd + mu)
    return preds


def _heldout_ratio(preds: list[float], rates: list[float], n_train: int) -> tuple[float, float]:
    """held-out 64 对（探针协议：目标 = rates[i+1]，i ≥ n_train；输入 = 真实速率上下文）。"""
    ms = [(preds[i] - rates[i + 1]) ** 2 for i in range(n_train, len(rates) - 1)]
    ps = [rates[i + 1] ** 2 for i in range(n_train, len(rates) - 1)]
    persist = sum(ps) / len(ps)
    return (sum(ms) / len(ms)) / persist, persist


def _horizon_ratios(model: RSSMWorldModel, norm_rates: list[float],
                    mu: float, sd: float, rates: list[float], n_train: int) -> dict[str, float]:
    """horizon 曲线（描述性——prediction_scales 交付物；h=1 = 滤波同式）。

    h≥2 = imagine 反馈链（先验均值潜变量）；比率含困难布局 cells 的不可约结构，
    如实报告非判据。
    """
    ratios: dict[str, float] = {}
    with torch.no_grad():
        h_state = torch.zeros(model.det_dim)
        z_state = torch.zeros(model.latent_dim)
        x_prev = torch.zeros(1)              # 首拍 e = x₁（研究配置逐位锚）
        states: list[tuple[torch.Tensor, torch.Tensor]] = []
        for r in norm_rates:
            x = torch.tensor([r], dtype=torch.float32)
            h_state, _mq, _lq, _mp, _lp, _pred = model.step(x, h_state, z_state, x_prev)
            z_state = _mq
            x_prev = _pred               # 误差反馈 = x − x̂_{t|t−1}（上拍预测）
            states.append((h_state.clone(), z_state.clone()))
    for horizon in range(1, _HORIZONS + 1):
        ms: list[float] = []
        ps: list[float] = []
        for i in range(n_train, len(rates) - horizon):
            st_h, st_z = states[i]
            imagined = model.imagine(st_h, st_z, steps=horizon)
            pred = float(imagined[horizon - 1][0]) * sd + mu
            actual = rates[i + horizon]
            ms.append((pred - actual) ** 2)
            ps.append(actual ** 2)
        denom = sum(ps) / len(ps) if ps else 0.0
        ratios[f"h{horizon}"] = (sum(ms) / len(ms)) / denom if denom > 0 else float("inf")
    return ratios


# ---------------------------------------------------------------- 会话链
@dataclass(frozen=True, slots=True)
class CellResult:
    """单 sealed cell 的学习会话链结果（评价判定器输入）。"""

    index: int
    task_digest: str
    unified_digest: str
    claim_record: dict[str, Any]                   # 模型 A（MW0 单域判据承载）录制
    session1_record: dict[str, Any]                # 模型 B p1 预训练会话（双域义务）
    session2_record: dict[str, Any]                # 模型 B MW0 会话（谱系链 session2.before==session1.after）
    replay_bit_exact: bool
    mw0_only_ratio: float                          # MW0 单域从零模型（v1.2 判据口径——探针 like-for-like）
    chain_ratio: float                             # 双域链模型比率（描述性——迁移干扰量化）
    table_ratio: float                             # 线性 12 滞后表格基线（ADR-G-0030 §2 冻结形）
    persist_mse: float
    rssm_mse: float
    horizon_ratios: dict[str, float]               # 描述性（prediction_scales 交付；h=1..8）
    param_count: int
    p1_heldout_ratio: float                        # 描述性：p1 域 held-out（非判据）
    train_mean: float
    train_std: float


def run_cell(index: int, params: P4AlphaBrainParams,
             p1_rates: list[float], p1_digest: str) -> CellResult:
    """单 cell：双域学习会话链 + held-out 评价（全部确定性）。"""
    master_seed = cell_master_seed(index)
    init_seed = params.init_seed                    # 探针锚全 cell 固定（like-for-like）
    _rows, intero_series, unified_digest, task_digest = collect_stream_vectors(master_seed)
    rates = task_rates(intero_series)
    n_train = len(rates) - _HOLDOUT
    if n_train < 2 * _HOLDOUT:
        raise ValueError(f"cell {index}: train segment too short ({n_train})")
    norm_rates, mu, sd = _zscore(rates, n_train)

    # —— 模型 A：MW0 单域从零（v1.2 判据承载——探针协议 like-for-like，Q-L04-12 补裁②）——
    model = RSSMWorldModel(params, parent_digest="root", init_seed=init_seed, input_dim=1)
    param_count = model.param_count()
    train_xs = [torch.tensor([r], dtype=torch.float32) for r in norm_rates[:n_train + 1]]
    digest_before_a = model.digest()
    losses_a = model.train_on_sequence(train_xs, lr=params.lr,
                                       epochs=params.epochs, target_dims=(0,),
                                       val_context=(mu, sd))
    session_a = record_training_session(master_seed, init_seed, task_digest, model,
                                        digest_before_a, losses_a, params)
    claim_record = _record_view(session_a)

    # 判据评价（MW0 单域模型末权重——v1.2 判据口径）
    preds = _predict_next_rates(model, norm_rates, mu, sd)
    mw0_only_ratio, persist_mse = _heldout_ratio(preds, rates, n_train)
    table_ratio = table_baseline_ratio(rates)
    horizons = _horizon_ratios(model, norm_rates, mu, sd, rates, n_train)

    # 重放判据（判据承载模型——同种子同数据 → 末权重逐位恒等；I1）
    def _retrain_a(module: Any) -> list[float]:
        assert isinstance(module, RSSMWorldModel)
        return module.train_on_sequence(train_xs, lr=params.lr,
                                        epochs=params.epochs, target_dims=(0,),
                                        val_context=(mu, sd))

    replay_ok = replay_training_session(
        session_a,
        rebuild=lambda: RSSMWorldModel(params, parent_digest="root",
                                       init_seed=init_seed, input_dim=1),
        retrain=_retrain_a,
    )

    # —— 模型 B：双域链（Q-L04-12② 义务承载——p1 预训练 → MW0；机械门 + 干扰描述性）——
    model_b = RSSMWorldModel(params, parent_digest="root", init_seed=init_seed, input_dim=1)
    norm_p1, mu1, sd1 = _zscore(p1_rates, len(p1_rates) - _P1_HOLDOUT)
    p1_xs = [torch.tensor([r], dtype=torch.float32) for r in norm_p1]
    digest_before_1 = model_b.digest()
    losses_1 = model_b.train_on_sequence(p1_xs, lr=params.lr,
                                         epochs=params.epochs, target_dims=(0,),
                                         val_context=(mu1, sd1))
    session1 = record_training_session(master_seed, init_seed, p1_digest, model_b,
                                       digest_before_1, losses_1, params)
    b1_record = _record_view(session1)
    digest_before_2 = model_b.digest()
    losses_2 = model_b.train_on_sequence(train_xs, lr=params.lr,
                                         epochs=params.epochs, target_dims=(0,),
                                         val_context=(mu, sd))
    session2 = record_training_session(master_seed, init_seed, task_digest, model_b,
                                       digest_before_2, losses_2, params)
    b2_record = _record_view(session2)
    chain_preds = _predict_next_rates(model_b, norm_rates, mu, sd)
    chain_ratio, _ = _heldout_ratio(chain_preds, rates, n_train)

    # p1 域 held-out（描述性——双域链模型）
    p1_preds = _predict_next_rates(model_b, norm_p1, mu1, sd1)
    p1_ratio, _ = _heldout_ratio(p1_preds, p1_rates, len(p1_rates) - _P1_HOLDOUT)

    return CellResult(
        index=index, task_digest=task_digest, unified_digest=unified_digest,
        claim_record=claim_record, session1_record=b1_record,
        session2_record=b2_record, replay_bit_exact=replay_ok,
        mw0_only_ratio=mw0_only_ratio, chain_ratio=chain_ratio,
        table_ratio=table_ratio, persist_mse=persist_mse,
        rssm_mse=mw0_only_ratio * persist_mse, horizon_ratios=horizons,
        param_count=param_count, p1_heldout_ratio=p1_ratio,
        train_mean=mu, train_std=sd,
    )


def _record_view(session: Any) -> dict[str, Any]:
    """TrainingSessionRecord → JSON 视图（工件落盘形）。"""
    return {
        "master_seed_hex": session.master_seed_hex,
        "init_seed": session.init_seed,
        "data_digest": session.data_digest,
        "weights_digest_before": session.weights_digest_before,
        "weights_digest_after": session.weights_digest_after,
        "loss_first": session.loss_first,
        "loss_last": session.loss_last,
        "optimizer": session.optimizer,
        "lr": session.lr,
        "epochs": session.epochs,
    }


def run_cell_guarded(index: int, params: P4AlphaBrainParams,
                     p1_rates: list[float], p1_digest: str
                     ) -> tuple[CellResult | None, str]:
    """run_cell 的剔除包装（stat plan v1.3：训练失稳 cell 全指标剔除并留痕——守卫不放宽）。"""
    from galatea.subject.brain.ports import TrainingSessionViolation

    try:
        return run_cell(index, params, p1_rates, p1_digest), ""
    except TrainingSessionViolation as broken:
        return None, f"cell {index}: training_session_violation: {broken}"


def run_smoke(cells: int = 2) -> list[CellResult]:
    """冒烟（stat plan 冻结前判据可达性诊断——运行前修订留痕先例 c1）。"""
    params = load_p4_alpha_profile(_ROOT / "config/profiles/p4_alpha_brain.profile.yaml")
    p1_rates, p1_digest = p1_rate_series()
    results: list[CellResult] = []
    for i in range(cells):
        cell, _reason = run_cell_guarded(i, params, p1_rates, p1_digest)
        if cell is not None:
            results.append(cell)
    return results


# ---------------------------------------------------------------- 首评编排
def run_p4_first_evaluation(root: Path | None = None, out_dir: Path | None = None,
                            n_cells: int = 64,
                            leakage_free_override: bool | None = None) -> dict[str, Any]:
    """首评 R-p4-brain-001：64 sealed cells + 三 claim 判定 + Holm 复合；工件落盘。"""
    import json as _json

    root = root or _REPO
    out_dir = out_dir or root / "evidence" / "p4_alpha_brain_first_evaluation"
    stat_plan_ref = "config/evidence/stat_plans/p4_alpha.yaml"
    params = load_p4_alpha_profile(root / "config/profiles/p4_alpha_brain.profile.yaml")
    p1_rates, p1_digest = p1_rate_series()

    cells: list[CellResult] = []
    exclusions: list[str] = []
    for i in range(n_cells):
        cell, reason = run_cell_guarded(i, params, p1_rates, p1_digest)
        if cell is None:
            exclusions.append(reason)               # stat plan v1.3 剔除留痕
        else:
            cells.append(cell)
    n_completed = len(cells)
    mw0_only_ratios = tuple(c.mw0_only_ratio for c in cells)
    chain_ratios = tuple(c.chain_ratio for c in cells)
    table_ratios = tuple(c.table_ratio for c in cells)

    from galatea.evidence.evaluator.evaluate_p4 import (
        evaluate_p4_composite,
        evaluate_p4_dual_domain_gate,
        evaluate_p4_margin_median,
        evaluate_p4_replay_gate,
    )

    margin = evaluate_p4_margin_median(
        "R-p4-brain-margin", stat_plan_ref, mw0_only_ratios,
        params.heldout_margin_vs_persistence)
    dual = evaluate_p4_dual_domain_gate(
        "R-p4-brain-dualdomain", stat_plan_ref,
        tuple(c.session2_record["weights_digest_before"]
              == c.session1_record["weights_digest_after"] for c in cells),
        tuple(len(c.session1_record) == 10 and len(c.session2_record) == 10
              for c in cells))
    replay = evaluate_p4_replay_gate(
        "R-p4-brain-replay", stat_plan_ref,
        tuple(c.replay_bit_exact for c in cells))
    if leakage_free_override is None:
        from galatea.evidence.evaluator.leakage import load_tree_sources, run_leakage_suite
        leakage_free = run_leakage_suite(load_tree_sources(root)).leakage_free
    else:
        leakage_free = leakage_free_override
    composite = evaluate_p4_composite(
        "R-p4-brain-001", stat_plan_ref, margin, dual, replay,
        leakage_free=leakage_free)

    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "result_id": composite.result_id,
        "stat_plan_ref": stat_plan_ref,
        "profile": "p4_alpha_brain@v1.1",
        "stat_plan_version": "v1.3",
        "n_cells": n_cells,
        "n_completed": n_completed,
        "exclusions": exclusions,
        "claims": {
            "p4_alpha_heldout_vs_persistence": {
                "verdict": margin.verdict.value, "p": margin.p_or_bayes,
                "effect": margin.effect_size, "detail": margin.data_refs,
            },
            "p4_alpha_dual_domain_training_delivered": {
                "verdict": dual.verdict.value, "p": dual.p_or_bayes,
                "effect": dual.effect_size,
            },
            "p4_alpha_training_replay_bit_exact": {
                "verdict": replay.verdict.value, "p": replay.p_or_bayes,
                "effect": replay.effect_size,
            },
        },
        "descriptive": {
            "table_baseline_pairing": {
                "role": "Q-L04-12③ 对照基线语境工件（非门判据——v1.2 立法）",
                "n_completed": n_completed,
                "rssm_median": _median(mw0_only_ratios),
                "table_median": _median(table_ratios),
                "chain_median": _median(chain_ratios),
                "rssm_beats_table": sum(1 for r, s in zip(mw0_only_ratios, table_ratios) if r < s),
            },
        },
        "cells": [
            {
                "index": c.index, "task_digest": c.task_digest,
                "mw0_only_ratio": c.mw0_only_ratio, "chain_ratio": c.chain_ratio,
                "table_ratio": c.table_ratio,
                "persist_mse": c.persist_mse, "rssm_mse": c.rssm_mse,
                "replay_bit_exact": c.replay_bit_exact,
                "horizon_ratios": c.horizon_ratios,
                "p1_heldout_ratio": c.p1_heldout_ratio,
                "param_count": c.param_count,
                "session1": c.session1_record, "session2": c.session2_record,
            } for c in cells
        ],
        "composite": {"verdict": composite.verdict.value, "p": composite.p_or_bayes,
                      "effect": composite.effect_size,
                      "refutations": list(composite.refutations)},
        "leakage_free": leakage_free,
        "i1_match": bool(replay.recompute_ok
                         and replay.verdict.value == "SUPPORTED"),
    }
    (out_dir / "R-p4-brain-001.json").write_text(
        _json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for claim_result in (margin, dual, replay):
        (out_dir / f"{claim_result.result_id}.json").write_text(
            _json.dumps({
                "result_id": claim_result.result_id,
                "hypothesis_refs": list(claim_result.hypothesis_refs),
                "stat_plan_ref": claim_result.stat_plan_ref,
                "estimand": claim_result.estimand,
                "effect_size": claim_result.effect_size,
                "ci": ({"lower": claim_result.ci.lower, "upper": claim_result.ci.upper,
                        "level": claim_result.ci.level} if claim_result.ci is not None
                       else None),
                "p_or_bayes": claim_result.p_or_bayes,
                "verdict": claim_result.verdict.value,
                "refutations": list(claim_result.refutations),
                "data_refs": list(claim_result.data_refs),
                "recompute_ok": claim_result.recompute_ok,
            }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"composite": composite, "margin": margin, "dual": dual,
            "replay": replay, "leakage_free": leakage_free, "out_dir": out_dir}
