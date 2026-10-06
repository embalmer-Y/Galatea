"""C3 正式评价 runner（四臂协议 + recorder 四分区 + I1 复算 + 机械判据）。

臂（同 seed 同世界流；差异唯一来源 = 仲裁序/OOD 注入——D-10 可干预）：
- full_priority：优先序仲裁（Q-L08-04）+ 七源 + metacontrol
- score_only：front 内纯分数 tie-break（优先序消融）
- ood_full：full_priority + OOD 注入（每 8 拍窗[0][0]=5.0 → abstain → OBSERVE 触发）
- clean_full：full_priority 无注入（claim 2 对照）

REV-0014 R1 教训在案：registry blob 恒 bytes 显式 decode。
"""
import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from galatea.kernel.clock import CycleClock
from galatea.kernel.digest import content_digest
from galatea.kernel.packet import ArtifactRef
from galatea.kernel.registry import Registry
from galatea.kernel.rng import RngDirectory, chacha8_block
from galatea.kernel.state import Stores
from galatea.evidence.recorder.heartbeat import probe_recorder
from galatea.evidence.recorder.manifest import RunManifest
from galatea.evidence.recorder.replay import recompute_i1
from galatea.evidence.recorder.writer import EvidenceWriter
from galatea.evidence.evaluator.statplan import StatPlanViolation, load_stat_plan
from galatea.env.channels.adapter import ChannelBus
from galatea.env.channels.extero import ExteroceptiveChannel
from galatea.env.channels.intero import InteroceptiveChannel
from galatea.env.channels.outcome import OutcomeChannel
from galatea.env.channels.proprio import ProprioceptiveChannel
from galatea.env.interventions.registry import InterventionRegistry
from galatea.env.profile import MW0Profile, load_profile
from galatea.env.world.dynamics import Command as DynCommand
from galatea.env.world.dynamics import MW0Dynamics
from galatea.env.world.mw0 import MW0World, Primitive
from galatea.subject.action.gateway import ActionSpec, CapabilityGateway, load_gateway_config
from galatea.subject.action.signature import derive_signing_key
from galatea.subject.control.intention import ActionIntention
from galatea.subject.affect.pipeline import AffectPipeline
from galatea.subject.affect.ports import AffectCycleInputs
from galatea.subject.c1profile import load_c1_profile
from galatea.subject.c2profile import load_c2_affect_profile
from galatea.subject.c3profile import load_c3_motivation_profile
from galatea.subject.goals.arbitration import arbitrate as arbitrate_candidates
from galatea.subject.goals.arbitration import vector_of
from galatea.subject.goals.motives import motive_opportunity, motive_request
from galatea.subject.goals.producers import ProducersBundle, collect_motives_c3
from galatea.subject.action.metacontrol import MetaControlState, MetaTriggers
from galatea.subject.perception.pipeline import PerceptionPipeline
from galatea.subject.sensorium.calibration import bind_calibration
from galatea.subject.sensorium.ingest import CARRIER_INTERO
from galatea.subject.sensorium.pipeline import SensoriumPipeline, audit
from galatea.subject.sensorium.ports import InteroSensations, load_c0_sensorium_profile

__all__ = [
    "C3Scenario", "load_c3_scenario", "C3ArmRecord", "C3Runner", "run_c3_evaluation",
    "c3_divergence_diffs", "c3_observe_diffs", "c3_affective_shares",
]

_EVAL_MASTER_SEED_C3 = b"c3-motivation"
_TRIAL_LABEL = "c3.motivation"
_CARRIER_OUTCOME = "channel.outcome.received.v1"
ARMS: tuple[str, ...] = ("full_priority", "score_only", "ood_full", "clean_full")


@dataclass(frozen=True, slots=True)
class C3Scenario:
    cycles: int
    moves: dict[int, str]
    rests: tuple[int, ...]


