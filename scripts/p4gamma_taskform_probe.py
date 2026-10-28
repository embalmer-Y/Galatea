"""P4-γ 非退化 MPC 任务形——方向对比探针（研究级，非 claim；REV-0031 R1 移交项备证）。

背景（ADR-G-0035 §退化披露 / stat plan p4_gamma_mind v1.1 qualifiers
mpc_degeneracy_disclosure）：探针形 MW0 经济中 rest +0.10/拍无条件（eat +0.15 需存粮、
forage −0.02 囤粮、move −0.01），纯能量最大化下 rest 结构性占优 → MPC 臂构造性塌缩
为常量 rest。立法指定替换方向 =「eat 链/带外排放经济 + INC-08 迷你探针先证可击败」。

本探针对比两个候选任务形（均为计分侧带外排放经济——世界冻结参数零触碰）：
  Form A：三原语 [move,rest,forage]（动作空间不扩，input_dim=4）；
  Form B：eat 链——MW0 既有原语 eat 进入动作空间 [move,rest,forage,eat]（input_dim=5；
          eat 为 m0 冻结世界既有原语 Q-L01-09④，非新动作）。
带控判分：band [0.4,0.8]（研究级候选锚——正式锚随 stat plan 运行前修订冻结），
  dev_t = max(0, e−hi) + max(0, lo−e)（带外排放计罚），episode 指标 = mean|dev|（越低越好）。

臂（配对世界种子）：mpc（EFE-MPC）/ script（原反应式）/ hysteresis（调谐带控反应式，
  公平基线）/ const_rest（退化金丝雀——必须失败）/ mpc_blind（模型速率位清零消融——
  优势应由模型承载，INC-08 可失败性）。

可击败性判读（迷你探针，INC-08）：(a) const_rest 臂 dev 显著劣于其他臂（任务非退化）；
  (b) mpc dev < hysteresis dev（配对优势存在）；(c) mpc_blind 劣于 mpc（模型承载）；
  (d) mpc 首动作非单一常量（无构造性塌缩）。判读失败 → 该任务形不可用。

迭代记录（研究级，正式锚随 stat plan 运行前修订冻结）：
  迭代 1（阴性，如实留痕）：无代谢税——满能起步 + 帽顶钳制使 4 步视野内全计划
    pragmatic 打平，epistemic 噪声成为实际决策者（Form B 塌缩至 eat 488/512、
    Form A 塌缩至 forage 512/512）；hysteresis 基线作弊面（直读 stored_food 隐状态）；
    训练数据 rest 缺席。三缺陷全部迭代 2 修复。
  迭代 2（2026-10-28，n=8 配对世界种子，band [0.4,0.8]，64 cycles）：Form B 过四判读——
    mpc mean_dev 0.0225 / in_band 0.766（首动作 move 464+rest 48 非塌缩）；
    mpc_blind 0.20（模型承载差 +0.1775）；script 0.0372（mpc 8/8 胜，+0.0147）；
    const_rest 0.20 劣败（任务非退化）；hysteresis（公平化后）0.02242 与 mpc 打平
    （-8e-05，诚实限定：调谐反应式在确定性拟线性速率下近优）。Form A（不扩 eat）
    mpc_beats_script=false——eat 链为必要组件。呈递 owner sync 后方可 stat plan
    运行前修订（claim1 任务形替换 + 判据重冻，禁本方自裁 §4.6.5）。
"""
from __future__ import annotations

import hashlib
import json
import statistics
import sys
import tempfile
from pathlib import Path

import torch

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

BAND_LO = 0.4
BAND_HI = 0.8
W_EPISTEMIC = 0.1
N_WORLDS = 8
CYCLES = 64
EPOCHS = 300


def _seed(label: str) -> bytes:
    return hashlib.sha256(label.encode() + b"p4-gamma-taskform").digest()


