"""P4-γ sealed 评价 runner（stat plan p4_gamma_mind 冻结承载）——探针核心 + 冒烟面。

第九次冻结前可行性探针（硬机制第九次）的可复算核心（Q-L04-16/Q-G00-16；规格
ADR-G-0035 §2）：
- 动作条件化 RSSM：input_dim=4 = [energy_rate, move, rest, forage]（formed INTERO
  能级差分 + 拍动作 one-hot——主体平面输入，Q-L04-12④ 继承）；
- EFE-MPC（Q-L08-11/Q-L10-18）：8 候选 4 步计划枚举；pragmatic = 稳态偏差负积分
  （set-point 0.7）+ epistemic = 先验 logvar 负和 × 0.1；
- 生成式重放做梦巩固（Q-L06-09）：P1 模型自 imagine 600 步混入微调；
- 在线双域不退化门（Q-L11-09）：新任务改善 ∧ 旧任务 held-out ≤ pre×1.5。

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
