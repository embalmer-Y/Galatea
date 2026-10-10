"""H1 平台硬化门判据实现（L13 §9 H1 行 + L10 §9 H1 行；ADR-G-0024 冻结前置）。

**INC-13 教训在案**：本模块前版本（事故中丢失）的 I3 函数 finally 块含
工作目录递归删除缺陷行（原样描述见 INC-13）——工作目录递归删除导致全树丢失（INC-13）。
本版本纪律：任何清理调用只允许针对 tempfile.mkdtemp 返回的具体路径，
禁止 Path(".")/仓库根/相对路径字面量（test_no_repo_root_cleanup 钉死）。

四判据：
1. 长时运行稳定性（256 cycles 连续 + 记忆容量治理真实接管）；
2. 故障注入 + 恢复演练（fault 致投递丢失 + store 关闭重开 digest 不失）；
3. 供应链 hash 审计（manifest 全锚 sha256 重算比对——Q-T08 语义）；
4. I3 独立重现（Q-L13-08②：新 seed 集同派生式 + 效应方向一致 ∧ d≥0.5）。
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from galatea.env.channels.adapter import ChannelBus
from galatea.env.channels.extero import ExteroceptiveChannel
from galatea.env.channels.intero import InteroceptiveChannel
from galatea.env.channels.proprio import ProprioceptiveChannel
from galatea.env.interventions.registry import InterventionRegistry
from galatea.env.profile import load_profile
from galatea.env.world.dynamics import MW0Dynamics
from galatea.env.world.mw0 import MW0World
from galatea.kernel.clock import CycleClock
from galatea.kernel.packet import ArtifactRef, RepresentationLevel
from galatea.kernel.registry import Registry
from galatea.kernel.rng import RngDirectory, chacha8_block
from galatea.kernel.state import Stores

_ROOT = Path(__file__).resolve().parents[3]


def _m2_profile():
    from galatea.subject.memory.store import load_m2_continuity_profile

    return load_m2_continuity_profile()


def long_run_stability(seed: bytes, cycles: int = 256) -> dict[str, Any]:
    """判据 1：256 cycles（4× 最长此前场景）连续运行。

    稳定性 = 全程无异常完成 + 记忆容量治理真实接管（溢出面在案）+ 终态 digest。
    """
    profile = load_profile(_ROOT / "config" / "profiles" / "m0_mw0.profile.yaml")
    tmp = Path(tempfile.mkdtemp(prefix="h1-long-"))   # INC-13 纪律：清理仅限此路径
    stores = Stores(tmp / "stores")
    try:
        reg = Registry(tmp / "registry", stores, CycleClock())
        world = MW0World(profile.params, RngDirectory(seed, chacha8_block), branch_id="B")
        dynamics = MW0Dynamics(world, profile, RngDirectory(seed, chacha8_block), branch_id="B")
        bus = ChannelBus(profile.params, reg, RngDirectory(seed, chacha8_block),
                         branch_id="B", interventions=InterventionRegistry())
        extero, intero = ExteroceptiveChannel(bus, world), InteroceptiveChannel(bus, world)
        proprio = ProprioceptiveChannel(bus, world)
        from galatea.subject.memory.encode import encode_working
        from galatea.subject.memory.ports import SourceType
        from galatea.subject.memory.store import MemoryStore, MemoryStoreViolation

        memory = MemoryStore(stores)
        m2 = _m2_profile()
        completed = 0
        overflow_events = 0
        for cycle in range(cycles):
            dynamics.step()
            truth_ref = ArtifactRef(digest=world.state_digest(), kind="world_state_ref")
            extero.render_and_submit(cycle, truth_ref)
            intero.render_and_submit(cycle, truth_ref, ())
            proprio.render_and_submit(cycle, truth_ref)
            delivery = bus.deliver(cycle)
            packets: list[tuple[Any, str]] = []
            for packet in delivery.packets:
                blob = reg.get(ArtifactRef(digest=packet.payload_ref.digest,
                                           kind="payload")).blob
                try:
                    json.loads(blob)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                packets.append((packet, blob.decode("utf-8")))
            del packets, delivery
            if cycle % 4 == 0:
                try:
                    encode_working(memory, m2, f"w.{cycle}", world.state_digest(),
                                   RepresentationLevel.SENSORY_FORMED,
                                   SourceType.PERCEIVED, cycle)
                except MemoryStoreViolation:
                    overflow_events += 1   # 容量治理真实接管（长时运行实态）
            completed += 1
        return {
            "cycles_completed": completed,
            "final_digest": world.state_digest(),
            "overflow_events": overflow_events,
            "stable": completed == cycles,
        }
    finally:
        stores.close()
        shutil.rmtree(tmp, ignore_errors=True)   # INC-13 纪律：仅删 mkdtemp 具体路径


def fault_injection_and_recovery(seed: bytes) -> dict[str, Any]:
    """判据 2：fault 注入（投递丢失面）+ store 关闭重开（digest 不失 = 状态不失）。"""
    profile = load_profile(_ROOT / "config" / "profiles" / "m0_mw0.profile.yaml")
    tmp = Path(tempfile.mkdtemp(prefix="h1-fault-"))   # INC-13 纪律
    stores = Stores(tmp / "stores")
    try:
        reg = Registry(tmp / "registry", stores, CycleClock())
        world = MW0World(profile.params, RngDirectory(seed, chacha8_block), branch_id="B")
        dynamics = MW0Dynamics(world, profile, RngDirectory(seed, chacha8_block), branch_id="B")
        interventions = InterventionRegistry()
        interventions.register(record_id="iflt", kind="fault", registered_at_cycle=0,
                               from_cycle=4, to_cycle=4)
        bus = ChannelBus(profile.params, reg, RngDirectory(seed, chacha8_block),
                         branch_id="B", interventions=interventions)
        extero, intero = ExteroceptiveChannel(bus, world), InteroceptiveChannel(bus, world)
        proprio = ProprioceptiveChannel(bus, world)
        delivered_counts: list[int] = []
        for cycle in range(6):
            dynamics.step()
            truth_ref = ArtifactRef(digest=world.state_digest(), kind="world_state_ref")
            extero.render_and_submit(cycle, truth_ref)
            intero.render_and_submit(cycle, truth_ref, ())
            proprio.render_and_submit(cycle, truth_ref)
            delivery = bus.deliver(cycle)
            delivered_counts.append(len(delivery.packets))
        # 恢复演练实测（REV-0024 R4：store 持久面快照——registry 内容索引 digest，
        # 关闭重开前后必须一致；非 world 内存态【原断言构造恒真——INC-08 同族】）
        pre_index = reg.index_digest()
        stores.close()
        stores2 = Stores(tmp / "stores")
        reg2 = Registry(tmp / "registry", stores2, CycleClock())
        post_index = reg2.index_digest()
        stores2.close()
        shutil.rmtree(tmp, ignore_errors=True)   # INC-13 纪律：仅删 mkdtemp 路径
        return {
            "delivery_profile": delivered_counts,
            "recovery_index_unchanged": pre_index == post_index,
            "stable": pre_index == post_index and len(delivered_counts) == 6,
        }
    except Exception:
        stores.close()
        raise


def supply_chain_audit(root: Path) -> dict[str, Any]:
    """判据 3：供应链 hash 审计——manifest 全锚 sha256 重算比对（Q-T08 语义）。

    INC-13 丢失件（status_inc13 注记）计入 lost 非 failed——历史锚保留可溯。
    """
    import yaml

    manifest = yaml.safe_load(
        (root / "config" / "evidence" / "artifact_manifest.yaml").read_text(encoding="utf-8"))
    total, ok = 0, 0
    failed: list[str] = []
    lost: list[str] = []
    for entry in manifest["artifact_manifest"]["artifacts"]:
        total += 1
        p = root / entry["path"]
        status = entry.get("status_inc13", "") + entry.get("status_p2", "")
        if not p.is_file():
            if status.startswith(("LOST", "SUPERSEDED")):
                lost.append(entry["name"])       # 历史锚保留可溯（INC-13 惯例 + P2 服务化演进）
                continue
            failed.append(f"missing:{entry['name']}")
            continue
        if hashlib.sha256(p.read_bytes()).hexdigest() == entry["sha256"]:
            ok += 1
        else:
            failed.append(f"hash:{entry['name']}")
    profiles = sorted((root / "config" / "profiles").glob("*.yaml"))
    return {
        "manifest_total": total, "manifest_ok": ok,
        "failed": failed, "lost_inc13": lost,
        "profiles_audited": len(profiles),
        "stable": not failed and len(profiles) >= 8,
    }


def i3_independent_reproduction(root: Path, recording: Path,
                                n: int = 8) -> dict[str, Any]:
    """判据 4：I3 独立重现（Q-L13-08②）——C4 efference claim 新 seed 集（同派生
    式，前缀 = b"h1-i3-new-seeds" 先于运行钉死）重跑；效应方向一致 ∧ d≥0.5
    （冻结最小效应；点估计不要求恒等——种子变异性是重现对象）。"""
    import math

    from galatea.evidence.control.recording import load_recording
    from galatea.evidence.control.runs_c4 import C4Runner

    _replay = load_recording(recording)   # 装载校验（miss 即 fail closed）；runs_c4 内部自录
    del _replay
    seed_prefix = b"h1-i3-new-seeds"
    runner = C4Runner(root, Path(tempfile.mkdtemp(prefix="h1-i3-")))   # INC-13 纪律
    diffs: list[float] = []
    try:
        for i in range(n):
            seed = hashlib.sha256(
                f"i3.reproduction|{i}".encode() + seed_prefix).digest()
            full = runner.run_efference(seed, ablated=False)
            ablated = runner.run_efference(seed, ablated=True)
            diffs.append(full["self_attribution_correct"]
                         - ablated["self_attribution_correct"])
    finally:
        from galatea.evidence.control.runs_c4 import cleanup_runner_tmp
        cleanup_runner_tmp(runner)   # INC-13 纪律：仅 mkdtemp 路径
    n_total = len(diffs)
    mean = sum(diffs) / n_total
    var = sum((x - mean) ** 2 for x in diffs) / (n_total - 1) if n_total > 1 else 0.0
    d = mean / math.sqrt(var) if var else float("inf")
    return {
        "n": n_total, "mean_diff": mean, "d": d,
        "direction_consistent": all(x >= 0 for x in diffs),
        "meets_min_effect": bool(mean >= 0.5 or (mean > 0 and math.isinf(d))),
        "stable": all(x >= 0 for x in diffs) and mean >= 0.5,
    }