def load_c3_scenario(stat_plan_path: Path) -> C3Scenario:
    if not stat_plan_path.is_file():
        raise StatPlanViolation(f"stat plan not found: {stat_plan_path}")
    raw = cast(dict[str, Any], yaml.safe_load(stat_plan_path.read_text(encoding="utf-8")))
    scenario = cast(dict[str, Any], cast(dict[str, Any], raw["stat_plan"])["scenario"])
    moves_raw = cast(dict[str, Any], scenario["moves"])
    return C3Scenario(
        cycles=int(scenario["cycles"]),
        moves={int(k): str(v) for k, v in moves_raw.items()},
        rests=tuple(int(x) for x in cast(list[Any], scenario["rests"])),
    )


@dataclass(frozen=True, slots=True)
class C3ArmRecord:
    run_index: int
    arm: str
    cell_id: str
    seed_hex: str
    rows: tuple[dict[str, Any], ...]     # 逐拍：候选源/front/picked/decision/ood
    formation_counts: tuple[int, int, int]
    kinds_seen: tuple[str, ...]

    @property
    def digest(self) -> str:
        return content_digest({
            "run_index": self.run_index, "arm": self.arm, "seed_hex": self.seed_hex,
            "rows": list(self.rows), "kinds": list(self.kinds_seen),
        })


def _faulted_window(window: list[list[Any]]) -> list[list[Any]]:
    corrupted = [list(row) for row in window]
    corrupted[0][0] = 5.0
    return corrupted


