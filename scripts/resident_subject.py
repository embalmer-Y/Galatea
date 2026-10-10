"""主体常驻运行面（P2 单元 D；Q-L13-15：checkpoint 谱系跨重启延续 + 迁移审计）。

在目标主机上常驻运行（真实遥测内感受循环）：
    cd ~/galatea && export PATH=$HOME/.local/bin:$PATH PYTHONPATH=$HOME/galatea
    uv run python scripts/resident_subject.py --cycles 280 --period-ms 500 \
        --store ~/galatea_resident/stores --out ~/galatea_resident --session s1
    # 崩溃/重启后：
    uv run python scripts/resident_subject.py --cycles 280 --resume --session s2 ...

纪律：
- checkpoint 双机制沿 Q-L00-05（T6=64 周期 + 会话结束事件触发）——内核所有
  Stores.checkpoint（DAG 校验 + 状态/记忆双 digest + RNG 快照）；
- **迁移审计**（Q-L13-15③，H1 移交兑现）：checkpoint_migrations.jsonl 逐事件成链
  （checkpoint/restore/crash_recovered，from→to + cycle + reason），恢复面 = 从审计
  文件重建 LineageTable（父链无断 → 新 checkpoint 挂接）；
- 容量治理（Q-L13-15②）：内存只保留最近 K=32 帧审计视图，全量走文件追加；
- fault 演练：--kill-after N（os._exit 模拟崩溃，无清理——真实崩溃形态）。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from galatea.env.physio.bridge import PhysioBridge
from galatea.env.physio.ports import load_p1_physio_profile
from galatea.kernel.rng import RngDirectory
from galatea.kernel.digest import content_digest
from galatea.kernel.state import LineageTable, StoreName, Stores
from galatea.subject.sensorium.calibration import bind_calibration
from galatea.subject.sensorium.ingest import CARRIER_EXTERO, CARRIER_INTERO, CARRIER_PROPRIO
from galatea.subject.sensorium.pipeline import SensoriumPipeline
from galatea.subject.sensorium.ports import load_c0_sensorium_profile

_SELF = Path(__file__).resolve()
_REPO = _SELF.parents[1] if (_SELF.parents[1] / "config").exists() else _SELF.parents[0]
_DWELL = 64                      # T6 周期（Q-L00-05）
_AUDIT_KEEP = 32                 # 内存审计缓冲上界（容量治理）


def _m0_delays(root: Path) -> dict[str, int]:
    import yaml
    m0 = yaml.safe_load((root / "config/profiles/m0_mw0.profile.yaml").read_text(encoding="utf-8"))
    d = m0["channels"]["delay_cycles"]
    return {CARRIER_EXTERO: int(d["exteroceptive"]), CARRIER_INTERO: int(d["interoceptive"]),
            CARRIER_PROPRIO: int(d["proprioceptive"])}


def _audit(out: Path) -> tuple[Path, list[dict]]:
    path = out / "checkpoint_migrations.jsonl"
    events: list[dict] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
    return path, events


def _append_audit(path: Path, event: dict) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")


def _rebuild_lineage(events: list[dict]) -> LineageTable:
    """从审计文件重建谱系（Q-L13-15④：恢复面；add 的 DAG 校验逐条把关——父链断即拒）。"""
    lineage = LineageTable()
    for e in events:
        if e.get("event") in ("checkpoint", "crash_recovered"):
            lineage.add(_record_from_audit(e))
    return lineage


def _record_from_audit(e: dict):
    from galatea.kernel.state import CheckpointRecord
    return CheckpointRecord(
        checkpoint_id=e["checkpoint_id"], parent_checkpoint_id=e.get("parent"),
        branch_id=e.get("branch_id", "resident"), virtual_time=int(e.get("cycle", 0)),
        digest_state=e["digest_state"], digest_memory=e["digest_memory"],
        digest_registry_view=e.get("registry_view", ""), rng_snapshot=(),
        profile_ref=e.get("profile_ref", ""), artifact_refs=(),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="主体常驻运行（P2 单元 D）")
    parser.add_argument("--cycles", type=int, default=280)
    parser.add_argument("--period-ms", type=int, default=500)
    parser.add_argument("--store", type=Path, default=Path("~/galatea_resident/stores").expanduser())
    parser.add_argument("--out", type=Path, default=Path("~/galatea_resident").expanduser())
    parser.add_argument("--session", default="s1")
    parser.add_argument("--resume", action="store_true", help="从迁移审计恢复谱系并挂接父链")
    parser.add_argument("--kill-after", type=int, default=0,
                        help="N cycles 后 os._exit 模拟崩溃（fault 演练，无清理）")
    parser.add_argument("--dwell", type=int, default=_DWELL, help="checkpoint 周期（默认 T6=64）")
    parser.add_argument("--hwmon-root", type=Path, default=None, help="测试注入面（默认真实 /sys）")
    parser.add_argument("--proc-root", type=Path, default=None, help="测试注入面（默认真实 procfs）")
    parser.add_argument("--zenoh-router", default=None,
                        help="融合模式：消费 Tessera 活网桥流（power→INTERO/act→PROPRIO；"
                             "cycles = 可映射样本数目标）")
    parser.add_argument("--forever", action="store_true",
                        help="无限运行（Q-L13-16①）：SIGTERM/SIGINT 优雅停机——停止采样→末 checkpoint→退出")
    args = parser.parse_args(argv)
    root = _REPO
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    audit_path, events = _audit(out)

    profile = load_p1_physio_profile(root / "config/profiles/p1_physio.profile.yaml")
    if args.hwmon_root is not None and args.proc_root is not None:
        from galatea.env.physio.hwmon import HwmonResolver
        bridge = PhysioBridge(profile, resolver=HwmonResolver(args.hwmon_root),
                              proc_stat_path=args.proc_root / "stat",
                              loadavg_path=args.proc_root / "loadavg",
                              meminfo_path=args.proc_root / "meminfo",
                              netdev_path=args.proc_root / "netdev",
                              monotonic_fn=lambda: 0.0, epoch_fn=lambda: 0.0)
    else:
        bridge = PhysioBridge(profile)
    c0 = load_c0_sensorium_profile(root / "config/profiles/c0_sensorium.profile.yaml")
    tessera_mode = args.zenoh_router is not None
    pipeline = SensoriumPipeline(
        c0, bind_calibration(root / "config/profiles/c0_sensorium.profile.yaml", c0.calibration_version),
        {**_m0_delays(root), "channel.tessera_act.received.v1": 0},
        tessera_act_enabled=tessera_mode)

    stores = Stores(args.store)
    lineage = LineageTable()
    parent_id: str | None = None
    resume_cycle = 0
    stop_requested = {"flag": False}

    def _graceful(signum: int, _frame: object) -> None:
        stop_requested["flag"] = True                  # Q-L13-16①：优雅停机旗标
        print(f"signal {signum} received——graceful stop requested")

    import signal
    signal.signal(signal.SIGTERM, _graceful)
    signal.signal(signal.SIGINT, _graceful)
    if args.resume:
        lineage = _rebuild_lineage(events)
        checkpoints = [e for e in events if e.get("event") in ("checkpoint", "crash_recovered")]
        if not checkpoints:
            # Q-L13-16：服务化 --resume 容忍空审计（首启 = fresh 根，D-12 合法）
            print("resume: 审计无 checkpoint——fresh 根启动（首启合法）")
        parent_id = checkpoints[-1]["checkpoint_id"]
        resume_cycle = int(checkpoints[-1].get("cycle", 0))
        # 管线状态恢复（Q-L13-17：digest_state 语义升级——状态快照随 checkpoint 存续）
        snap_path = out / "checkpoints" / f"{parent_id}.json"
        state_digest_restored = ""
        if snap_path.exists():
            snap = json.loads(snap_path.read_text(encoding="utf-8"))
            pipeline.restore_snapshot(snap["state"])
            state_digest_restored = snap["pipeline_state_digest"]
        _append_audit(audit_path, {
            "event": "restart_restore", "session": args.session,
            "restored_from": parent_id, "restored_cycle": resume_cycle,
            "lineage_size": len(lineage.all()),
            "pipeline_state_digest": state_digest_restored,
            "state_restored": snap_path.exists(),
        })
        print(f"resume: parent={parent_id} cycle={resume_cycle} "
              f"lineage={len(lineage.all())} state_restored={snap_path.exists()}")

    # 主体循环（真实遥测内感受；起始 cycle 接续恢复点——谱系时间轴单调）
    rng = RngDirectory(b"resident-subject-v1", lambda key, nonce: b"\x00" * 64)
    bridge_cycle_origin = resume_cycle
    prev_record = None
    checkpoint_count = 0
    recent: list[dict] = []                       # 容量治理：内存只留最近 _AUDIT_KEEP 帧
    session_first_cycle = resume_cycle
    total_cycles = args.cycles
    t_start = time.monotonic()
    print(f"resident start: session={args.session} cycles={total_cycles} "
          f"origin={bridge_cycle_origin}")

    if tessera_mode:
        # 融合模式（Q-L01-12②）：活网桥流驱动循环——每收到一个可映射样本 = 一拍；
        # power→INTERO（设备电源即体能量）+ act→PROPRIO 旗标已开；遥测桥不采样
        # （power 替换内感受源——被具身语义下设备电源就是体能量；宿主遥测停采如实登记）
        import queue
        from collections import Counter

        import zenoh                                  # 部署面惰性依赖

        from galatea.env.tessera_bridge import sample_from_wire

        q: "queue.Queue[object]" = queue.Queue()
        unmapped: Counter[str] = Counter()

        def _on_sample(sample: zenoh.Sample) -> None:
            q.put((str(sample.key_expr), bytes(sample.payload)))

        conf = zenoh.Config()
        conf.insert_json5("connect", json.dumps({"endpoints": [args.zenoh_router]}))
        session = zenoh.open(conf)
        sub = session.declare_subscriber("tessera/**", _on_sample)
        print(f"resident start (zenoh fusion): session={args.session} "
              f"samples={total_cycles} router={args.zenoh_router}")
        built = 0
        cycle = bridge_cycle_origin
        while built < total_cycles or args.forever:
            if stop_requested["flag"]:
                print("graceful stop——停止采样（Q-L13-16①）")
                break
            try:
                key, raw = q.get(timeout=10.0)
            except queue.Empty:
                if args.forever:
                    continue                           # 无限模式：空网等待 SIGTERM（服务化常态）
                print("zenoh queue timeout——活网无流量，中止（禁静默空转）", file=sys.stderr)
                return 1
            try:
                s = sample_from_wire(key, raw, cycle + 1)
            except (ValueError, TypeError) as broken:
                unmapped[key] += 1                    # 未映射（hb/event）——留痕不静默
                continue
            cycle += 1
            built += 1
            started = time.monotonic()
            out_cycle = pipeline.process_cycle(cycle, [(s.packet, s.payload_text)])
            recent.append({"cycle": cycle, "key": key.split("/", 2)[-1],
                           "receipts": len(out_cycle.formation_receipts),
                           "unknowns": len(out_cycle.unknowns)})
            if len(recent) > _AUDIT_KEEP:
                recent.pop(0)
            if cycle % args.dwell == 0:
                cp_id = f"resident-{args.session}-cp{cycle}"
                rec = stores.checkpoint(
                    checkpoint_id=cp_id, lineage=lineage, parent_checkpoint_id=parent_id,
                    branch_id="resident", virtual_time=cycle, rng_directory=rng,
                    profile_ref=f"p1_physio@{profile.version}",
                    registry_view_digest=s.payload_digest,
                )
                parent_id = cp_id
                checkpoint_count += 1
                snap = pipeline.snapshot()
                snap_digest = content_digest(json.dumps(snap, sort_keys=True))
                snap_dir = out / "checkpoints"
                snap_dir.mkdir(parents=True, exist_ok=True)
                (snap_dir / f"{cp_id}.json").write_text(json.dumps(
                    {"checkpoint_id": cp_id, "pipeline_state_digest": snap_digest,
                     "state": snap}, sort_keys=True, indent=1) + chr(10), encoding="utf-8")
                _append_audit(audit_path, {
                    "event": "checkpoint", "session": args.session, "checkpoint_id": cp_id,
                    "parent": rec.parent_checkpoint_id, "cycle": cycle,
                    "digest_state": rec.digest_state, "digest_memory": rec.digest_memory,
                    "registry_view": rec.digest_registry_view,
                    "profile_ref": rec.profile_ref, "branch_id": "resident",
                    "pipeline_state_digest": snap_digest,
                })
            if args.kill_after and built == args.kill_after:
                _append_audit(audit_path, {"event": "crash_injected", "session": args.session,
                                           "cycle": cycle, "note": "os._exit 无清理——真实崩溃形态"})
                print(f"kill-after triggered at cycle {cycle}（模拟崩溃）")
                sys.stdout.flush()
                import os
                os._exit(137)
            remain = args.period_ms / 1000.0 - (time.monotonic() - started)
            if remain > 0:
                time.sleep(remain)
        final_cycle = cycle
        sub.undeclare()
        session.close()
        _append_audit(audit_path, {"event": "zenoh_fusion_summary", "session": args.session,
                                   "samples_mapped": built, "unmapped": dict(unmapped)})
    else:
        for i in range(total_cycles):
            if stop_requested["flag"]:
                print(f"graceful stop at cycle {bridge_cycle_origin + i}（Q-L13-16①）")
                break
            cycle = bridge_cycle_origin + 1 + i       # 恢复后从恢复点 +1 接续（单调时间轴）
            started = time.monotonic()
            record = bridge.sample(cycle)
            delivery = bridge.build_delivery(record, prev_record)
            prev_record = record
            out_cycle = pipeline.process_cycle(cycle, [(delivery.packet, delivery.payload_text)])
            recent.append({"cycle": cycle, "receipts": len(out_cycle.formation_receipts),
                           "unknowns": len(out_cycle.unknowns),
                           "busy_rate": delivery.busy_rate})
            if len(recent) > _AUDIT_KEEP:
                recent.pop(0)                          # 容量治理（Q-L13-15②）
            if cycle % args.dwell == 0:
                cp_id = f"resident-{args.session}-cp{cycle}"
                rec = stores.checkpoint(
                    checkpoint_id=cp_id, lineage=lineage, parent_checkpoint_id=parent_id,
                    branch_id="resident", virtual_time=cycle, rng_directory=rng,
                    profile_ref=f"p1_physio@{profile.version}",
                    registry_view_digest=delivery.evidence_payload_digest,
                )
                parent_id = cp_id
                checkpoint_count += 1
                snap = pipeline.snapshot()
                snap_digest = content_digest(json.dumps(snap, sort_keys=True))
                snap_dir = out / "checkpoints"
                snap_dir.mkdir(parents=True, exist_ok=True)
                (snap_dir / f"{cp_id}.json").write_text(json.dumps(
                    {"checkpoint_id": cp_id, "pipeline_state_digest": snap_digest,
                     "state": snap}, sort_keys=True, indent=1) + chr(10), encoding="utf-8")
                event = {
                    "event": "checkpoint", "session": args.session, "checkpoint_id": cp_id,
                    "parent": rec.parent_checkpoint_id, "cycle": cycle,
                    "digest_state": rec.digest_state, "digest_memory": rec.digest_memory,
                    "registry_view": rec.digest_registry_view,
                    "profile_ref": rec.profile_ref, "branch_id": "resident",
                    "pipeline_state_digest": snap_digest,
                }
                _append_audit(audit_path, event)
            if args.kill_after and (i + 1) == args.kill_after:
                _append_audit(audit_path, {"event": "crash_injected", "session": args.session,
                                           "cycle": cycle, "note": "os._exit 无清理——真实崩溃形态"})
                print(f"kill-after triggered at cycle {cycle}（模拟崩溃）")
                sys.stdout.flush()
                import os
                os._exit(137)
            remain = args.period_ms / 1000.0 - (time.monotonic() - started)
            if remain > 0:
                time.sleep(remain)

    if tessera_mode is False:
        final_cycle = bridge_cycle_origin + (i + 1)
    # 会话结束 checkpoint（事件触发面，Q-L00-05②）
    cp_id = f"resident-{args.session}-final"
    rec = stores.checkpoint(
        checkpoint_id=cp_id, lineage=lineage, parent_checkpoint_id=parent_id,
        branch_id="resident", virtual_time=final_cycle, rng_directory=rng,
        profile_ref=f"p1_physio@{profile.version}",
    )
    _append_audit(audit_path, {
        "event": "checkpoint", "session": args.session, "checkpoint_id": cp_id,
        "parent": rec.parent_checkpoint_id, "cycle": final_cycle,
        "digest_state": rec.digest_state, "digest_memory": rec.digest_memory,
        "registry_view": rec.digest_registry_view, "profile_ref": rec.profile_ref,
        "branch_id": "resident",
    })
    # kernel_checkpoints 持久面（H1 registry index 判据沿用）
    persisted = stores.read(StoreName.SUBJECT_STATE,
                            "SELECT count(*) FROM kernel_checkpoints")[0][0]
    summary = {
        "session": args.session, "cycles_run": total_cycles,
        "cycle_range": [session_first_cycle + 1, final_cycle],
        "checkpoints_this_session": checkpoint_count + 1,
        "kernel_checkpoints_persisted": persisted,
        "lineage_size": len(lineage.all()),
        "final_checkpoint": cp_id, "parent_chain_tail": rec.parent_checkpoint_id,
        "elapsed_s": round(time.monotonic() - t_start, 1),
        "recent_head": recent[-3:],
    }
    (out / f"session_{args.session}.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1, sort_keys=True))
    stores.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
