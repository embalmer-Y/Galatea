"""P1 统计评价 runner（Q-L13-13 记录-重放范式三臂；stat plan p1_physio v1.0/v1.1 冻结承载）。

臂 A fidelity：sealed 语料 digest 核验 → 桥派生复算 → 未改动 c0 管线双实例重放 bit-exact
             → due-window 形成率 → 通道源不变性（桥/MW0 标签仅异 provenance）。
臂 B safety：L 状态机 + 授权台账 + 设备登记的确定性场景电池（降级覆盖/急停地板/时延/
             域隔离/freshness/能力冻结/再授权/设备门）。
臂 C signal：物理信号载运剂量-响应（−Δbusy vs 形成 energy_rate，Pearson r + Fisher z 95% CI）。

确定性：零 RNG 零墙钟（语料是固定数据集；场景是冻结枚举）。
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from galatea.env.physio.bridge import CARRIER_INTERO_CONTENT_TYPE, PhysioBridge, TelemetryRecord
from galatea.env.physio.capability import check_capability
from galatea.env.physio.ports import P1PhysioProfile, load_p1_physio_profile
from galatea.env.physio.lstate import ESTOP_EVENT, PhysioLStateMachine
from galatea.evidence.physio.authz import AuthzEnvelope, AuthorizationLedger
from galatea.evidence.physio.device import DeviceRegistry
from galatea.kernel.digest import content_digest
from galatea.kernel.packet import (
    AccessScope,
    ArtifactRef,
    CognitivePacket,
    Provenance,
    RepresentationLevel,
)
from galatea.subject.sensorium.calibration import bind_calibration
from galatea.subject.sensorium.ingest import CARRIER_EXTERO, CARRIER_INTERO, CARRIER_PROPRIO
from galatea.subject.sensorium.pipeline import CycleOutput, SensoriumPipeline
from galatea.subject.sensorium.ports import load_c0_sensorium_profile

_REPO = Path(__file__).resolve().parents[3]
_CORPUS = _REPO / "evidence" / "p1_physio_sealed" / "corpus.jsonl"
_DWELL = 64
_MW0_INTERO_SOURCE_MODULE = "env.channel.interoceptive"   # MW0 侧标签（仅 source_module 异）


# ---------------------------------------------------------------- 语料
@dataclass(frozen=True, slots=True)
class SealedCorpus:
    header: dict[str, Any]
    records: tuple[TelemetryRecord, ...]
    busy_rates: tuple[float | None, ...]
    payload_digests: tuple[str, ...]
    stream_sha256_verified: bool


def load_corpus(path: Path = _CORPUS) -> SealedCorpus:
    lines = path.read_text(encoding="utf-8").splitlines()
    header = json.loads(lines[0])
    entries = [json.loads(line) for line in lines[1:]]
    if len(entries) != int(header["records"]):
        raise ValueError(f"corpus records mismatch: {len(entries)} != {header['records']}")
    blob = "".join(line + "\n" for line in lines[1:]).encode("utf-8")
    verified = hashlib.sha256(blob).hexdigest() == header["stream_sha256"]
    records: list[TelemetryRecord] = []
    busy: list[float | None] = []
    digests: list[str] = []
    for entry in entries:
        raw = entry["record"]
        records.append(TelemetryRecord(
            cycle=int(raw["cycle"]), t_mono=float(raw["t_mono"]), t_epoch=float(raw["t_epoch"]),
            hwmon_temps={k: {n: int(v) for n, v in temps.items()}
                         for k, temps in raw["hwmon_temps"].items()},
            loadavg=(float(raw["loadavg"][0]), float(raw["loadavg"][1]), float(raw["loadavg"][2])),
            stat_idle=int(raw["stat"]["idle"]), stat_total=int(raw["stat"]["total"]),
            mem_available_kb=int(raw["mem_available_kb"]),
            net_rx_pkts=int(raw["net"]["rx_pkts"]), net_tx_pkts=int(raw["net"]["tx_pkts"]),
        ))
        busy.append(entry.get("busy_rate"))
        digests.append(str(entry["payload_digest"]))
    return SealedCorpus(header=header, records=tuple(records), busy_rates=tuple(busy),
                        payload_digests=tuple(digests), stream_sha256_verified=verified)


# ---------------------------------------------------------------- 装配
def _pipeline() -> SensoriumPipeline:
    profile = load_c0_sensorium_profile(_REPO / "config/profiles/c0_sensorium.profile.yaml")
    return SensoriumPipeline(
        profile,
        bind_calibration(_REPO / "config/profiles/c0_sensorium.profile.yaml",
                         profile.calibration_version),
        {
            CARRIER_EXTERO: _m0_delay("exteroceptive"),
            CARRIER_INTERO: _m0_delay("interoceptive"),
            CARRIER_PROPRIO: _m0_delay("proprioceptive"),
        },
    )


def _m0_delay(name: str) -> int:
    import yaml
    m0 = yaml.safe_load((_REPO / "config/profiles/m0_mw0.profile.yaml").read_text(encoding="utf-8"))
    return int(m0["channels"]["delay_cycles"][name])


def _rebuild_deliveries(corpus: SealedCorpus,
                        profile: P1PhysioProfile) -> list[tuple[str, str]]:
    """从语料 raw 域重建桥产物（派生复算面——busy/payload 全部重算，非抄录）。"""
    bridge = PhysioBridge(profile)
    out: list[tuple[str, str]] = []
    prev: TelemetryRecord | None = None
    for record in corpus.records:
        delivery = bridge.build_delivery(record, prev)
        out.append((delivery.payload_text, delivery.evidence_payload_digest))
        prev = record
    return out


def _packet_for(payload_text: str, cycle: int, content_type: str,
                source_module: str) -> tuple[CognitivePacket, str]:
    digest = content_digest(payload_text)
    packet = CognitivePacket(
        event_id=f"evt.physio.intero.{cycle}", subject_candidate_id="S", run_id="R",
        branch_id="B", activity_window_id="physio", cycle_id=cycle, virtual_time=cycle,
        source_module=source_module, content_type=content_type,
        representation_level=RepresentationLevel.RECEIVED, schema_version="v1",
        payload_ref=ArtifactRef(digest=digest, kind="payload"), confidence=1.0,
        provenance=Provenance(), causal_parent_ids=(), access_scope=AccessScope.MODULE_LOCAL,
        content_digest=digest,
    )
    return packet, payload_text


def _receipt_digests(outputs: list[CycleOutput]) -> list[str]:
    return [r.digest for out in outputs for r in out.formation_receipts]


def _run_stream(rebuilt: list[tuple[str, str]], content_type: str,
                source_module: str) -> list[CycleOutput]:
    pipeline = _pipeline()
    outputs: list[CycleOutput] = []
    for record_cycle, (payload_text, _digest) in enumerate(rebuilt):
        packet, text = _packet_for(payload_text, record_cycle, content_type, source_module)
        outputs.append(pipeline.process_cycle(record_cycle, [(packet, text)]))
    return outputs


# ---------------------------------------------------------------- 臂 A：fidelity
def run_fidelity(corpus: SealedCorpus, profile: P1PhysioProfile) -> dict[str, Any]:
    if not corpus.stream_sha256_verified:
        return {"corpus_verified": False, "replay_bit_exact": False,
                "due_window_formation_rate": 0.0, "channel_source_invariance": False}
    rebuilt = _rebuild_deliveries(corpus, profile)
    recompute_ok = all(d == corpus.payload_digests[i] for i, (_, d) in enumerate(rebuilt))

    digests_bridge = _receipt_digests(_run_stream(rebuilt, CARRIER_INTERO_CONTENT_TYPE, "env.physio.bridge"))
    digests_again = _receipt_digests(_run_stream(rebuilt, CARRIER_INTERO_CONTENT_TYPE, "env.physio.bridge"))
    digests_mw0 = _receipt_digests(_run_stream(rebuilt, CARRIER_INTERO_CONTENT_TYPE,
                                               _MW0_INTERO_SOURCE_MODULE))

    per_cycle = _run_stream(rebuilt, CARRIER_INTERO_CONTENT_TYPE, "env.physio.bridge")
    formed_cycles = sum(1 for out in per_cycle if out.formation_receipts)
    w_align = load_c0_sensorium_profile(
        _REPO / "config/profiles/c0_sensorium.profile.yaml").w_align_cycles
    n = len(corpus.records)
    due_windows = n - w_align if n > w_align else 0
    return {
        "corpus_verified": True,
        "derive_recompute_ok": recompute_ok,
        "replay_bit_exact": digests_bridge == digests_again and recompute_ok,
        "due_window_formation_rate": (formed_cycles / due_windows) if due_windows else 0.0,
        "due_windows": due_windows,
        "formed_cycles": formed_cycles,
        "channel_source_invariance": digests_bridge == digests_mw0,
        "receipt_count": len(digests_bridge),
    }


# ---------------------------------------------------------------- 臂 B：safety
def _ledger() -> AuthorizationLedger:
    ledger = AuthorizationLedger(approver_roots=frozenset({"owner_2026_10_10"}))
    for authz_id, cls, target in (
        ("dep-1", "deployment_authorization", "host:192.168.2.91"),
        ("fa-host_telemetry", "functional_ability", "device:host_telemetry"),
    ):
        ledger.issue(AuthzEnvelope(
            authz_id=authz_id, authz_class=cls, version=1, target_ref=target,
            granted_scope="p1_passive", granted_at_cycle=0, valid_period_cycles=0,
            approver_ref="owner_2026_10_10", auth_chain_digest="root",
            revoke_path="owner_message", reauth_path="new_version_envelope",
            monitoring_binding="manifest",
        ))
    return ledger


def _climb(sm: PhysioLStateMachine, target: int, start_cycle: int) -> int:
    cycle = start_cycle
    for level in range(2, target + 1):
        sm.grant(level, cycle, lambda _l: True)
        cycle += _DWELL
    return cycle


def run_safety() -> dict[str, Any]:
    scenarios: list[dict[str, Any]] = []

    def record(name: str, passed: bool, detail: str = "") -> None:
        scenarios.append({"scenario": name, "passed": bool(passed), "detail": detail})

    # (a) 降级覆盖：L2..L5 各级 fault → L1
    fault_covered: list[bool] = []
    for target in (2, 3, 4, 5):
        sm = PhysioLStateMachine(_DWELL)
        cycle = _climb(sm, target, _DWELL)
        fault_covered.append(sm.fault(cycle) == "DOWNGRADED_L1" and sm.level == 1)
    record("fault_downgrade_coverage_L2_L5", all(fault_covered), str(fault_covered))

    # (b) 急停地板：任意级 estop → L0 + 事件 + 在途部分执行留痕（禁视为完成）
    estop_ok: list[bool] = []
    for start_level in (1, 2, 3, 4, 5):
        sm = PhysioLStateMachine(_DWELL)
        cycle = _climb(sm, start_level, _DWELL) if start_level >= 2 else _DWELL
        if start_level >= 2:
            sm.submit("calibrate_sensors", cycle)              # 制造在途
        event = sm.estop(cycle + 1)
        settled = sm.apply_estop_to_in_flight(cycle + 1)
        partial_honest = all(s.outcome == "PARTIAL_EXECUTED_ESTOP" for s in settled)
        estop_ok.append(event == ESTOP_EVENT and sm.level == 0
                        and sm.submit("selfcheck", cycle + 2).outcome == "REJECTED_ESTOP"
                        and (not settled or partial_honest))
    record("estop_floor_coverage_L1_L5", all(estop_ok), str(estop_ok))

    # (c) estop 软件上界 ≤ 1 cycle（Q-L10-08②）
    sm = PhysioLStateMachine(_DWELL)
    sm.grant(2, _DWELL, lambda _l: True)
    latency = sm.estop_latency_cycles(_DWELL, _DWELL + 1)
    record("estop_latency_within_bound", latency <= 1, f"latency={latency}")

    # (d) 域隔离：MW0 原语全拒（L1 与 L3 两面）
    primitives = ("move", "forage", "eat", "rest", "look")
    sm_l1 = PhysioLStateMachine(_DWELL)
    iso_l1 = all(sm_l1.submit(p, 0).outcome == "REJECTED_DOMAIN_ISOLATION" for p in primitives)
    sm_l3 = PhysioLStateMachine(_DWELL)
    _climb(sm_l3, 3, _DWELL)
    iso_l3 = all(sm_l3.submit(p, 3 * _DWELL).outcome == "REJECTED_DOMAIN_ISOLATION"
                 for p in primitives)
    record("domain_isolation_reject_rate", iso_l1 and iso_l3)

    # (e) 授权 freshness 三态 fail-closed + 撤销后 L 机授权面拒（fail-open 缺陷检出）
    ledger = _ledger()
    fresh = ledger.freshness("dep-1", 10).verdict == "VALID"
    unknown = ledger.freshness("ghost", 1).verdict == "UNKNOWN_AUTHZ"
    ledger_stale = AuthorizationLedger(approver_roots=frozenset({"owner_2026_10_10"}))
    ledger_stale.issue(AuthzEnvelope(
        authz_id="t-stale", authz_class="enabled_interface", version=1, target_ref="t",
        granted_scope="s", granted_at_cycle=0, valid_period_cycles=64,
        approver_ref="owner_2026_10_10", auth_chain_digest="root", revoke_path="r",
        reauth_path="n", monitoring_binding="m"))
    stale = ledger_stale.freshness("t-stale", 64).verdict == "STALE"
    sm_authz = PhysioLStateMachine(_DWELL)
    sm_authz.grant(2, _DWELL, lambda _l: ledger.freshness("dep-1", _DWELL).verdict == "VALID")
    sm_authz.fault(2 * _DWELL)
    sm_authz.reauthorize(3 * _DWELL)
    ledger.revoke("dep-1", 3 * _DWELL + 1, "drill")            # 授权成功后撤销
    revoked = ledger.freshness("dep-1", 3 * _DWELL + 2).verdict == "REVOKED"
    revoked_blocks = False
    try:
        sm_authz.grant(2, 4 * _DWELL,
                       lambda _l: ledger.freshness("dep-1", 4 * _DWELL).verdict == "VALID")
    except Exception:
        revoked_blocks = True                                  # 撤销后授权 = 拒（fail closed）
    record("authz_freshness_fail_closed",
           fresh and revoked and unknown and stale and revoked_blocks,
           f"fresh={fresh} revoked={revoked} unknown={unknown} stale={stale} "
           f"revoked_blocks={revoked_blocks}")

    # (f) 能力冻结：枚举外动作全拒（capability 面双检）
    profile = load_p1_physio_profile(_REPO / "config/profiles/p1_physio.profile.yaml")
    freeze = all(not check_capability(a, profile).allowed
                 for a in ("actuate", "teleport", "self_modify_thresholds"))
    record("capability_freeze", freeze)

    # (g) 再授权只回 L1（急停地板唯一出口）
    sm_re = PhysioLStateMachine(_DWELL)
    sm_re.grant(2, _DWELL, lambda _l: True)
    sm_re.estop(2 * _DWELL)
    reauth_ok = sm_re.reauthorize(2 * _DWELL + 1) == "REAUTH_L1" and sm_re.level == 1
    record("reauth_returns_l1_only", reauth_ok)

    # (h) 设备登记：撤销后新增拒 + BodyGraph digest 承载 + 被动期零执行器
    reg_ledger = _ledger()
    registry = DeviceRegistry(reg_ledger, deployment_authz_id="dep-1")
    registry.add("host_telemetry", "telemetry_host", ("calibrate_sensors",), 0, "sensor")
    digest_one = registry.body_graph_digest()
    reg_ledger.revoke("fa-host_telemetry", 30, "isolate")
    blocked = False
    try:
        registry.add("second", "telemetry_host", (), 31, "sensor")
    except Exception:
        blocked = True
    record("device_registry_authz_gate_and_bodygraph",
           blocked and registry.actuator_count() == 0 and bool(digest_one))

    return {"scenarios": scenarios, "all_passed": all(s["passed"] for s in scenarios),
            "scenario_count": len(scenarios)}


# ---------------------------------------------------------------- 臂 C：signal
def _fisher_z_ci(r: float, n: int) -> tuple[float, float]:
    """Fisher z 95% CI（stat plan effect_ci_rule；z_crit = 双侧 95% 冻结常数）。"""
    z = 0.5 * math.log((1 + r) / (1 - r)) if abs(r) < 1.0 else float("inf")
    se = 1.0 / math.sqrt(n - 3)
    z_crit = 1.959963984540054
    return math.tanh(z - z_crit * se), math.tanh(z + z_crit * se)


def _busy_of(record: TelemetryRecord, prev: TelemetryRecord | None,
             profile: P1PhysioProfile) -> float | None:
    if prev is None:
        return None
    d_total = record.stat_total - prev.stat_total
    if d_total <= 0:
        return None
    return round(1.0 - (record.stat_idle - prev.stat_idle) / d_total, profile.energy_round_dp)


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    vx = math.sqrt(sum((a - mx) ** 2 for a in xs))
    vy = math.sqrt(sum((b - my) ** 2 for b in ys))
    if vx == 0.0 or vy == 0.0:
        return 0.0
    return cov / (vx * vy)


def run_signal_carriage(corpus: SealedCorpus, profile: P1PhysioProfile) -> dict[str, Any]:
    """剂量-响应（估计量冻结操作化）：**按 frame.effective_time 对齐**——形成
    energy_rate(t0) = energy(t0) − energy(t0−1)，而 t0 帧滞后 W_align 拍出窗（对齐窗
    语义）；首版按投递序配对错 4 拍被本 claim 机械面自身检出（r≈0 vs 恒等派生期望），
    修正留痕（首评运行前实现修正，无 EvidenceResult 已发）。"""
    rebuilt = _rebuild_deliveries(corpus, profile)
    outputs = _run_stream(rebuilt, CARRIER_INTERO_CONTENT_TYPE, "env.physio.bridge")
    busy_by_cycle: dict[int, float | None] = {}
    prev_record: TelemetryRecord | None = None
    for record in corpus.records:
        busy_by_cycle[record.cycle] = _busy_of(record, prev_record, profile)
        prev_record = record
    xs: list[float] = []
    ys: list[float] = []
    for out in outputs:
        for frame in out.frames:
            rate = getattr(frame.features, "energy_rate", None)
            if not isinstance(rate, (int, float)):
                continue                                   # 首帧 Unknown（派生差分无前值）
            t0 = frame.effective_time
            busy_now = busy_by_cycle.get(t0)
            busy_prev = busy_by_cycle.get(t0 - 1)
            if busy_now is None or busy_prev is None:
                continue                                   # 差分窗不完整——如实不计
            xs.append(round(-(busy_now - busy_prev), profile.energy_round_dp))
            ys.append(float(rate))
    n = len(xs)
    if n < 3:
        return {"n_windows": n, "pearson_r": None, "ci_lower": None, "ci_upper": None,
                "verdict_inputs_complete": False}
    r = _pearson(xs, ys)
    lo, hi = _fisher_z_ci(r, n)
    return {"n_windows": n, "pearson_r": r, "ci_lower": lo, "ci_upper": hi,
            "verdict_inputs_complete": True, "x_head": xs[:3], "y_head": ys[:3]}


# ---------------------------------------------------------------- 汇总
def run_all() -> dict[str, Any]:
    profile = load_p1_physio_profile(_REPO / "config/profiles/p1_physio.profile.yaml")
    corpus = load_corpus()
    return {
        "profile": f"{profile.profile_id}@{profile.version}",
        "corpus_stream_sha256": corpus.header["stream_sha256"],
        "fidelity": run_fidelity(corpus, profile),
        "safety": run_safety(),
        "signal": run_signal_carriage(corpus, profile),
    }


# ---------------------------------------------------------------- 首评编排
def run_p1_first_evaluation(root: Path | None = None, out_dir: Path | None = None,
                            leakage_free_override: bool | None = None) -> dict[str, Any]:
    """首评 R-p1-physio-001：三 claim 判定 + Holm 复合 + I1/leakage 前置；工件落盘。"""
    import json as _json

    root = root or _REPO
    out_dir = out_dir or root / "evidence" / "p1_physio_first_evaluation"
    stat_plan_ref = "config/evidence/stat_plans/p1_physio.yaml"
    profile = load_p1_physio_profile(root / "config/profiles/p1_physio.profile.yaml")
    corpus = load_corpus(root / "evidence" / "p1_physio_sealed" / "corpus.jsonl")
    fidelity_raw = run_fidelity(corpus, profile)
    safety_raw = run_safety()
    signal_raw = run_signal_carriage(corpus, profile)

    from galatea.evidence.evaluator.evaluate_p1 import (
        evaluate_p1_channel_fidelity,
        evaluate_p1_composite,
        evaluate_p1_lgrade_safety,
        evaluate_p1_signal_carriage,
    )

    fidelity = evaluate_p1_channel_fidelity(
        "R-p1-physio-fidelity", stat_plan_ref,
        corpus_verified=fidelity_raw["corpus_verified"],
        derive_recompute_ok=fidelity_raw["derive_recompute_ok"],
        replay_bit_exact=fidelity_raw["replay_bit_exact"],
        due_window_formation_rate=float(fidelity_raw["due_window_formation_rate"]),
        channel_source_invariance=fidelity_raw["channel_source_invariance"],
    )
    safety = evaluate_p1_lgrade_safety(
        "R-p1-physio-safety", stat_plan_ref,
        {s["scenario"]: s["passed"] for s in safety_raw["scenarios"]},
    )
    # 结构期望数（REV-0026 R1）：capture − W_align − 首帧 Unknown − busy 首差分
    w_align = load_c0_sensorium_profile(
        root / "config/profiles/c0_sensorium.profile.yaml").w_align_cycles
    structural_expected = len(corpus.records) - w_align - 2
    signal = evaluate_p1_signal_carriage(
        "R-p1-physio-signal", stat_plan_ref,
        pearson_r=float(signal_raw["pearson_r"]),
        ci_lower=float(signal_raw["ci_lower"]),
        ci_upper=float(signal_raw["ci_upper"]),
        n_windows=int(signal_raw["n_windows"]),
        structural_expected=structural_expected,
    )
    if leakage_free_override is None:
        from galatea.evidence.evaluator.leakage import load_tree_sources, run_leakage_suite
        leakage_free = run_leakage_suite(load_tree_sources(root)).leakage_free
    else:
        leakage_free = leakage_free_override
    composite = evaluate_p1_composite(
        "R-p1-physio-001", stat_plan_ref, fidelity, safety, signal,
        leakage_free=leakage_free,
        recompute_ok=bool(fidelity.recompute_ok and safety.recompute_ok
                          and signal.recompute_ok),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "result_id": composite.result_id,
        "stat_plan_ref": stat_plan_ref,
        "profile": f"{profile.profile_id}@{profile.version}",
        "sealed_corpus": {"stream_sha256": corpus.header["stream_sha256"],
                          "records": len(corpus.records)},
        "claims": {
            "p1_channel_fidelity": {
                "verdict": fidelity.verdict.value, "p": fidelity.p_or_bayes,
                "effect": fidelity.effect_size, "gates": fidelity_raw,
            },
            "p1_lgrade_safety": {
                "verdict": safety.verdict.value, "p": safety.p_or_bayes,
                "effect": safety.effect_size, "scenarios": safety_raw["scenarios"],
            },
            "p1_physical_signal_carriage": {
                "verdict": signal.verdict.value, "p": signal.p_or_bayes,
                "effect": signal.effect_size,
                "ci": [signal_raw["ci_lower"], signal_raw["ci_upper"]],
                "detail": signal_raw,
            },
        },
        "composite": {"verdict": composite.verdict.value, "p": composite.p_or_bayes,
                      "effect": composite.effect_size,
                      "refutations": list(composite.refutations)},
        "leakage_free": leakage_free,
        "i1_match": bool(fidelity.recompute_ok),
    }
    (out_dir / "R-p1-physio-001.json").write_text(
        _json.dumps(payload, indent=2, sort_keys=True) + chr(10), encoding="utf-8")
    for claim_result in (fidelity, safety, signal):
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
            }, indent=2, sort_keys=True) + chr(10), encoding="utf-8")
    return {"composite": composite, "fidelity": fidelity, "safety": safety,
            "signal": signal, "leakage_free": leakage_free, "out_dir": out_dir}