class C3Runner:
    """C3 单 run 四臂运行器（真实流 + 七源生产者 + 仲裁/元决策层）。"""

    def __init__(self, root: Path, tmp_dir: Path) -> None:
        self._root = root
        self._tmp = tmp_dir
        self._m0_path = root / "config" / "profiles" / "m0_mw0.profile.yaml"
        self._profile: MW0Profile = load_profile(self._m0_path)
        self._c1 = load_c1_profile()
        self._c2a = load_c2_affect_profile()
        self._c3 = load_c3_motivation_profile(root / "config/profiles/c3_motivation.profile.yaml")
        self._c0 = load_c0_sensorium_profile()
        self._calibration = bind_calibration(
            root / "config/profiles/c0_sensorium.profile.yaml", self._c0.calibration_version)
        delays = self._profile.params.channel_delay_cycles
        self._time_basis = {
            "channel.exteroceptive.received.v1": int(delays["exteroceptive"]),
            CARRIER_INTERO: int(delays["interoceptive"]),
            "channel.proprioceptive.received.v1": int(delays["proprioceptive"]),
        }
        self._gateway_config = load_gateway_config(
            root / "config/profiles/m0_gateway.profile.yaml",
            root / "config/profiles/f0_action_contract.profile.yaml")
        self._profile_digests: tuple[tuple[str, str], ...] = (
            ("m0_mw0", content_digest(self._m0_path.read_text(encoding="utf-8"))),
            ("c3_motivation", content_digest(
                (root / "config/profiles/c3_motivation.profile.yaml").read_text(encoding="utf-8"))),
            ("c2_affect", content_digest(
                (root / "config/profiles/c2_affect.profile.yaml").read_text(encoding="utf-8"))),
            ("c1_perception_models", content_digest(
                (root / "config/profiles/c1_perception_models.profile.yaml").read_text(encoding="utf-8"))),
        )

    @property
    def profile_digests(self) -> tuple[tuple[str, str], ...]:
        return self._profile_digests

    def run_trial(self, seed: bytes, scenario: C3Scenario, trial_id: str, cell_id: str,
                  arm: str) -> C3ArmRecord:
        if arm not in ARMS:
            raise ValueError(f"unknown arm: {arm!r}")
        trial_dir = self._tmp / re.sub(r"[^A-Za-z0-9_-]", "_", trial_id)
        trial_dir.mkdir(parents=True, exist_ok=True)
        stores = Stores(trial_dir / "stores")
        try:
            registry = Registry(trial_dir / "registry", stores, CycleClock())
            world = MW0World(self._profile.params, RngDirectory(seed, chacha8_block), branch_id="B")
            dynamics = MW0Dynamics(world, self._profile, RngDirectory(seed, chacha8_block), branch_id="B")
            signing_key = derive_signing_key(seed)
            gateway = CapabilityGateway(self._gateway_config, signing_key,
                                        run_id="R", branch_id="B", subject_candidate_id="S")
            bus = ChannelBus(self._profile.params, registry, RngDirectory(seed, chacha8_block),
                             branch_id="B", interventions=InterventionRegistry())
            extero, intero_ch = ExteroceptiveChannel(bus, world), InteroceptiveChannel(bus, world)
            proprio, outcome = ProprioceptiveChannel(bus, world), OutcomeChannel(bus)
            sensorium = SensoriumPipeline(self._c0, self._calibration, self._time_basis)
            perception = PerceptionPipeline(self._c1)
            affect = AffectPipeline(self._c2a)
            meta = MetaControlState()

            ood = arm == "ood_full"
            priority_on = arm != "score_only"

            cmd_seq = 0
            prev_intero: tuple[float, float] | None = None
            prev_e_energy = 0.0
            formation = (0, 0, 0)
            rows: list[dict[str, Any]] = []
            kinds: set[str] = set()

            for delivery in range(scenario.cycles):
                if delivery in scenario.moves:
                    key = f"c3m{cmd_seq}"; cmd_seq += 1
                    _, command = gateway.authorize(
                        ActionIntention(f"i-{key}", "c3-eval", "eval", delivery + 8, None, key),
                        ActionSpec("move", scenario.moves[delivery]),
                        subject_candidate_id="S", run_id="R", branch_id="B", virtual_time=delivery)
                    assert command is not None
                    fact = dynamics.apply(DynCommand(primitive=Primitive.MOVE,
                                                     param=scenario.moves[delivery],
                                                     command_id=command.command_id),
                                          InterventionRegistry(), delivery)
                    outcome.render_and_submit(delivery,
                                              ArtifactRef(digest=world.state_digest(), kind="world_state_ref"),
                                              command.command_id, fact.effective_effect)
                elif delivery in scenario.rests:
                    key = f"c3r{cmd_seq}"; cmd_seq += 1
                    _, command = gateway.authorize(
                        ActionIntention(f"i-{key}", "c3-eval", "eval", delivery + 8, None, key),
                        ActionSpec("rest", None),
                        subject_candidate_id="S", run_id="R", branch_id="B", virtual_time=delivery)
                    assert command is not None
                    fact = dynamics.apply(DynCommand(primitive=Primitive.REST, param=None,
                                                     command_id=command.command_id),
                                          InterventionRegistry(), delivery)
                    outcome.render_and_submit(delivery,
                                              ArtifactRef(digest=world.state_digest(), kind="world_state_ref"),
                                              command.command_id, fact.effective_effect)

                events = dynamics.step()
                truth_ref = ArtifactRef(digest=world.state_digest(), kind="world_state_ref")
                extero.render_and_submit(delivery, truth_ref)
                intero_ch.render_and_submit(delivery, truth_ref, events)
                proprio.render_and_submit(delivery, truth_ref)
                delivered = bus.deliver(delivery)
                packets: list[tuple[Any, str]] = []
                for packet in delivered.packets:
                    if packet.content_type == _CARRIER_OUTCOME:
                        continue
                    blob = registry.get(ArtifactRef(digest=packet.payload_ref.digest, kind="payload")).blob
                    try:
                        json.loads(blob)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
                    text_payload = blob.decode("utf-8")   # REV-0014 R1 教训在案
                    if (ood and delivery % 8 == 0
                            and '"observation_window"' in text_payload):
                        payload = json.loads(text_payload)
                        if "window" in payload:
                            payload["window"] = _faulted_window(payload["window"])
                            text_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
                    packets.append((packet, text_payload))

                e_energy = 1.0 - (prev_intero[0] if prev_intero else 1.0)
                e_integ = 1.0 - (prev_intero[1] if prev_intero else 1.0)
                e_max = max(e_energy, e_integ)
                # MISMATCH 事件阈 = 0.05（Q-L01-08 damage_event_min_delta 同标度——
                # rest 回升 +0.10 触发、move −0.01 不触发；零新常数）
                rising = abs(e_energy - prev_e_energy) >= 0.05 and delivery > 0
                prev_e_energy = e_energy
                affect_out = affect.step(AffectCycleInputs(
                    cycle=delivery,
                    body_energy=prev_intero[0] if prev_intero else None,
                    body_integrity=prev_intero[1] if prev_intero else None))

                cycle_out = sensorium.process_cycle(delivery, packets)
                formation = (formation[0] + len(cycle_out.frames),
                             formation[1] + len(cycle_out.formation_receipts),
                             formation[2] + len(cycle_out.gain_receipts))
                audit(cycle_out.frames, cycle_out.formation_receipts, cycle_out.gain_receipts)
                frames_by_t: dict[int, list[Any]] = {}
                for frame in cycle_out.frames:
                    frames_by_t.setdefault(frame.effective_time, []).append(frame)
                abstain_hit = False
                center_post: float | None = None
                unc_mean: float | None = None
                for t in sorted(frames_by_t):
                    perc = perception.process_window(t, tuple(frames_by_t[t]))
                    abstain_hit = abstain_hit or bool(perc.abstains)
                    if perc.cells:
                        unc_mean = sum(1.0 - c.posterior_present for c in perc.cells) / len(perc.cells)
                        center = next((c.posterior_present for c in perc.cells
                                       if (c.dx, c.dy) == (0, 0)), None)
                        if center is not None:
                            center_post = float(center)
                for f in cycle_out.frames:
                    if f.modality.value == "INTERO" and isinstance(f.features, InteroSensations):
                        prev_intero = (float(f.features.energy_level), float(f.features.integrity_level))

                # —— 七源生产者（冻结映射）——
                from galatea.subject.affect.drives import severity_of
                alert = severity_of(e_max, 0.1)
                sev_alert = None
                if alert is not None and prev_intero is not None:
                    from galatea.subject.affect.drives import HomeostaticAlert
                    from galatea.subject.affect.ports import DriveKind
                    sev_alert = HomeostaticAlert(
                        DriveKind.ENERGY, alert, e_max, "c3.probe", e_max - prev_e_energy)
                from galatea.subject.goals.request import (
                    ExternalRequest, RequesterIdentity, RequestPhrasing)
                req = ExternalRequest(
                    requester=RequesterIdentity.EXPERIMENT_CONTROL_PROXY,
                    phrasing=RequestPhrasing.NEUTRAL, phrasing_text="probe",
                    content_ref=f"req.{delivery}", received_refs=(f"ev.{delivery}",))
                bundle = ProducersBundle(
                    cycle=delivery, alert=sev_alert,
                    affect_proposal=affect_out.motive_proposal,
                    model_error_rising=rising, model_error_refs=(f"pe.{delivery}",),
                    norm_id=None, window_uncertainty=unc_mean)
                motives = collect_motives_c3(
                    bundle,
                    request_motive=motive_request(req, delivery),
                    opportunity_motive=(
                        motive_opportunity(f"aff.{delivery}", center_post, (), delivery)
                        if center_post is not None and center_post >= 0.5 else None))
                kinds.update(m.source_kind.value for m in motives)

                # —— 仲裁（arm 依赖 tie-break）——
                cands = tuple(vector_of(f"cand{i}", m) for i, m in enumerate(motives))
                vec_map = {c.candidate_id: c.vector for c in cands}
                front = arbitrate_candidates(cands, delivery) if cands else None
                picked_cls = "none"
                cid_to_src = {c.candidate_id: c.source_kind.value for c in cands}
                if front is not None and front.picked is not None:
                    if priority_on:
                        picked_cls = cid_to_src[front.picked]
                    else:
                        # 纯分数序：front 内 sum(vector) 最高者（tie 按 id）
                        best = max(front.front, key=lambda cid: (sum(vec_map[cid]), cid))
                        picked_cls = cid_to_src[best]

                # —— metacontrol（OOD 注入臂：abstain → OBSERVE 触发）——
                decision, _switched = meta.step(MetaTriggers(ood_or_abstain_event=abstain_hit),
                                                delivery)
                rows.append({
                    "run_index": _run_index_of(trial_id), "arm": arm, "cycle": delivery,
                    "n_candidates": len(cands), "front_size": len(front.front) if front else 0,
                    "picked_class": picked_cls,
                    "decision": decision,
                    "ood_injected": int(ood and delivery % 8 == 0),
                    "e_max": e_max,
                })

            return C3ArmRecord(
                run_index=_run_index_of(trial_id), arm=arm, cell_id=cell_id,
                seed_hex=seed.hex(), rows=tuple(rows), formation_counts=formation,
                kinds_seen=tuple(sorted(kinds)))
        finally:
            stores.close()
            shutil.rmtree(trial_dir, ignore_errors=True)