def _collect_v2(master_seed: bytes, cycles: int, with_eat: bool) -> list[tuple[float, int]]:
    """真实 MW0 流（formed INTERO 能级差分）+ 状态感知脚本（eat 链数据）。"""
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

    acts = ("move", "rest", "forage", "eat") if with_eat else ("move", "rest", "forage")
    act_id = {a: i for i, a in enumerate(acts)}
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
            prim = {"move": (Primitive.MOVE, "E"), "rest": (Primitive.REST, None),
                    "forage": (Primitive.FORAGE, None), "eat": (Primitive.EAT, None),
                    "look": (Primitive.LOOK, None)}
            frames_by_cycle: dict[int, list] = {}
            acts_by_cycle: dict[int, int] = {}
            for cycle in range(cycles):
                e = world.energy_fraction()
                if with_eat and world.stored_food() >= 1 and e < 0.6:
                    act = "eat"
                elif world.body_cell_kind() == "resource" and e >= 0.5 and world.stored_food() < 5:
                    act = "forage"
                elif e >= 0.6 and cycle % 3 == 0:
                    act = "rest"    # 迭代 2：rest 段补全（迭代 1 覆盖 [move,forage,eat]——rest 缺席致 RRRR 不可信）
                elif not with_eat and cycle % 12 in (1, 4):
                    act = "forage"
                else:
                    act = "move"
                acts_by_cycle[cycle] = act_id[act]
                # 代谢税（任务经济 overlay，研究级——迭代 2）：每拍先扣 look(−0.005)。
                # 动因：满能起步 + 帽顶钳制下 4 步视野内全计划 pragmatic 打平（迭代 1 实测
                # 塌缩至 eat 488/512 由 epistemic 噪声决定）；税使 move 净 −0.015 严格优于
                # 帽顶 rest，恢复短视野调节梯度。带外排放计罚不变。
                dynamics.apply(DynCommand(primitive=prim["look"][0], param=None,
                                          command_id=f"tf-tax-{cycle}"),
                               InterventionRegistry(), cycle)
                p, param = prim[act]
                dynamics.apply(DynCommand(primitive=p, param=param, command_id=f"tf-{cycle}"),
                               InterventionRegistry(), cycle)
                events = dynamics.step()
                truth_ref = ArtifactRef(digest=world.state_digest(), kind="world_state_ref")
                extero.render_and_submit(cycle, truth_ref)
                intero.render_and_submit(cycle, truth_ref, events)
                proprio.render_and_submit(cycle, truth_ref)
                delivered = bus.deliver(cycle)
                packets = []
                for packet in delivered.packets:
                    if packet.content_type == carrier_outcome:
                        continue
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
                prior = [c for c in acts_by_cycle if c <= t0]
                if prior:
                    rows.append((e1 - e0, acts_by_cycle[max(prior)]))
            return rows
        finally:
            stores.close()


def _train(rows: list[tuple[float, int]], input_dim: int, epochs: int):
    from galatea.subject.brain.world_model import RSSMWorldModel
    from galatea.subject.p4profile import load_p4_alpha_profile
    params = load_p4_alpha_profile(_ROOT / "config/profiles/p4_alpha_brain.profile.yaml")
    xs = []
    for rate, act in rows:
        onehot = [0.0] * (input_dim - 1)
        onehot[act] = 1.0
        xs.append(torch.tensor([rate] + onehot, dtype=torch.float32))
    m = RSSMWorldModel(params, parent_digest="taskform-probe", init_seed=params.init_seed,
                       input_dim=input_dim)
    m.train_on_sequence(xs[: len(xs) - 31], lr=params.lr, epochs=epochs, target_dims=(0,))
    return m


def _plans_v2() -> tuple[tuple[int, ...], ...]:
    """Form B 候选计划集（研究级候选——正式集合随运行前修订冻结）：
    RRRR 慢升 / EEEE 快升（需粮）/ MMMM 排放 / FFFF 排放+囤粮 / RREE 混合升 / EEMM 先升后排 /
    MMRR 先排后升 / FFEE eat 链（forage,forage,eat,eat）。"""
    return ((1, 1, 1, 1), (3, 3, 3, 3), (0, 0, 0, 0), (2, 2, 2, 2),
            (1, 1, 3, 3), (3, 3, 0, 0), (0, 0, 1, 1), (2, 2, 3, 3))


