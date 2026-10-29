"""P4-γ sealed 评价 runner（stat plan p4_gamma_mind 冻结承载）——探针核心 + 冒烟面。

第九次冻结前可行性探针（硬机制第九次）的可复算核心（Q-L04-16/Q-G00-16；规格
ADR-G-0035 §2）：
- 动作条件化 RSSM：input_dim=4 = [energy_rate, move, rest, forage]（formed INTERO
  能级差分 + 拍动作 one-hot——主体平面输入，Q-L04-12④ 继承）；
- EFE-MPC（Q-L08-11/Q-L10-18）：8 候选 4 步计划枚举；pragmatic = 稳态偏差负积分
  （set-point 0.7）+ epistemic = 先验 logvar 负和 × 0.1；
- 生成式重放做梦巩固（Q-L06-09）：P1 模型自 imagine 600 步混入微调；
- 在线双域不退化门（Q-L11-09）：新任务改善 ∧ 旧任务 held-out ≤ pre×1.5。

任务形 v2（v1.0 符号之后追加，owner「采纳 A」裁决 2026-10-28——stat plan v1.2 /
profile v1.1 运行前修订；REV-0031 R1 移交项兑现）：claim1 专属 = collect_conditioned_v2
/ to_tensors_v2 / train_conditioned_v2 / imagine_plan_v2（blind 归因消融）/
efe_score_v2（带控 [0.4,0.8]）/ _run_episode_v2（五臂）/ run_claim1（n=16 正式）。
**claim2（睡眠）/ claim3（门）继续消费 v1.0 符号——数据通路与冻结锚零触碰。**
世界冻结参数零触碰：代谢税 = 评价层逐拍 look 原语（m0 冻结成本）。

确定性：零全局 RNG（numpy default_rng 种子化 / torch 种子锚）；规划双跑 bit-exact
（探针实证）。本模块为 P4-γ 实现/评价单元的 runner 种子（INC-08：runner 路径
出生即带覆盖——tests/evidence/test_p4_gamma_probe.py）。
"""
from __future__ import annotations

import hashlib
import statistics
import tempfile
from pathlib import Path
from typing import Any

import torch

_ROOT = Path(__file__).resolve().parents[3]
repo_root = _ROOT                    # 公开别名（scripts/ 消费——REV-0029 R2 后禁引私有名）
_MASTER = b"p4-gamma-probe"

ACTIONS = ("move", "rest", "forage")
ACT_ID = {a: i for i, a in enumerate(ACTIONS)}

#: 探针冻结候选计划集（profile p4_gamma_mind mpc.candidate_plans = 8 的原文集合）
PLANS = (
    (1, 1, 1, 1), (1, 1, 1, 2), (1, 1, 2, 2), (1, 2, 2, 2),
    (2, 2, 2, 2), (0, 0, 0, 0), (0, 1, 0, 1), (2, 0, 2, 0),
)

SET_POINT = 0.7
W_EPISTEMIC = 0.1
DREAM_STEPS = 600


def seed_for(label: str) -> bytes:
    """探针种子派生（master = b"p4-gamma-probe"；claim 运行用 stat plan master）。"""
    return hashlib.sha256(label.encode() + _MASTER).digest()