def _run_index_of(trial_id: str) -> int:
    try:
        return int(trial_id.split("#")[-1].split(":")[0])
    except ValueError:
        return -1


# ---- 指标纯函数（I1 复算共用） ----

def c3_divergence_diffs(full: tuple[C3ArmRecord, ...],
                        ablated: tuple[C3ArmRecord, ...]) -> tuple[float, ...]:
    """claim 1：共存拍（两臂 front>1）分歧率（full 的 picked ≠ score_only 的 picked 比例）。"""
    out: list[float] = []
    for fa, fb in zip(full, ablated):
        by_a = {int(r["cycle"]): r for r in fa.rows}
        by_b = {int(r["cycle"]): r for r in fb.rows}
        common = sorted(set(by_a) & set(by_b))
        coexist = [c for c in common if int(by_a[c]["front_size"]) > 1]
        if not coexist:
            raise ValueError(f"run #{fa.run_index}: no coexistence arbitration beats")
        diverge = sum(1 for c in coexist
                      if by_a[c]["picked_class"] != by_b[c]["picked_class"])
        out.append(diverge / len(coexist))
    return tuple(out)


def c3_observe_diffs(injected: tuple[C3ArmRecord, ...],
                     clean: tuple[C3ArmRecord, ...]) -> tuple[float, ...]:
    """claim 2：OBSERVE 拍占比差（注入臂 − 干净臂）。"""
    out: list[float] = []
    for fi, fc in zip(injected, clean):
        rate_i = sum(1 for r in fi.rows if r["decision"] == "OBSERVE") / len(fi.rows)
        rate_c = sum(1 for r in fc.rows if r["decision"] == "OBSERVE") / len(fc.rows)
        out.append(rate_i - rate_c)
    return tuple(out)