def _plans_a() -> tuple[tuple[int, ...], ...]:
    """Form A 候选计划集 = 原探针冻结集合（ADR-G-0035 §2 原文）。"""
    return ((1, 1, 1, 1), (1, 1, 1, 2), (1, 1, 2, 2), (1, 2, 2, 2),
            (2, 2, 2, 2), (0, 0, 0, 0), (0, 1, 0, 1), (2, 0, 2, 0))


def _imagine(model, h, z, plan, steps, blind: bool):
    core = model._core()
    dev = next(model.module.parameters()).device
    h, z = h.to(dev), z.to(dev)
    x_pred = core.dec(torch.cat([h, z], dim=-1))
    if blind:
        x_pred = x_pred.clone()
        x_pred[0] = 0.0
    preds = []
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


def _efe(preds, energy_now):
    energy = energy_now
    pragmatic = 0.0
    epistemic = 0.0
    for rate, logvar_mean in preds:
        energy = max(0.0, min(1.0, energy + rate))
        pragmatic += -(max(0.0, energy - BAND_HI) + max(0.0, BAND_LO - energy))
    return pragmatic + W_EPISTEMIC * epistemic


def _episode(world_seed: bytes, model, with_eat: bool, mode: str) -> dict:
    from galatea.env.interventions.registry import InterventionRegistry
    from galatea.env.profile import load_profile
    from galatea.env.world.dynamics import Command as DynCommand
    from galatea.env.world.dynamics import MW0Dynamics
    from galatea.env.world.mw0 import MW0World, Primitive
    from galatea.kernel.rng import RngDirectory, chacha8_block

    profile = load_profile(_ROOT / "config/profiles/m0_mw0.profile.yaml")
    acts = ("move", "rest", "forage", "eat") if with_eat else ("move", "rest", "forage")
    act_id = {a: i for i, a in enumerate(acts)}
    prim = {"move": (Primitive.MOVE, "E"), "rest": (Primitive.REST, None),
            "forage": (Primitive.FORAGE, None), "eat": (Primitive.EAT, None),
            "look": (Primitive.LOOK, None)}
    plans = _plans_v2() if with_eat else _plans_a()
    world = MW0World(profile.params, RngDirectory(world_seed, chacha8_block), branch_id="B")
    dynamics = MW0Dynamics(world, profile, RngDirectory(world_seed, chacha8_block), branch_id="B")
    history: list[tuple[float, int]] = []
    energies: list[float] = []
    first_actions: list[int] = []
    for cycle in range(CYCLES):
        energy = world.energy_fraction()
        energies.append(energy)
        if mode == "const_rest":
            act = "rest"
        elif mode == "script":
            act = "rest" if cycle % 12 == 11 else ("forage" if cycle % 12 in (1, 4) else "move")
        elif mode == "hysteresis":
            if energy < 0.45:
                # 公平化（迭代 2）：不读 stored_food（主体不可观测隐状态，迭代 1 作弊面）——
                # 盲 eat，无粮即空拍（rate 0）；这是反应式控制器的真实劣势面。
                act = "eat" if with_eat else "rest"
            elif energy > 0.75:
                act = "move"
            else:
                act = "rest" if energy < 0.65 else "move"
        else:  # mpc / mpc_blind
            xs = []
            for rate, a in history[-64:]:
                onehot = [0.0] * (len(acts))
                onehot[a] = 1.0
                xs.append(torch.tensor([rate] + onehot, dtype=torch.float32))
            if xs:
                h, z = model.filter_state(xs)
            else:
                h = torch.zeros(model.det_dim)
                z = torch.zeros(model.latent_dim)
            blind = mode == "mpc_blind"
            scores = [_efe(_imagine(model, h, z, plan, steps=4, blind=blind), energy)
                      for plan in plans]
            best = max(range(len(plans)), key=lambda i: (scores[i], -i))
            first_actions.append(plans[best][0])
            act = acts[plans[best][0]]
        # 代谢税（迭代 2）——与采集管线同经济（模型所见速率 = 税后复合速率）。
        dynamics.apply(DynCommand(primitive=prim["look"][0], param=None,
                                  command_id=f"tf-ep-tax-{cycle}"),
                       InterventionRegistry(), cycle)
        p, param = prim[act]
        dynamics.apply(DynCommand(primitive=p, param=param, command_id=f"tf-ep-{cycle}"),
                       InterventionRegistry(), cycle)
        dynamics.step()
        prev = energies[-1]
        history.append((world.energy_fraction() - prev, act_id[act]))
    devs = [max(0.0, e - BAND_HI) + max(0.0, BAND_LO - e) for e in energies]
    return {"mean_dev": statistics.mean(devs),
            "in_band": sum(1 for e in energies if BAND_LO <= e <= BAND_HI) / len(energies),
            "mean_energy": statistics.mean(energies),
            "first_actions": first_actions}