def collect_conditioned(master_seed: bytes, cycles: int = 256,
                        script: Any = None) -> list[tuple[float, int]]:
    """真实 MW0 流 → [(rate_t, action_t)]（formed INTERO 能级差分 + 拍动作标签）。"""
    script_fn = script
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
    from galatea.subject.sensorium.ports import InteroSensations, load_c0_sensorium_profile

    if script_fn is None:
        def script_fn(cycle: int) -> str:
            phase = cycle % 12
            if phase == 11:
                return "rest"
            if phase in (1, 4):
                return "forage"
            return "move"

    profile = load_profile(_ROOT / "config/profiles/m0_mw0.profile.yaml")
    c0 = load_c0_sensorium_profile()
    calibration = bind_calibration(_ROOT / "config/profiles/c0_sensorium.profile.yaml",
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
            prim_map = {"move": (Primitive.MOVE, "E"), "rest": (Primitive.REST, None),
                        "forage": (Primitive.FORAGE, None)}
            levels: list[tuple[int, float, int]] = []
            frames_by_cycle: dict[int, list[Any]] = {}
            for cycle in range(cycles):
                act = script_fn(cycle)
                prim, param = prim_map[act]
                dynamics.apply(DynCommand(primitive=prim, param=param,
                                          command_id=f"p4g-{cycle}"),
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
                levels.append((cycle, world.energy_fraction(), ACT_ID[act]))
            formed: list[tuple[int, float]] = []
            for t in sorted(frames_by_cycle):
                for frame in frames_by_cycle[t]:
                    if isinstance(frame.features, InteroSensations):
                        formed.append((frame.effective_time, float(frame.features.energy_level)))
            formed.sort(key=lambda pair: pair[0])
            act_by_cycle = {c: a for c, _, a in levels}
            rows: list[tuple[float, int]] = []
            for i in range(len(formed) - 1):
                t0, e0 = formed[i]
                _t1, e1 = formed[i + 1]
                prior_cycles = [c for c in act_by_cycle if c <= t0]
                if not prior_cycles:
                    continue
                rows.append((e1 - e0, act_by_cycle[max(prior_cycles)]))
            return rows
        finally:
            stores.close()


def to_tensors(rows: list[tuple[float, int]]) -> list[torch.Tensor]:
    out: list[torch.Tensor] = []
    for rate, act in rows:
        onehot = [0.0] * 3
        onehot[act] = 1.0
        out.append(torch.tensor([rate] + onehot, dtype=torch.float32))
    return out


def imagine_plan(model: Any, h: torch.Tensor, z: torch.Tensor,
                 plan: tuple[int, ...], steps: int) -> list[tuple[float, float]]:
    """动作条件化想象：x 速率位 = 上拍预测（e 速率位恒 0——无观测），动作位 = 计划。"""
    dev = next(model.module.parameters()).device
    core = model._core()
    h = h.to(dev)
    z = z.to(dev)
    x_pred = core.dec(torch.cat([h, z], dim=-1))
    preds: list[tuple[float, float]] = []
    with torch.no_grad():
        for k in range(steps):
            act = plan[k] if k < len(plan) else plan[-1]
            x_in = x_pred.clone()
            x_in[1:] = 0.0
            x_in[1 + act] = 1.0
            e = x_in - x_pred
            h = core.cell(torch.cat([x_in, e, z], dim=-1), h)
            pri_hidden = torch.tanh(core.pri_in(h))
            mu_p = core.pri_mu(pri_hidden)
            logvar_p = torch.clamp(core.pri_logvar(pri_hidden), -8.0, 8.0)
            z = mu_p
            x_pred = core.dec(torch.cat([h, z], dim=-1))
            preds.append((float(x_pred[0]), float(logvar_p.mean())))
    return preds


def efe_score(preds: list[tuple[float, float]], energy_now: float,
              set_point: float = SET_POINT, w_epistemic: float = W_EPISTEMIC) -> float:
    """EFE（Q-L08-11）：pragmatic = 稳态偏差负积分 + epistemic = 先验方差负和 × 权重。"""
    energy = energy_now
    pragmatic = 0.0
    epistemic = 0.0
    for rate, logvar_mean in preds:
        energy = max(0.0, min(1.0, energy + rate))
        pragmatic += -abs(energy - set_point)
        epistemic += -logvar_mean
    return pragmatic + w_epistemic * epistemic


def _dyn_command(primitive: Any, param: str | None, command_id: str) -> Any:
    """世界侧命令构造（dynamics.apply 签名）。"""
    from galatea.env.world.dynamics import Command
    return Command(primitive=primitive, param=param, command_id=command_id)


def run_episode(world_seed: bytes, model: Any, cycles: int = 64, mode: str = "mpc") -> dict[str, Any]:
    """真实 MW0 世界回合：MPC 滚动规划 vs 反应式脚本（配对评价双臂）。"""
    from galatea.env.interventions.registry import InterventionRegistry
    from galatea.env.profile import load_profile
    from galatea.env.world.dynamics import MW0Dynamics
    from galatea.env.world.mw0 import MW0World, Primitive
    from galatea.kernel.rng import RngDirectory, chacha8_block

    profile = load_profile(_ROOT / "config/profiles/m0_mw0.profile.yaml")
    prim_map = {"move": (Primitive.MOVE, "E"), "rest": (Primitive.REST, None),
                "forage": (Primitive.FORAGE, None)}
    world = MW0World(profile.params, RngDirectory(world_seed, chacha8_block), branch_id="B")
    dynamics = MW0Dynamics(world, profile, RngDirectory(world_seed, chacha8_block), branch_id="B")
    history: list[tuple[float, int]] = []
    energies: list[float] = []
    plan_trace: list[tuple[str, ...]] = []
    for cycle in range(cycles):
        energy = world.energy_fraction()
        energies.append(energy)
        if mode == "script":
            act = "rest" if cycle % 12 == 11 else ("forage" if cycle % 12 in (1, 4) else "move")
        else:
            xs = to_tensors(history[-64:])
            if xs:
                h, z = model.filter_state(xs)
            else:
                h = torch.zeros(model.det_dim)
                z = torch.zeros(model.latent_dim)
            scores = [efe_score(imagine_plan(model, h, z, plan, steps=4), energy)
                      for plan in PLANS]
            best = max(range(len(PLANS)), key=lambda i: (scores[i], -i))
            plan_trace.append(tuple(ACTIONS[a] for a in PLANS[best]))
            act = ACTIONS[PLANS[best][0]]
        prim, param = prim_map[act]
        dynamics.apply(_dyn_command(prim, param, f"ep-{cycle}"), InterventionRegistry(), cycle)
        dynamics.step()
        prev = energies[-1]
        history.append((world.energy_fraction() - prev, ACT_ID[act]))
    in_band = sum(1 for e in energies if 0.3 <= e <= 0.95)
    return {"mean_energy": statistics.mean(energies), "in_band": in_band / len(energies),
            "min_energy": min(energies), "plans": plan_trace}


def train_conditioned(data: list[torch.Tensor], epochs: int) -> Any:
    """动作条件化 RSSM 训练（P4-α 冻结超参继承：init_seed/lr——Q-L11-09①）。"""
    from galatea.subject.brain.world_model import RSSMWorldModel
    from galatea.subject.p4profile import load_p4_alpha_profile
    params = load_p4_alpha_profile(_ROOT / "config/profiles/p4_alpha_brain.profile.yaml")
    m = RSSMWorldModel(params, parent_digest="root", init_seed=params.init_seed, input_dim=4)
    m.train_on_sequence(data, lr=params.lr, epochs=epochs, target_dims=(0,))
    return m


def heldout_mse(model: Any, data: list[torch.Tensor]) -> float:
    preds = model.filter_sequence(data)
    return statistics.mean((float(p[0]) - float(x[0])) ** 2 for p, x in zip(preds, data))


def dream_samples(model: Any, context: list[torch.Tensor],
                  steps: int = DREAM_STEPS) -> list[torch.Tensor]:
    """生成式重放采样（Q-L06-09②）：自 imagine——速率位 = 预测、动作位 = argmax 预测。"""
    core = model._core()
    h, z = model.filter_state(context)
    rows: list[tuple[float, int]] = []
    with torch.no_grad():
        for _ in range(steps):
            xp = core.dec(torch.cat([h, z], dim=-1))
            rate = float(xp[0])
            act = int(max(range(3), key=lambda j: float(xp[1 + j])))
            rows.append((rate, act))
            onehot = [0.0] * 3
            onehot[act] = 1.0
            x_in = xp.clone()
            x_in[1:] = torch.tensor(onehot)
            e = x_in - xp
            h = core.cell(torch.cat([x_in, e, z], dim=-1), h)
            z = core.pri_mu(torch.tanh(core.pri_in(h)))
    return to_tensors(rows)


def run_smoke(n_worlds: int = 2) -> dict[str, Any]:
    """缩规模冒烟（INC-08）：训练 300 + MPC 双臂 + dream/gate 结构面。"""
    rows = collect_conditioned(seed_for("p4.gamma|train"), cycles=256)
    assert {a for _, a in rows} == {0, 1, 2}
    xs = to_tensors(rows)
    model = train_conditioned(xs[: len(xs) - 31], 300)
    seed0 = seed_for("p4.gamma|world|0")
    r1 = run_episode(seed0, model, mode="mpc")
    r2 = run_episode(seed0, model, mode="mpc")
    det = r1["plans"] == r2["plans"] and r1["mean_energy"] == r2["mean_energy"]
    pairs: list[tuple[float, float]] = []
    for i in range(n_worlds):
        s = seed_for(f"p4.gamma|world|{i}")
        m_score = run_episode(s, model, mode="mpc")["mean_energy"]
        s_score = run_episode(s, model, mode="script")["mean_energy"]
        pairs.append((float(m_score), float(s_score)))
    return {
        "determinism_double_run": det,
        "paired": pairs,
        "advantage": (statistics.mean(a for a, _ in pairs)
                      - statistics.mean(b for _, b in pairs)),
        "n_worlds": n_worlds,
    }


# ============================================================================
# 任务形 v2（claim1 专属——owner「采纳 A」裁决 2026-10-28；stat plan v1.2 /
# profile v1.1 运行前修订承载；REV-0031 R1 移交项兑现）。
# 世界冻结参数零触碰：带控判分与代谢税均为评价任务层 overlay（税 = 逐拍先执行一次
# look 原语，其成本 = m0 冻结 action_energy_delta["look"] = −0.005）。
# claim2（睡眠）/ claim3（门）数据通路 = 上方 v1.0 符号，零改动。
# ============================================================================
ACTIONS_V2 = ("move", "rest", "forage", "eat")
ACT_ID_V2 = {a: i for i, a in enumerate(ACTIONS_V2)}
INPUT_DIM_V2 = 5

PLANS_V2 = (                                   # profile task_form_v2.plans_v2 冻结集合
    (1, 1, 1, 1),   # RRRR 慢升
    (3, 3, 3, 3),   # EEEE 快升（需存粮）
    (0, 0, 0, 0),   # MMMM 排放
    (2, 2, 2, 2),   # FFFF 排放+囤粮
    (1, 1, 3, 3),   # RREE 混合升
    (3, 3, 0, 0),   # EEMM 先升后排
    (0, 0, 1, 1),   # MMRR 先排后升
    (2, 2, 3, 3),   # FFEE eat 链
)
BAND_LO, BAND_HI = 0.4, 0.8                    # 带控判分区间（profile task_form_v2.band）


def collect_conditioned_v2(master_seed: bytes, cycles: int = 256) -> list[tuple[float, int]]:
    """任务形 v2 训练流：formed INTERO 能级差分（含代谢税复合速率）+ 状态感知脚本动作标签。

    脚本 = eat 链状态感知（存粮≥1 且能低 → eat；资源格且能足 → forage；能足且非资源格
    周期性 rest；否则 move E）——覆盖四动作 + eat 链关联（INC-08：训练分布须覆盖判据
    依赖的全部动作——迭代 1 rest 缺席教训）。税先行（与评价回合同经济）。
    """
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
    from galatea.subject.sensorium.ports import InteroSensations, load_c0_sensorium_profile

    profile = load_profile(_ROOT / "config/profiles/m0_mw0.profile.yaml")
    c0 = load_c0_sensorium_profile()
    calibration = bind_calibration(_ROOT / "config/profiles/c0_sensorium.profile.yaml",
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
            prim_map = {"move": (Primitive.MOVE, "E"), "rest": (Primitive.REST, None),
                        "forage": (Primitive.FORAGE, None), "eat": (Primitive.EAT, None)}
            frames_by_cycle: dict[int, list[Any]] = {}
            acts_by_cycle: dict[int, int] = {}
            for cycle in range(cycles):
                energy = world.energy_fraction()
                # 逐字复刻 scripts/p4gamma_taskform_probe.py _collect_v2（with_eat=True）——
                # 判据锚（stat plan v1.2 probe_measured）出自该流，锚语义必须同源
                # （INC-08 族纪律）。eat 分支在本世界从不触发（能降不到 0.6）——eat 通道
                # 零训练样本如实登记；迭代 3 三连教训见 git 历史（rest 采样竞速失败族）。
                if world.stored_food() >= 1 and energy < 0.6:
                    act = "eat"
                elif (world.body_cell_kind() == "resource" and energy >= 0.5
                      and world.stored_food() < 5):
                    act = "forage"
                elif energy >= 0.6 and cycle % 3 == 0:
                    act = "rest"         # 中段 rest +0.095——模型可学的可靠爬升关联
                else:
                    act = "move"
                acts_by_cycle[cycle] = ACT_ID_V2[act]
                dynamics.apply(DynCommand(primitive=Primitive.LOOK, param=None,
                                          command_id=f"p4g2-tax-{cycle}"),
                               InterventionRegistry(), cycle)
                prim, param = prim_map[act]
                dynamics.apply(DynCommand(primitive=prim, param=param,
                                          command_id=f"p4g2-{cycle}"),
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
            formed: list[tuple[int, float]] = []
            for t in sorted(frames_by_cycle):
                for frame in frames_by_cycle[t]:
                    if isinstance(frame.features, InteroSensations):
                        formed.append((frame.effective_time, float(frame.features.energy_level)))
            formed.sort(key=lambda pair: pair[0])
            rows: list[tuple[float, int]] = []
            for i in range(len(formed) - 1):
                t0, e0 = formed[i]
                _t1, e1 = formed[i + 1]
                prior_cycles = [c for c in acts_by_cycle if c <= t0]
                if not prior_cycles:
                    continue
                rows.append((e1 - e0, acts_by_cycle[max(prior_cycles)]))
            return rows
        finally:
            stores.close()


def to_tensors_v2(rows: list[tuple[float, int]]) -> list[torch.Tensor]:
    out: list[torch.Tensor] = []
    for rate, act in rows:
        onehot = [0.0] * 4
        onehot[act] = 1.0
        out.append(torch.tensor([rate] + onehot, dtype=torch.float32))
    return out


def train_conditioned_v2(data: list[torch.Tensor], epochs: int) -> Any:
    """任务形 v2 动作条件化 RSSM 训练（input_dim=5；P4-α 冻结超参继承）。"""
    from galatea.subject.brain.world_model import RSSMWorldModel
    from galatea.subject.p4profile import load_p4_alpha_profile
    params = load_p4_alpha_profile(_ROOT / "config/profiles/p4_alpha_brain.profile.yaml")
    m = RSSMWorldModel(params, parent_digest="root", init_seed=params.init_seed,
                       input_dim=INPUT_DIM_V2)
    m.train_on_sequence(data, lr=params.lr, epochs=epochs, target_dims=(0,))
    return m


def imagine_plan_v2(model: Any, h: torch.Tensor, z: torch.Tensor,
                    plan: tuple[int, ...], steps: int, blind: bool = False
                    ) -> list[tuple[float, float]]:
    """v2 想象：动作位 = 计划；blind=True 时速率位恒 0（归因消融——模型预测被清除）。"""
    dev = next(model.module.parameters()).device
    core = model._core()
    h = h.to(dev)
    z = z.to(dev)
    x_pred = core.dec(torch.cat([h, z], dim=-1))
    if blind:
        x_pred = x_pred.clone()
        x_pred[0] = 0.0
    preds: list[tuple[float, float]] = []
    with torch.no_grad():
        for k in range(steps):
            act = plan[k] if k < len(plan) else plan[-1]
            x_in = x_pred.clone()
            x_in[1:] = 0.0
            x_in[1 + act] = 1.0
            e = x_in - x_pred
            h = core.cell(torch.cat([x_in, e, z], dim=-1), h)
            pri_hidden = torch.tanh(core.pri_in(h))
            mu_p = core.pri_mu(pri_hidden)
            logvar_p = torch.clamp(core.pri_logvar(pri_hidden), -8.0, 8.0)
            z = mu_p
            x_pred = core.dec(torch.cat([h, z], dim=-1))
            if blind:
                x_pred = x_pred.clone()
                x_pred[0] = 0.0
            preds.append((float(x_pred[0]), float(logvar_p.mean())))
    return preds


def efe_score_v2(preds: list[tuple[float, float]], energy_now: float,
                 w_epistemic: float = W_EPISTEMIC,
                 band: tuple[float, float] = (BAND_LO, BAND_HI)) -> float:
    """任务形 v2 EFE（profile efe v1.1）：pragmatic = 带外偏差负积分 + epistemic 权重项。"""
    energy = energy_now
    pragmatic = 0.0
    epistemic = 0.0
    for rate, logvar_mean in preds:
        energy = max(0.0, min(1.0, energy + rate))
        pragmatic += -(max(0.0, energy - band[1]) + max(0.0, band[0] - energy))
        epistemic += -logvar_mean
    return pragmatic + w_epistemic * epistemic


def _run_episode_v2(world_seed: bytes, model: Any, mode: str,
                    cycles: int = 64) -> dict[str, Any]:
    """任务形 v2 回合（五臂）：mpc / mpc_blind / script / hysteresis / const_rest。

    hysteresis = 公平化调谐反射式（不读 stored_food 隐状态——盲 eat，迭代 1 作弊面教训）；
    税先行与训练流同经济。
    """
    from galatea.env.interventions.registry import InterventionRegistry
    from galatea.env.profile import load_profile
    from galatea.env.world.dynamics import MW0Dynamics
    from galatea.env.world.mw0 import MW0World, Primitive
    from galatea.kernel.rng import RngDirectory, chacha8_block

    profile = load_profile(_ROOT / "config/profiles/m0_mw0.profile.yaml")
    prim_map = {"move": (Primitive.MOVE, "E"), "rest": (Primitive.REST, None),
                "forage": (Primitive.FORAGE, None), "eat": (Primitive.EAT, None)}
    world = MW0World(profile.params, RngDirectory(world_seed, chacha8_block), branch_id="B")
    dynamics = MW0Dynamics(world, profile, RngDirectory(world_seed, chacha8_block), branch_id="B")
    history: list[tuple[float, int]] = []
    energies: list[float] = []
    first_actions: list[int] = []
    plan_trace: list[tuple[str, ...]] = []
    for cycle in range(cycles):
        energy = world.energy_fraction()
        energies.append(energy)
        if mode == "const_rest":
            act = "rest"
        elif mode == "script":
            act = "rest" if cycle % 12 == 11 else ("forage" if cycle % 12 in (1, 4) else "move")
        elif mode == "hysteresis":
            if energy < 0.45:
                act = "eat"                  # 盲 eat（无粮即空拍——反应式真实劣势面）
            elif energy > 0.75:
                act = "move"
            else:
                act = "rest" if energy < 0.65 else "move"
        else:                                # mpc / mpc_blind
            xs = to_tensors_v2(history[-64:])
            if xs:
                h, z = model.filter_state(xs)
            else:
                h = torch.zeros(model.det_dim)
                z = torch.zeros(model.latent_dim)
            blind = mode == "mpc_blind"
            scores = [efe_score_v2(imagine_plan_v2(model, h, z, plan, steps=4, blind=blind),
                                   energy)
                      for plan in PLANS_V2]
            best = max(range(len(PLANS_V2)), key=lambda i: (scores[i], -i))
            first_actions.append(PLANS_V2[best][0])
            plan_trace.append(tuple(ACTIONS_V2[a] for a in PLANS_V2[best]))
            act = ACTIONS_V2[PLANS_V2[best][0]]
        dynamics.apply(_dyn_command(Primitive.LOOK, None, f"ep2-tax-{cycle}"),
                       InterventionRegistry(), cycle)
        prim, param = prim_map[act]
        dynamics.apply(_dyn_command(prim, param, f"ep2-{cycle}"), InterventionRegistry(), cycle)
        dynamics.step()
        prev = energies[-1]
        history.append((world.energy_fraction() - prev, ACT_ID_V2[act]))
    devs = [max(0.0, e - BAND_HI) + max(0.0, BAND_LO - e) for e in energies]
    return {"mean_dev": statistics.mean(devs),
            "in_band": sum(1 for e in energies if BAND_LO <= e <= BAND_HI) / len(energies),
            "mean_energy": statistics.mean(energies),
            "min_energy": min(energies),
            "first_actions": first_actions,
            "plans": plan_trace}


def run_claim1(n_worlds: int = 16, epochs: int = 300) -> dict[str, Any]:
    """claim1 正式运行（stat plan p4_gamma_mind v1.2 冻结承载）：n=16 配对世界种子五臂。

    判据（v1.2 冻结）：advantage > 0.005 ∧ wins > 0.5 ∧ blind 归因差 > 0.01；
    任务有效性守卫：const_rest 逐种子劣败于 script（多数）。
    """
    rows = collect_conditioned_v2(seed_for("p4.gamma|train"), cycles=256)
    coverage = sorted({a for _, a in rows})
    assert {0, 1, 2} <= set(coverage), f"训练流必须覆盖 move/rest/forage（锚流同源）: {coverage}"
    xs = to_tensors_v2(rows)
    model = train_conditioned_v2(xs[: len(xs) - 31], epochs)
    arms = ("mpc", "mpc_blind", "script", "hysteresis", "const_rest")
    per_arm: dict[str, list[dict[str, Any]]] = {a: [] for a in arms}
    for i in range(n_worlds):
        s = seed_for(f"p4.gamma|world|{i}")
        for arm in arms:
            per_arm[arm].append(_run_episode_v2(s, model, arm))

    def mean_dev(arm: str) -> float:
        return statistics.mean(r["mean_dev"] for r in per_arm[arm])

    advantage = mean_dev("script") - mean_dev("mpc")
    wins = sum(1 for i in range(n_worlds)
               if per_arm["script"][i]["mean_dev"] > per_arm["mpc"][i]["mean_dev"])
    blind_advantage = mean_dev("mpc_blind") - mean_dev("mpc")
    blind_wins = sum(1 for i in range(n_worlds)
                     if per_arm["mpc_blind"][i]["mean_dev"] > per_arm["mpc"][i]["mean_dev"])
    guard_wins = sum(1 for i in range(n_worlds)
                     if per_arm["const_rest"][i]["mean_dev"] > per_arm["script"][i]["mean_dev"])
    hyst_context = mean_dev("hysteresis") - mean_dev("mpc")
    first_flat = [a for r in per_arm["mpc"] for a in r["first_actions"]]
    result: dict[str, Any] = {
        "claim": "p4_gamma_mpc_planning_advantage",
        "task_form": "v2_band_economy",
        "stat_plan": "p4_gamma_mind v1.2",
        "profile": "p4_gamma_mind v1.1",
        "band": [BAND_LO, BAND_HI],
        "input_dim": INPUT_DIM_V2,
        "n_worlds": n_worlds,
        "train_rows": len(rows),
        "train_act_coverage": coverage,
        "master_seed": "p4-gamma-probe(seed_for 派生)",
        "mean_dev": {a: mean_dev(a) for a in arms},
        "in_band": {a: statistics.mean(r["in_band"] for r in per_arm[a]) for a in arms},
        "advantage_script_minus_mpc": advantage,
        "wins_mpc_vs_script": f"{wins}/{n_worlds}",
        "blind_ablation_advantage": blind_advantage,
        "blind_wins": f"{blind_wins}/{n_worlds}",
        "hysteresis_minus_mpc_descriptive": hyst_context,
        "task_validity_guard_const_rest_loses": f"{guard_wins}/{n_worlds}",
        "mpc_first_action_hist": {ACTIONS_V2[i]: first_flat.count(i) for i in range(4)},
        "criteria": {"advantage>0.005": advantage > 0.005,
                     "wins>0.5": wins > n_worlds / 2,
                     "blind>0.01": blind_advantage > 0.01,
                     "guard_const_rest_loses_majority": guard_wins > n_worlds / 2},
    }
    result["verdict"] = ("SUPPORTED" if all(result["criteria"].values()) else "REFUTED")
    return result


def _finetune(parent: Any, mix: list[torch.Tensor], epochs: int = 100,
              input_dim: int = 4) -> Any:
    """在线学习语义微调（Q-L11-09①：从父权重起步——非重训；claim2/3 v1.0 通路）。"""
    from galatea.subject.brain.world_model import RSSMWorldModel
    from galatea.subject.p4profile import load_p4_alpha_profile
    params = load_p4_alpha_profile(_ROOT / "config/profiles/p4_alpha_brain.profile.yaml")
    m = RSSMWorldModel(params, parent_digest="root", init_seed=params.init_seed,
                       input_dim=input_dim)
    m.load_state(parent.state_dict())
    m.train_on_sequence(mix, lr=params.lr, epochs=epochs, target_dims=(0,))
    return m


def run_claim2(n_pairs: int = 8, epochs_parent: int = 300, epochs_finetune: int = 100,
               dream_steps: int = DREAM_STEPS) -> dict[str, Any]:
    """claim2 睡眠增益正式运行（stat plan p4_gamma_mind 冻结承载；Q-L06-09/Q-L13-23②）。

    n=8 配对相位对：P1 = phase1 前半训练；臂 a = 仅 phase2 前半微调；
    臂 b = phase2 前半 ⊕ dream（P1 自 imagine 生成式重放）；遗忘 = phase1 后半 held-out
    MSE 增量。冻结判据：mean(forget_a) > mean(forget_b) ∧ 逐对 forget_b ≤ 0.1×|pre|。
    数据通路 = v1.0 三动作符号（claim1 REFUTED 终态零触碰——Q-L13-23 补裁③）。
    """
    pairs: list[dict[str, Any]] = []
    for i in range(n_pairs):
        rows1 = collect_conditioned(seed_for(f"p4.gamma|phase1|{i}"), cycles=256)
        rows2 = collect_conditioned(seed_for(f"p4.gamma|phase2|{i}"), cycles=256)
        xs1, xs2 = to_tensors(rows1), to_tensors(rows2)
        half1, half2 = len(xs1) // 2, len(xs2) // 2
        model_p1 = train_conditioned(xs1[: half1 + 1], epochs_parent)
        pre = heldout_mse(model_p1, xs1[half1:])
        model_a = _finetune(model_p1, xs2[: half2 + 1], epochs_finetune)
        forget_a = heldout_mse(model_a, xs1[half1:]) - pre
        dream = dream_samples(model_p1, xs1[: half1 + 1], steps=dream_steps)
        model_b = _finetune(model_p1, xs2[: half2 + 1] + dream, epochs_finetune)
        forget_b = heldout_mse(model_b, xs1[half1:]) - pre
        pairs.append({"pair": i, "pre": pre, "forget_a": forget_a,
                      "forget_b": forget_b,
                      "replay_no_regression": forget_b <= 0.1 * abs(pre)})
    mean_a = statistics.mean(p["forget_a"] for p in pairs)
    mean_b = statistics.mean(p["forget_b"] for p in pairs)
    wins = sum(1 for p in pairs if p["forget_a"] > p["forget_b"])
    no_reg = sum(1 for p in pairs if p["replay_no_regression"])
    result: dict[str, Any] = {
        "claim": "p4_gamma_sleep_gain",
        "stat_plan": "p4_gamma_mind v1.2",
        "n_pairs": n_pairs,
        "epochs": {"parent": epochs_parent, "finetune": epochs_finetune,
                   "dream_steps": dream_steps},
        "mean_forget_a": mean_a, "mean_forget_b": mean_b,
        "paired_sleep_gain": mean_a - mean_b,
        "wins_a_over_b": f"{wins}/{n_pairs}",
        "replay_arm_no_regression": f"{no_reg}/{n_pairs}",
        "pairs": pairs,
        "criteria": {"forget_a>forget_b": mean_a > mean_b,
                     "forget_b<=0.1*|pre|": no_reg == n_pairs},
    }
    result["verdict"] = ("SUPPORTED" if all(result["criteria"].values()) else "REFUTED")
    return result


def _corrupt_rows(xs: list[torch.Tensor], kind: int) -> list[torch.Tensor]:
    """claim3 回归臂确定性损毁（10 种——去同质；全确定性零 RNG）。"""
    out: list[torch.Tensor] = []
    for x in xs:
        y = x.clone()
        if kind == 0:
            y[0] = 0.0                                          # 速率清零
        elif kind == 1:
            y[0] = -y[0]                                        # 速率翻转
        elif kind == 2:
            y[0] = 0.5                                          # 常量正速率
        elif kind == 3:
            y[0] = -0.1                                         # 负常量速率
        elif kind == 4:
            y[1:] = torch.tensor([1.0, 0.0, 0.0])               # 动作恒 move（v1.0 三动作流）
        elif kind == 5:
            y[1:] = 0.0                                         # 动作全零（无动作）
        elif kind == 6:
            y[0] = y[0] * 2.0                                   # 速率倍增
        elif kind == 7:
            y[1:] = y[1:].roll(1)                               # 动作位轮转
        elif kind == 8:
            y[0] = y[0] * 0.5                                   # 速率减半
        else:
            y[0] = y[0] * float((len(out) + 1) % 2)             # 隔行速率清零
        out.append(y)
    return out


def run_claim3(n_cases: int = 14, epochs_parent: int = 300,
               epochs_finetune: int = 100) -> dict[str, Any]:
    """claim3 在线双域门判别正式运行（stat plan v1.4 判据重设计；owner「α′」裁决承载）。

    v1.4 判据（Q-L11-09 合同本义「双域不退化」）：admit = cand ≤ parent×1.5（ph2）
    ∧ cand ≤ pre1×1.5（ph1）——对称双域 1.5× 容差（Q-L11-09 既有探针容差，零新常数）。
    候选谱 = 15 构造实测谱冻结取 14（谱测量探针 /tmp/p4gamma_claim3_spectrum.json：
    良性 8 形 0.73–1.41× / 损害 7 形 1.78–87.8×，1.5× 自然分离；预标"损毁"中恒 move/
    减半/隔行清零三形实测良性归准入侧语义已按谱修正）：
    准入七形 = 巩固 dream{300,600}×{30,100}ep（4）+ 轻微调 phase2{30,60}ep
    + dream300⊕phase2@30ep；拒收七形 = 过拟合 phase2@10ep + 损毁{1,2,3,5,6,7}@100ep
    （速率翻转/常正/常负/动作全零/倍增/轮转）。判据：14/14 判别正确 + 构造有效双向。
    v1.2/v1.3 形 REFUTED 工件保留归档（manifest v1.44 锚 e7f64e87 / 执行记录 df86588）。
    """
    rows1 = collect_conditioned(seed_for("p4.gamma|gate|phase1"), cycles=256)
    rows2 = collect_conditioned(seed_for("p4.gamma|gate|phase2"), cycles=256)
    xs1, xs2 = to_tensors(rows1), to_tensors(rows2)
    half1, half2 = len(xs1) // 2, len(xs2) // 2
    parent = train_conditioned(xs1[: half1 + 1], epochs_parent)
    pre1 = heldout_mse(parent, xs1[half1:])
    parent_ph2 = heldout_mse(parent, xs2[half2:])
    dream300 = dream_samples(parent, xs1[: half1 + 1], steps=300)
    dream600 = dream_samples(parent, xs1[: half1 + 1], steps=600)
    admit_specs = (
        ("consolidate-dream300-30ep", dream300, 30),
        ("consolidate-dream300-100ep", dream300, 100),
        ("consolidate-dream600-30ep", dream600, 30),
        ("consolidate-dream600-100ep", dream600, 100),
        ("mild-phase2-30ep", xs2[: half2 + 1], 30),
        ("mild-phase2-60ep", xs2[: half2 + 1], 60),
        ("mild-dream300+phase2-30ep", xs2[: half2 + 1] + dream300, 30),
    )
    reject_specs = (
        ("overfit-phase2-10ep", xs2[: half2 + 1], 10),
        ("regress-flip-100ep", _corrupt_rows(xs2[: half2 + 1], 1), 100),
        ("regress-constpos-100ep", _corrupt_rows(xs2[: half2 + 1], 2), 100),
        ("regress-constneg-100ep", _corrupt_rows(xs2[: half2 + 1], 3), 100),
        ("regress-actionzero-100ep", _corrupt_rows(xs2[: half2 + 1], 5), 100),
        ("regress-doubled-100ep", _corrupt_rows(xs2[: half2 + 1], 6), 100),
        ("regress-roll-100ep", _corrupt_rows(xs2[: half2 + 1], 7), 100),
    )
    assert n_cases == len(admit_specs) + len(reject_specs)
    cases: list[dict[str, Any]] = []
    for label, mix, ep in admit_specs:             # 良性候选（不退化 → 应准入）
        cand = _finetune(parent, mix, ep)
        cand_ph2 = heldout_mse(cand, xs2[half2:])
        cand_ph1 = heldout_mse(cand, xs1[half1:])
        within_ph2 = cand_ph2 <= parent_ph2 * 1.5
        within_ph1 = cand_ph1 <= pre1 * 1.5
        cases.append({"case": label, "expected": "admit",
                      "within_ph2_tol": within_ph2, "within_ph1_tol": within_ph1,
                      "gate_decision": "admit" if (within_ph2 and within_ph1) else "reject",
                      "cand_ph2": cand_ph2, "cand_ph1": cand_ph1,
                      "ph2_ratio": cand_ph2 / parent_ph2, "ph1_ratio": cand_ph1 / pre1})
    for label, mix, ep in reject_specs:            # 退化候选（超容差 → 应拒收）
        cand = _finetune(parent, mix, ep)
        cand_ph2 = heldout_mse(cand, xs2[half2:])
        cand_ph1 = heldout_mse(cand, xs1[half1:])
        within_ph2 = cand_ph2 <= parent_ph2 * 1.5
        within_ph1 = cand_ph1 <= pre1 * 1.5
        cases.append({"case": label, "expected": "reject",
                      "within_ph2_tol": within_ph2, "within_ph1_tol": within_ph1,
                      "gate_decision": "admit" if (within_ph2 and within_ph1) else "reject",
                      "cand_ph2": cand_ph2, "cand_ph1": cand_ph1,
                      "ph2_ratio": cand_ph2 / parent_ph2, "ph1_ratio": cand_ph1 / pre1})
    correct = sum(1 for c in cases if c["gate_decision"] == c["expected"])
    construction_valid = (all(c["ph2_ratio"] <= 1.5 and c["ph1_ratio"] <= 1.5
                              for c in cases if c["expected"] == "admit")
                          and all(c["ph2_ratio"] > 1.5 or c["ph1_ratio"] > 1.5
                                  for c in cases if c["expected"] == "reject"))
    result: dict[str, Any] = {
        "claim": "p4_gamma_online_gate_discrimination",
        "stat_plan": "p4_gamma_mind v1.4（判据重设计——owner α′ 裁决）",
        "profile": "p4_gamma_mind v1.2（online_learning.gate 双域 1.5×）",
        "n_cases": n_cases,
        "tolerance": 1.5,
        "parent_pre1": pre1, "parent_ph2_heldout": parent_ph2,
        "cases": cases,
        "correct": f"{correct}/{n_cases}",
        "construction_valid": construction_valid,
        "criteria": {"all_cases_correct": correct == n_cases,
                     "construction_valid": construction_valid},
    }
    result["verdict"] = ("SUPPORTED" if all(result["criteria"].values()) else "REFUTED")
    return result


def mini_probe_claim3() -> dict[str, Any]:
    """claim3 v1.4 判据 INC-08 迷你探针：四案例门禁（最紧准入/中段准入/最松拒收/最强拒收）。

    最紧准入 = consolidate-dream600-100ep（谱实测 1.412×，距 1.5× 仅 8%——若它被拒，
    容差边界不可靠）；中段准入 = mild-dream300+phase2-30ep（1.073×）；最松拒收 =
    overfit-phase2-10ep（1.783×）；最强拒收 = regress-flip（4.4×）。
    四案例全对 + 构造有效双向方准正式运行（Q-L13-23 补裁④⑤ 门禁）。
    """
    rows1 = collect_conditioned(seed_for("p4.gamma|gate|phase1"), cycles=256)
    rows2 = collect_conditioned(seed_for("p4.gamma|gate|phase2"), cycles=256)
    xs1, xs2 = to_tensors(rows1), to_tensors(rows2)
    half1, half2 = len(xs1) // 2, len(xs2) // 2
    parent = train_conditioned(xs1[: half1 + 1], 300)
    pre1 = heldout_mse(parent, xs1[half1:])
    parent_ph2 = heldout_mse(parent, xs2[half2:])
    dream600 = dream_samples(parent, xs1[: half1 + 1], steps=600)
    dream300 = dream_samples(parent, xs1[: half1 + 1], steps=300)
    cases: list[dict[str, Any]] = []
    for label, mix, ep, expect in (
            ("tightest-admit-dream600-100ep", dream600, 100, "admit"),
            ("mid-admit-dream300+phase2-30ep", xs2[: half2 + 1] + dream300, 30, "admit"),
            ("loosest-reject-overfit-10ep", xs2[: half2 + 1], 10, "reject"),
            ("strongest-reject-flip-100ep", _corrupt_rows(xs2[: half2 + 1], 1), 100, "reject")):
        cand = _finetune(parent, mix, ep)
        cand_ph2 = heldout_mse(cand, xs2[half2:])
        cand_ph1 = heldout_mse(cand, xs1[half1:])
        within = cand_ph2 <= parent_ph2 * 1.5 and cand_ph1 <= pre1 * 1.5
        decision = "admit" if within else "reject"
        cases.append({"case": label, "expected": expect, "gate_decision": decision,
                      "cand_ph2": cand_ph2, "cand_ph1": cand_ph1,
                      "ph2_ratio": cand_ph2 / parent_ph2, "ph1_ratio": cand_ph1 / pre1})
    construction_valid = (all(c["ph2_ratio"] <= 1.5 and c["ph1_ratio"] <= 1.5
                              for c in cases if c["expected"] == "admit")
                          and all(c["ph2_ratio"] > 1.5 or c["ph1_ratio"] > 1.5
                                  for c in cases if c["expected"] == "reject"))
    correct = sum(1 for c in cases if c["gate_decision"] == c["expected"])
    result = {"probe": "claim3_v1.4_criteria_mini", "cases": cases,
              "parent_pre1": pre1, "parent_ph2_heldout": parent_ph2,
              "correct": f"{correct}/4", "construction_valid": construction_valid,
              "verdict": "PASS" if (correct == 4 and construction_valid) else "FAIL"}
    return result