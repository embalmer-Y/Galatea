"""P4-α 探针报告生成器（REV-0027 R5：探针报告生成器并入 P4-α 实现 runner）。

落位证据面（galatea/evidence/control/）的理由：生成器需 env 真实流
（MW0+ChannelBus+sensorium），W/O 隔离守卫禁主体平面 import env
（tests/env/test_leakage_env.py 机械强制）——"训练会话录制器"的 record/replay
面在 subject 平面（galatea/subject/brain/recorder.py），流采集 + 报告产出
在本模块（证据面 = 实验控制/评价域）。重算规格 = ADR-G-0030 §2 全量。
"""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import torch

from galatea.subject.brain.module import (
    aggregate_digest,
    configure_deterministic_torch,
    per_key_digests,
)
from galatea.subject.p4profile import P4AlphaBrainParams


def _collect_probe_stream() -> tuple[list[list[float]], list[float], str]:
    """ADR-G-0030 §2 层B 流：真实 MW0+ChannelBus+sensorium，256 cycles 恒向 E 脚本。

    与 tests/evidence/test_p4_alpha_probe.py 同规格（单一事实源 = ADR 规格；
    本函数为正式 runner 面，测试面保持独立回归）。
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
    from galatea.subject.sensorium.ports import (
        ExtLocalObsFeatures,
        InteroSensations,
        load_c0_sensorium_profile,
    )

    root = Path(__file__).resolve().parents[3]
    profile = load_profile(root / "config" / "profiles" / "m0_mw0.profile.yaml")
    c0 = load_c0_sensorium_profile()
    calibration = bind_calibration(root / "config" / "profiles" / "c0_sensorium.profile.yaml",
                                   c0.calibration_version)
    master_seed = b"p4-alpha-probe"               # Q-G00-15②（ADR-G-0030 §2 钉死）
    cycles = 256
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
            windows: dict[int, list[float]] = {}
            energies: dict[int, float] = {}
            stream_bytes = bytearray()
            for cycle in range(cycles):
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
                    if packet.content_type == carrier_outcome:
                        continue                    # OUTCOME 不入 sensorium（Q-G00-12①）
                    blob = registry.get(packet.payload_ref).blob
                    packets.append((packet, blob.decode("utf-8")))
                out = sensorium.process_cycle(cycle, packets)  # type: ignore[arg-type]
                for frame in out.frames:
                    if isinstance(frame.features, ExtLocalObsFeatures):
                        windows[frame.effective_time] = [
                            v for row in frame.features.window for v in row]
                    elif isinstance(frame.features, InteroSensations):
                        energies[frame.effective_time] = frame.features.energy_level
            for t in sorted(windows):
                stream_bytes += json.dumps(windows[t], sort_keys=True).encode("utf-8")
            stream_bytes += json.dumps([energies[t] for t in sorted(energies)],
                                       sort_keys=True).encode("utf-8")
            return ([windows[t] for t in sorted(windows)],
                    [energies[t] for t in sorted(energies)],
                    hashlib.sha256(bytes(stream_bytes)).hexdigest())
        finally:
            stores.close()


def verify_probe_stream_anchor(params: P4AlphaBrainParams) -> bool:
    """流 digest 锚核验（Q-G00-15②：流 digest 7d8aa887… 入 profile——跨会话数据身份恒定）。

    只跑流采集（不训练）——数据身份锚的轻量机械面。
    """
    _xs, _energies, stream_digest = _collect_probe_stream()
    return stream_digest == params.probe_stream_digest


def _probe_rate_dataset(energies: list[float], lags: int) -> tuple[torch.Tensor, torch.Tensor]:
    """速率递归数据集（探针同式：12 滞后速率，最新在前；差分平稳化）。"""
    rates = [energies[i] - energies[i - 1] for i in range(1, len(energies))]
    rows: list[list[float]] = []
    targets: list[float] = []
    for i in range(lags, len(rates) - 1):
        rows.append(list(reversed(rates[i - lags:i])))
        targets.append(rates[i + 1])
    return (torch.tensor(rows, dtype=torch.float32),
            torch.tensor(targets, dtype=torch.float32).unsqueeze(1))


def generate_probe_report(params: P4AlphaBrainParams,
                          out_path: Path | None = None) -> dict[str, object]:
    """探针报告生成器（REV-0027 R5 并入 runner；重算规格 = ADR-G-0030 §2 全量）。

    层A 机器面四检 + 层B 真实流学习会话（线性 next-rate 递归预测器——探针
    冻结任务形），全部判据可失败；报告 verdict=PASS 仅当全部判据通过。
    """
    configure_deterministic_torch()
    hard_mechanism_run = 7                        # 硬机制第七次执行（ADR-G-0030 §1）
    master_seed = b"p4-alpha-probe"
    init_seed = params.init_seed
    rate_lags = 12
    epochs = 600
    lr = 0.01
    held_out = 64

    xs_raw, energies, stream_digest = _collect_probe_stream()
    energy_range = [min(energies), max(energies)]
    x, y = _probe_rate_dataset(energies, rate_lags)
    n_train = len(x) - held_out
    x_train, y_train = x[:n_train], y[:n_train]
    x_hold, y_hold = x[n_train:], y[n_train:]
    persist_mse = float(torch.mean(y_hold ** 2))

    generator = torch.Generator().manual_seed(init_seed)
    model = torch.nn.Linear(rate_lags, 1)
    with torch.no_grad():
        model.weight.copy_(torch.randn(1, rate_lags, generator=generator) * 0.01)
        model.bias.zero_()
    digests_before = per_key_digests(model.state_dict())
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    losses: list[float] = []
    for _ in range(epochs):
        optimizer.zero_grad()
        loss = torch.mean((model(x_train) - y_train) ** 2)
        loss.backward()  # pyright: ignore[reportUnknownMemberType] - torch stub 边界
        optimizer.step()  # pyright: ignore[reportUnknownMemberType] - torch stub 边界
        losses.append(float(loss.detach()))
    digests_after = per_key_digests(model.state_dict())

    # 重放：同种子同数据 → 初始化逐位命中 + 末权重逐位恒等（训练可复算，宪法语义核心）
    generator_r = torch.Generator().manual_seed(init_seed)
    replay = torch.nn.Linear(rate_lags, 1)
    with torch.no_grad():
        replay.weight.copy_(torch.randn(1, rate_lags, generator=generator_r) * 0.01)
        replay.bias.zero_()
    replay_init_ok = (aggregate_digest(per_key_digests(replay.state_dict()))
                      == aggregate_digest(digests_before))
    optimizer_r = torch.optim.Adam(replay.parameters(), lr=lr)
    replay_loss_last = float("nan")
    for _ in range(epochs):
        optimizer_r.zero_grad()
        loss_r = torch.mean((replay(x_train) - y_train) ** 2)
        loss_r.backward()  # pyright: ignore[reportUnknownMemberType] - torch stub 边界
        optimizer_r.step()  # pyright: ignore[reportUnknownMemberType] - torch stub 边界
        replay_loss_last = float(loss_r.detach())
    replay_ok = (replay_init_ok
                 and per_key_digests(replay.state_dict()) == digests_after
                 and replay_loss_last == losses[-1])

    model.eval()
    with torch.no_grad():
        preds = model(x_hold)
        preds_again = model(x_hold)
    double_run_ok = preds.detach().numpy().tobytes() == preds_again.detach().numpy().tobytes()
    mse_model = float(torch.mean((preds - y_hold) ** 2))
    ratio = mse_model / persist_mse
    margin = params.heldout_margin_vs_persistence
    ablation_offset = float(torch.mean(torch.abs(preds)))
    loss_down = losses[-1] < losses[0]
    verdict = "PASS" if (loss_down and ratio < margin and double_run_ok
                         and replay_ok and ablation_offset > 1e-4) else "FAIL"

    report: dict[str, object] = {
        "ablation_offset_mean_abs_pred": ablation_offset,
        "energy_range": energy_range,
        "hard_mechanism_run": hard_mechanism_run,
        "held_out": held_out,
        "heldout_mse_model": mse_model,
        "heldout_mse_persist": persist_mse,
        "init_seed": init_seed,
        "loss_first": losses[0],
        "loss_last": losses[-1],
        "margin_threshold": margin,
        "master_seed_hex": master_seed.hex(),
        "probe": "p4_alpha_freeze_prerequisite",
        "rate_lags": rate_lags,
        "ratio": ratio,
        "stream_digest": stream_digest,
        "stream_windows": len(xs_raw),
        "torch_config": {
            "default_dtype": str(torch.get_default_dtype()),
            "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
            "num_threads": torch.get_num_threads(),
            "torch_version": torch.__version__,
        },
        "train_pairs": n_train,
        "verdict": verdict,
        "weights_after": digests_after,
        "weights_before": digests_before,
    }
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
    return report