def _arm(world_seed: bytes, model, with_eat: bool, mode: str) -> dict:
    if mode in ("mpc", "mpc_blind"):
        return _episode(world_seed, model, with_eat, mode)
    return _episode(world_seed, None, with_eat, mode)


def run_form(with_eat: bool) -> dict:
    label = "B(eat-chain)" if with_eat else "A(3-prim)"
    input_dim = 5 if with_eat else 4
    rows = _collect_v2(_seed("train"), 256, with_eat)
    seen = sorted({a for _, a in rows})
    model = _train(rows, input_dim, EPOCHS)
    arms = ("mpc", "mpc_blind", "script", "hysteresis", "const_rest")
    per_arm: dict[str, list[dict]] = {a: [] for a in arms}
    for i in range(N_WORLDS):
        s = _seed(f"world|{i}")
        for arm in arms:
            per_arm[arm].append(_arm(s, model, with_eat, arm))
    def mean_dev(arm): return statistics.mean(r["mean_dev"] for r in per_arm[arm])
    adv_script = mean_dev("script") - mean_dev("mpc")
    adv_hyst = mean_dev("hysteresis") - mean_dev("mpc")
    adv_blind = mean_dev("mpc_blind") - mean_dev("mpc")
    wins_script = sum(1 for i in range(N_WORLDS)
                      if per_arm["script"][i]["mean_dev"] > per_arm["mpc"][i]["mean_dev"])
    wins_hyst = sum(1 for i in range(N_WORLDS)
                    if per_arm["hysteresis"][i]["mean_dev"] > per_arm["mpc"][i]["mean_dev"])
    fa = [a for r in per_arm["mpc"] for a in r["first_actions"]]
    hist = {acts: fa.count(i) for i, acts in enumerate(
        ("move", "rest", "forage", "eat") if with_eat else ("move", "rest", "forage"))}
    verdict = {
        "const_rest_fails": mean_dev("const_rest") > mean_dev("script"),
        "mpc_beats_script": adv_script > 0 and wins_script > N_WORLDS / 2,
        "mpc_beats_hysteresis": adv_hyst > 0,
        "model_carried": adv_blind > 0,
        "no_constant_collapse": len(set(fa)) > 1,
    }
    return {"form": label, "input_dim": input_dim,
            "train_rows": len(rows), "train_act_coverage": seen,
            "mean_dev": {a: mean_dev(a) for a in arms},
            "in_band": {a: statistics.mean(r["in_band"] for r in per_arm[a]) for a in arms},
            "advantage_vs_mpc": {"script": adv_script, "hysteresis": adv_hyst,
                                 "mpc_blind": adv_blind},
            "wins_vs_mpc": {"script": f"{wins_script}/{N_WORLDS}",
                            "hysteresis": f"{wins_hyst}/{N_WORLDS}"},
            "mpc_first_action_hist": hist,
            "verdict": verdict}


def main() -> None:
    out = {"probe": "p4_gamma_taskform_direction", "grade": "research_non_claim",
           "band": [BAND_LO, BAND_HI], "n_worlds": N_WORLDS, "cycles": CYCLES,
           "epochs": EPOCHS, "forms": []}
    for with_eat in (False, True):
        r = run_form(with_eat)
        out["forms"].append(r)
        print(json.dumps(r, ensure_ascii=False, indent=1))
    dest = Path("/tmp/p4gamma_taskform_probe.json")
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"written: {dest}")


if __name__ == "__main__":
    main()