def c3_affective_shares(full: tuple[C3ArmRecord, ...]) -> tuple[float, ...]:
    """claim 3：AFFECTIVE 被选占比（有候选拍分母；上界判据 < 0.5）。"""
    out: list[float] = []
    for r in full:
        decided = [row for row in r.rows if row["picked_class"] != "none"]
        if not decided:
            raise ValueError(f"run #{r.run_index}: no arbitration picks")
        aff = sum(1 for row in decided if row["picked_class"] == "AFFECTIVE")
        out.append(aff / len(decided))
    return tuple(out)


def _trial_seed(master: bytes, index: int) -> bytes:
    sub = hashlib.sha256(f"{_TRIAL_LABEL}|{index}".encode("utf-8") + master).hexdigest()
    return bytes.fromhex(sub)


def _mechanical_checks(records: tuple[C3ArmRecord, ...]) -> dict[str, bool]:
    full = [r for r in records if r.arm == "full_priority"]
    kinds_ok = any(len(r.kinds_seen) >= 6 for r in full)
    dwell_ok = True
    for r in full:
        last_switch = -100
        last_decision = "ACT"
        for row in r.rows:
            if row["decision"] != last_decision:
                if int(row["cycle"]) - last_switch < 4:
                    dwell_ok = False
                last_switch = int(row["cycle"])
                last_decision = str(row["decision"])
    return {"source_coverage_ge_6_kinds": bool(kinds_ok), "dwell_hysteresis_respected": dwell_ok}


def run_c3_evaluation(
    root: Path, run_dir: Path, tmp_dir: Path, sealed_cells: tuple[Any, ...],
    stat_plan_path: Path, split_digest: str, n_limit: int | None = None,
) -> tuple[tuple[C3ArmRecord, ...], dict[str, bool], str, str, bool]:
    """C3 正式评价编排（四臂 + 机械判据 + I1）。"""
    if n_limit is not None and n_limit <= 0:
        raise ValueError("n_limit must be positive when provided")
    probe_recorder(run_dir)
    plan = load_stat_plan(stat_plan_path)
    claim = next((c for c in plan.claims if c.claim_id == "c3_priority_arbitration_causal"), None)
    if claim is None:
        raise StatPlanViolation("stat plan missing frozen claim c3_priority_arbitration_causal")
    n = claim.n if n_limit is None else min(n_limit, claim.n)
    scenario = load_c3_scenario(stat_plan_path)
    runner = C3Runner(root, tmp_dir)

    stores = Stores(run_dir / "stores")
    try:
        registry = Registry(run_dir / "registry", stores, CycleClock())
        writer = EvidenceWriter(registry)
        writer.add_manifest(RunManifest.create(
            "c3-motivation-sealed-evaluation", _EVAL_MASTER_SEED_C3.hex(), "B",
            runner.profile_digests, plan.digest, split_digest))
        all_records: list[C3ArmRecord] = []
        for p in range(n):
            cell = sealed_cells[p % len(sealed_cells)]
            seed = _trial_seed(_EVAL_MASTER_SEED_C3, p)
            for arm in ARMS:
                record = runner.run_trial(seed, scenario, f"c3.motivation#{p}:{arm}",
                                          cell.cell_id, arm)
                all_records.append(record)
                writer.add("trace", {"record_digest": record.digest,
                                     "run_index": record.run_index, "arm": record.arm,
                                     "cell_id": record.cell_id, "seed_hex": record.seed_hex,
                                     "formation_counts": list(record.formation_counts)})
                for row in record.rows:
                    writer.add("evidence", row)
        mechanical = _mechanical_checks(tuple(all_records))
        shutil.rmtree(tmp_dir, ignore_errors=True)
        shutil.rmtree(run_dir / "scratch", ignore_errors=True)

        full = tuple(r for r in all_records if r.arm == "full_priority")
        vector_digest = _vector_digest(full, tuple(all_records))
        refs = writer.close()

        def _recompute(partitions: dict[str, list[dict[str, Any]]]) -> str:
            by_key: dict[tuple[int, str], list[dict[str, Any]]] = {}
            for row in partitions["evidence"]:
                by_key.setdefault((int(row["run_index"]), str(row["arm"])), []).append(row)
            rebuilt: dict[str, list[C3ArmRecord]] = {arm: [] for arm in ARMS}
            for (idx, arm), rows in sorted(by_key.items()):
                rebuilt[arm].append(C3ArmRecord(
                    run_index=idx, arm=arm, cell_id=f"recomputed:{idx}", seed_hex="",
                    rows=tuple(sorted(rows, key=lambda r: int(r["cycle"]))),
                    formation_counts=(0, 0, 0), kinds_seen=()))
            f = tuple(rebuilt["full_priority"])
            all_r: list[C3ArmRecord] = []
            for arm in ARMS:
                all_r.extend(rebuilt[arm])
            return _vector_digest(f, tuple(all_r))

        report = recompute_i1(registry, refs, _recompute, vector_digest)   # type: ignore[arg-type]
        return (tuple(all_records), mechanical, plan.digest, split_digest, report.match)
    finally:
        stores.close()


def _vector_digest(full: tuple[C3ArmRecord, ...], all_records: tuple[C3ArmRecord, ...]) -> str:
    return content_digest({
        "divergence": list(c3_divergence_diffs(
            full, tuple(r for r in all_records if r.arm == "score_only"))),
        "observe": list(c3_observe_diffs(
            tuple(r for r in all_records if r.arm == "ood_full"),
            tuple(r for r in all_records if r.arm == "clean_full"))),
        "aff_share": list(c3_affective_shares(full)),
    })
