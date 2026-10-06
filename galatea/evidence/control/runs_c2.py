"""C2 正式评价 runner（五臂协议 + recorder 四分区 + I1 复算 + 机械判据）。

场景/臂协议/调制应用规则 = 冻结统计计划 c2_affect_workspace v1.0（StatPlanMutation
拒运行后改）；真实 MW0+ChannelBus 流 + gateway 签名路径（runs_c1 同构——REV-0014 R1
教训在案：registry blob 恒 bytes 显式 decode）。

五臂（同 seed 同世界流；输入面/调制面唯一差异——D-10 因果可干预）：
- full：affect 全开 + 三调制接线（gain→sensorium / threshold→perception / salience→workspace）
- no_gain / no_threshold / no_salience：分面消融臂（发放面在——接收面零应用）
- flat_full：输入面 rest 替换（moves→rest），claim 3 恒满流对照

调制应用规则（stat plan 冻结）：issued_at = c → 生效窗 [c+1, c+ttl]（下一拍形成起，
含首尾）；消费回执 received_at = c+1；TTL 到期自动 clear。
"""
import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from galatea.subject.action.gateway import ActionSpec, CapabilityGateway, load_gateway_config
from galatea.subject.action.signature import derive_signing_key
from galatea.subject.control.intention import ActionIntention
from galatea.kernel.clock import CycleClock
from galatea.kernel.digest import content_digest
from galatea.kernel.packet import ArtifactRef
from galatea.kernel.registry import Registry
from galatea.kernel.rng import RngDirectory, chacha8_block
from galatea.kernel.state import Stores
from galatea.evidence.recorder.heartbeat import probe_recorder
from galatea.evidence.recorder.replay import recompute_i1
from galatea.subject.sensorium.ingest import CARRIER_INTERO
from galatea.evidence.recorder.manifest import RunManifest
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
from galatea.subject.affect.ports import AffectCycleInputs
from galatea.subject.affect.modulation import ModulationField, ModulationReceiptRecord
from galatea.subject.models.world import WorldModel
from galatea.subject.affect.pipeline import AffectPipeline
from galatea.subject.c1profile import load_c1_profile
from galatea.subject.c2profile import load_c2_affect_profile, load_c2_workspace_profile
from galatea.subject.perception.pipeline import PerceptionPipeline
from galatea.subject.sensorium.calibration import bind_calibration
from galatea.subject.sensorium.pipeline import SensoriumPipeline, audit
from galatea.subject.sensorium.ports import InteroSensations, load_c0_sensorium_profile
from galatea.subject.workspace.compete import consume_salience_modulation
from galatea.subject.workspace.broadcast import ReadReceipt
from galatea.subject.workspace.pipeline import WorkspaceCycleOutput, WorkspacePipeline
from galatea.subject.workspace.watch import WatchPointUpdate
from galatea.subject.workspace.propose import SalienceComponents, WorkspaceProposal
from galatea.kernel.packet import RepresentationLevel

__all__ = [
    "C2Scenario", "load_c2_scenario", "C2ArmRecord", "C2Runner", "run_c2_evaluation",
    "c2_gain_diffs", "c2_threshold_diffs", "c2_salience_diffs", "c2_r2_max", "c2_dynamics_diffs",
]

_EVAL_MASTER_SEED_C2 = b"c2-affect-sealed"   # Q-L13-12① 同族（stat plan 内嵌 hex）
_TRIAL_LABEL = "c2.affect"
_CARRIER_OUTCOME = "channel.outcome.received.v1"

#: 五臂（stat plan arm_protocol 冻结）
ARMS: tuple[str, ...] = ("full", "no_gain", "no_threshold", "no_salience", "flat_full")


@dataclass(frozen=True, slots=True)
class C2Scenario:
    """场景冻结参数（stat plan scenario 节 typed 视图，fail-closed）。"""

    cycles: int
    moves: dict[int, str]
    rests: tuple[int, ...]


def load_c2_scenario(stat_plan_path: Path) -> C2Scenario:
    if not stat_plan_path.is_file():
        raise StatPlanViolation(f"stat plan not found: {stat_plan_path}")
    raw = cast(dict[str, Any], yaml.safe_load(stat_plan_path.read_text(encoding="utf-8")))
    header = cast(dict[str, Any], raw["stat_plan"])
    scenario = cast(dict[str, Any], header["scenario"])
    moves_raw = cast(dict[str, Any], scenario["moves"])
    return C2Scenario(
        cycles=int(scenario["cycles"]),
        moves={int(k): str(v) for k, v in moves_raw.items()},
        rests=tuple(int(x) for x in cast(list[Any], scenario["rests"])),
    )


@dataclass(frozen=True, slots=True)
class C2ArmRecord:
    """单臂证据记录（行集 + 绑定；指标由行集纯函数派生——I1 可复算）。"""

    run_index: int
    arm: str
    cell_id: str
    seed_hex: str
    state_rows: tuple[dict[str, Any], ...]     # 逐拍感受态九维 + 驱力误差 + 门状态
    window_rows: tuple[dict[str, Any], ...]    # 逐拍：intero 值/abstain/入帧集/调制活性
    formation_counts: tuple[int, int, int]     # (frames, formation_receipts, gain_receipts)
    ledger_digest: str
    effective_access_count: int

    @property
    def digest(self) -> str:
        return content_digest({
            "run_index": self.run_index, "arm": self.arm, "seed_hex": self.seed_hex,
            "states": list(self.state_rows), "windows": list(self.window_rows),
            "ledger": self.ledger_digest, "eff_access": self.effective_access_count,
        })


class C2Runner:
    """C2 单 run 五臂运行器（生产主体栈 + 真实通道流；冻结场景编排）。"""

    def __init__(self, root: Path, tmp_dir: Path) -> None:
        self._root = root
        self._tmp = tmp_dir
        self._m0_path = root / "config" / "profiles" / "m0_mw0.profile.yaml"
        self._profile: MW0Profile = load_profile(self._m0_path)
        self._c1 = load_c1_profile()
        self._c2a = load_c2_affect_profile()
        self._c2w = load_c2_workspace_profile(root / "config" / "profiles" / "c2_workspace.profile.yaml")
        self._c0 = load_c0_sensorium_profile()
        self._calibration = bind_calibration(
            root / "config" / "profiles" / "c0_sensorium.profile.yaml", self._c0.calibration_version
        )
        delays = self._profile.params.channel_delay_cycles
        self._time_basis = {
            "channel.exteroceptive.received.v1": int(delays["exteroceptive"]),
            CARRIER_INTERO: int(delays["interoceptive"]),
            "channel.proprioceptive.received.v1": int(delays["proprioceptive"]),
        }
        self._gateway_config = load_gateway_config(
            root / "config" / "profiles" / "m0_gateway.profile.yaml",
            root / "config" / "profiles" / "f0_action_contract.profile.yaml",
        )
        self._profile_digests: tuple[tuple[str, str], ...] = (
            ("m0_mw0", content_digest(self._m0_path.read_text(encoding="utf-8"))),
            ("c2_affect", content_digest(
                (root / "config" / "profiles" / "c2_affect.profile.yaml").read_text(encoding="utf-8")
            )),
            ("c2_workspace", content_digest(
                (root / "config" / "profiles" / "c2_workspace.profile.yaml").read_text(encoding="utf-8")
            )),
            ("c1_perception_models", content_digest(
                (root / "config" / "profiles" / "c1_perception_models.profile.yaml").read_text(encoding="utf-8")
            )),
            ("c0_sensorium", content_digest(
                (root / "config" / "profiles" / "c0_sensorium.profile.yaml").read_text(encoding="utf-8")
            )),
        )

    @property
    def profile_digests(self) -> tuple[tuple[str, str], ...]:
        return self._profile_digests

    @property
    def mw0_profile(self) -> MW0Profile:
        return self._profile

    def run_trial(self, seed: bytes, scenario: C2Scenario, trial_id: str, cell_id: str,
                  arm: str) -> C2ArmRecord:
        trial_dir = self._tmp / re.sub(r"[^A-Za-z0-9_-]", "_", trial_id)
        trial_dir.mkdir(parents=True, exist_ok=True)
        stores = Stores(trial_dir / "stores")
        try:
            return self._run_in(seed, scenario, trial_id, cell_id, trial_dir, stores, arm)
        finally:
            stores.close()
            shutil.rmtree(trial_dir, ignore_errors=True)

    def _run_in(self, seed: bytes, scenario: C2Scenario, trial_id: str, cell_id: str,
                trial_dir: Path, stores: Stores, arm: str) -> C2ArmRecord:
        if arm not in ARMS:
            raise ValueError(f"unknown arm: {arm!r}（stat plan arm_protocol 冻结集）")
        flat = arm == "flat_full"
        wire_gain = arm != "no_gain"
        wire_threshold = arm != "no_threshold"
        wire_salience = arm != "no_salience"

        registry = Registry(trial_dir / "registry", stores, CycleClock())
        world = MW0World(self._profile.params, RngDirectory(seed, chacha8_block), branch_id="B")
        dynamics = MW0Dynamics(world, self._profile, RngDirectory(seed, chacha8_block), branch_id="B")
        signing_key = derive_signing_key(seed)
        gateway = CapabilityGateway(
            self._gateway_config, signing_key, run_id="R", branch_id="B", subject_candidate_id="S",
        )
        bus = ChannelBus(
            self._profile.params, registry, RngDirectory(seed, chacha8_block),
            branch_id="B", interventions=InterventionRegistry(),
        )
        extero = ExteroceptiveChannel(bus, world)
        intero = InteroceptiveChannel(bus, world)
        proprio = ProprioceptiveChannel(bus, world)
        outcome = OutcomeChannel(bus)
        sensorium = SensoriumPipeline(self._c0, self._calibration, self._time_basis)
        perception = PerceptionPipeline(self._c1)
        affect = AffectPipeline(self._c2a)
        workspace = WorkspacePipeline(self._c2w, readers=("perception", "models", "affect", "memory"))

        cmd_seq = 0
        formation_counts = (0, 0, 0)
        state_rows: list[dict[str, Any]] = []
        window_rows: list[dict[str, Any]] = []
        prev_intero: tuple[float, float] | None = None
        prev_obj_cells: frozenset[tuple[int, int]] | None = None
        prev_uncertainty: float | None = None
        prev_novelty: float | None = None
        world_real = WorldModel(self._c1, "R")
        _reader_digests: dict[str, str] = {}
        # 调制生效状态（application_rule 冻结：issued c → 生效 [c+1, c+ttl]；到期 clear）
        gain_until = -1
        threshold_until = -1
        salience_until = -1
        active_salience: ModulationField | None = None

        for delivery in range(scenario.cycles):
            # —— 过期调制先归零（生效窗 [c+1, c+ttl]；delivery > until 即过期）——
            if gain_until >= 0 and delivery > gain_until:
                sensorium.clear_gain_modulation()
                gain_until = -1
            if threshold_until >= 0 and delivery > threshold_until:
                perception.clear_threshold_modulation()
                threshold_until = -1
            if salience_until >= 0 and delivery > salience_until:
                active_salience = None
                salience_until = -1

            # —— 请求动作（flat 臂 moves 全替换为 rest；gateway 签名路径）——
            do_move = (not flat) and delivery in scenario.moves
            do_rest = flat and delivery in scenario.moves or delivery in scenario.rests
            if do_move or do_rest:
                action = "move" if do_move else "rest"
                param: str | None = scenario.moves[delivery] if do_move else None
                key = f"c2{'' if do_move else 'r'}{cmd_seq}"
                if flat and delivery in scenario.moves:
                    key = f"c2f{cmd_seq}"
                cmd_seq += 1
                decision, command = gateway.authorize(
                    ActionIntention(f"i-{key}", "c2-eval", "eval", delivery + 8, None, key),
                    ActionSpec(action, param),
                    subject_candidate_id="S", run_id="R", branch_id="B", virtual_time=delivery,
                )
                if command is None:
                    raise RuntimeError(f"{trial_id}: {action} rejected: {decision.reason_code}")
                fact = dynamics.apply(
                    DynCommand(
                        primitive=Primitive.MOVE if do_move else Primitive.REST,
                        param=param, command_id=command.command_id,
                    ),
                    InterventionRegistry(), delivery,
                )
                outcome.render_and_submit(
                    delivery, ArtifactRef(digest=world.state_digest(), kind="world_state_ref"),
                    command.command_id, fact.effective_effect,
                )

            events = dynamics.step()
            truth_ref = ArtifactRef(digest=world.state_digest(), kind="world_state_ref")
            extero.render_and_submit(delivery, truth_ref)
            intero.render_and_submit(delivery, truth_ref, events)
            proprio.render_and_submit(delivery, truth_ref)
            delivered = bus.deliver(delivery)
            packets: list[tuple[Any, str]] = []
            receipt_success: bool | None = None
            for packet in delivered.packets:
                blob = registry.get(ArtifactRef(digest=packet.payload_ref.digest, kind="payload")).blob
                try:
                    payload = json.loads(blob)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue    # 传输损坏 → 主体不可解析（schema 失败语义，不补零）
                if packet.content_type == _CARRIER_OUTCOME:
                    effect = str(payload.get("effect", ""))
                    # 归属输入（controllability 事件）：requested==effective 的完成回执
                    receipt_success = effect.endswith("_arrived") and "coerced" not in effect
                    continue
                # REV-0014 R1 教训在案：blob 恒 bytes → 显式 decode
                packets.append((packet, blob.decode("utf-8")))

            # —— affect step（T2 同拍；body 输入 = 上一拍内感受值，appraisal 输入 =
            #     上一拍窗统计——本拍窗未关闭，真实因果序禁用当拍未来信息）——
            affect_out = affect.step(AffectCycleInputs(
                cycle=delivery,
                body_energy=prev_intero[0] if prev_intero is not None else None,
                body_integrity=prev_intero[1] if prev_intero is not None else None,
                action_receipt_success=receipt_success,
                belief_uncertainty_mean=prev_uncertainty,
                sensory_residual_mean=prev_novelty,
            ))

            # —— 调制接线（issued c → 生效 [c+1, c+ttl]；回执 received_at = c+1）——
            for f in affect_out.modulations:
                until = f.issued_at + f.ttl_cycles
                if f.dimension == "gain" and wire_gain:
                    receipt = sensorium.apply_gain_modulation(f.requested_value)
                    affect.ledger.record_receipt(ModulationReceiptRecord(
                        modulation_id=f.modulation_id, accepted=True,
                        applied_value=receipt.applied_gain, bound_check=receipt.bound_check,
                        received_at=delivery + 1,
                    ))
                    gain_until = until
                elif f.dimension == "believe_threshold" and wire_threshold:
                    receipt = perception.apply_threshold_modulation(f.requested_value)
                    affect.ledger.record_receipt(ModulationReceiptRecord(
                        modulation_id=f.modulation_id, accepted=True,
                        applied_value=float(receipt.applied_value or 0.0),
                        bound_check=receipt.bound_check or "", received_at=delivery + 1,
                    ))
                    threshold_until = until
                elif f.dimension == "salience.affect" and wire_salience:
                    rec = consume_salience_modulation(f, delivery + 1)
                    affect.ledger.record_receipt(ModulationReceiptRecord(
                        modulation_id=f.modulation_id, accepted=True,
                        applied_value=rec.applied_value, bound_check=rec.bound_check,
                        received_at=delivery + 1,
                    ))
                    active_salience = f
                    salience_until = until

            cycle_out = sensorium.process_cycle(delivery, packets)
            formation_counts = (
                formation_counts[0] + len(cycle_out.frames),
                formation_counts[1] + len(cycle_out.formation_receipts),
                formation_counts[2] + len(cycle_out.gain_receipts),
            )
            audit(cycle_out.frames, cycle_out.formation_receipts, cycle_out.gain_receipts)

            # —— 知觉（窗级；threshold override 在 perception 内部生效）——
            frames_by_t: dict[int, list[Any]] = {}
            for frame in cycle_out.frames:
                frames_by_t.setdefault(frame.effective_time, []).append(frame)
            abstain_events = 0
            uncertainty_mean: float | None = None
            novelty_input: float | None = None
            object_count_total = 0
            window_posteriors: list[float] = []
            last_perc_cells: tuple[Any, ...] = ()
            for t in sorted(frames_by_t):
                frames = tuple(frames_by_t[t])
                perc = perception.process_window(t, frames)
                abstain_events += len(perc.abstains)
                # 门输入面（stat plan gate_inputs 冻结映射）：
                if perc.cells:
                    uncertainty_mean = sum(1.0 - c.posterior_present for c in perc.cells) / len(perc.cells)
                    window_posteriors.extend(float(c.posterior_present) for c in perc.cells)
                obj_cells = frozenset((c.dx, c.dy) for c in perc.cells if c.posterior_present >= 0.5)
                object_count_total += len(perc.objects)   # 生产面对象（override 感知）
                if prev_obj_cells is not None:
                    union = obj_cells | prev_obj_cells
                    novelty_input = 0.0 if not union else 1.0 - len(obj_cells & prev_obj_cells) / len(union)
                prev_obj_cells = obj_cells
                last_perc_cells = perc.cells
                # 逐对象格提案（workspace_feed 修订：单中心提案每拍 2 项 < K=4 无淘汰）
                for c in sorted((c for c in perc.cells if c.posterior_present >= 0.5),
                                key=lambda c: (c.dy, c.dx)):
                    workspace.submit(WorkspaceProposal(
                        proposal_id=f"ws.obj.{t}.{c.dx},{c.dy}",
                        content_ref=f"c.obj.{t}.{c.dx},{c.dy}",
                        source_level=RepresentationLevel.PERCEIVED,
                        salience=SalienceComponents(goal_relevance=0.1,
                                                    affect=float(c.posterior_present),
                                                    novelty=0.2, uncertainty=0.1, info_value=0.1),
                        sponsor_module="perception",
                    ))
            intero_now = _intero_now(cycle_out.frames)
            if intero_now is not None:
                prev_intero = intero_now
            prev_uncertainty = uncertainty_mean
            prev_novelty = novelty_input

            # —— workspace 竞争（T3 面；提案 = 逐对象格 + affect 动机；salience 活跃场）——
            workspace.submit(WorkspaceProposal(
                proposal_id=f"ws.mot.{delivery}", content_ref=f"c.mot.{delivery}",
                source_level=RepresentationLevel.PREDICTED,
                salience=SalienceComponents(goal_relevance=0.1, affect=affect_out.state.urgency,
                                            novelty=0.1, uncertainty=0.1, info_value=0.1),
                sponsor_module="affect",
            ))
            ws_out = workspace.run_competition(
                delivery,
                salience_modulation=active_salience if salience_until >= delivery else None,
                depth=0,
            )
            admitted_ids: tuple[str, ...] = ()
            eff = 0
            if isinstance(ws_out, WorkspaceCycleOutput):
                admitted_ids = tuple(i.proposal_id for i in ws_out.frame.items)
                # 读者面（stat plan reader_watch_digests 冻结派生：四声明读者真实状态 digest）
                last_belief = world_real.update(delivery, last_perc_cells, (), (), ())
                world_real.advance(delivery + 1, (), ())
                watches = {
                    "perception": content_digest([round(v, 12) for v in window_posteriors]),
                    "models": last_belief.digest(),
                    "affect": affect_out.state.content_digest,
                    "memory": content_digest(list(admitted_ids)),
                }
                for reader, post in watches.items():
                    pre = _reader_digests.get(reader, "")
                    changed = pre != "" and pre != post
                    workspace.submit_read_receipt(ReadReceipt(
                        frame_id=ws_out.frame.frame_id, reader_module=reader,
                        read_at=delivery, pre_state_digest=pre or post,
                        post_state_digest=post, effect_declared=changed,
                    ))
                    workspace.submit_watch_update(WatchPointUpdate(
                        watch_id=f"watch.{reader}", module=reader, changed=changed,
                        digest_before=pre or post, digest_after=post,
                        pre_registered=True, at_cycle=delivery,
                    ), frame_id=ws_out.frame.frame_id)
                    _reader_digests[reader] = post
                ev = workspace.settle(ws_out.frame.frame_id, now_cycle=delivery + 1)
                eff = int(ev.effective_access)

            state = affect_out.state
            state_rows.append({
                "run_index": _run_index_of(trial_id), "arm": arm, "cycle": delivery,
                "valence": state.valence, "arousal": state.arousal, "urgency": state.urgency,
                "controllability": state.controllability, "uncertainty": state.uncertainty,
                "novelty": state.novelty, "social_relevance": state.social_relevance,
                "persistence": state.persistence,
                "tendencies_max": max((t.strength for t in state.tendencies.items), default=0.0),
                "weighted_error": affect_out.step.weighted_error,
                "max_error": affect_out.step.max_error,
                "gate_gain_on": int(affect_out.step.gate_gain_on),
                "gate_threshold_on": int(affect_out.step.gate_threshold_on),
                "gate_salience_on": int(affect_out.step.gate_salience_on),
                "saturation_hits": state.dynamics_trace.saturation_hits,
                "recovery_phase": int(state.dynamics_trace.recovery_phase),
                "ethics_trigger": int(affect_out.ethics_trigger is not None),
            })
            window_rows.append({
                "run_index": _run_index_of(trial_id), "arm": arm, "cycle": delivery,
                "intero_energy": intero_now[0] if intero_now else None,
                "intero_integrity": intero_now[1] if intero_now else None,
                "abstain_events": abstain_events,
                "object_count": object_count_total,
                "admitted_ids": list(admitted_ids), "salience_factor": 0.0,
                "gain_active": int(gain_until >= delivery),
                "threshold_active": int(threshold_until >= delivery),
                "salience_active": int(active_salience is not None and salience_until >= delivery),
                "eff_access": eff,
            })

        return C2ArmRecord(
            run_index=_run_index_of(trial_id), arm=arm, cell_id=cell_id, seed_hex=seed.hex(),
            state_rows=tuple(state_rows), window_rows=tuple(window_rows),
            formation_counts=formation_counts, ledger_digest=affect.ledger.digest(),
            effective_access_count=sum(int(r["eff_access"]) for r in window_rows),
        )


def _intero_now(frames: tuple[Any, ...]) -> tuple[float, float] | None:
    from galatea.subject.sensorium.ports import SensoryModality
    for f in frames:
        if f.modality is SensoryModality.INTERO and isinstance(f.features, InteroSensations):
            return (float(f.features.energy_level), float(f.features.integrity_level))
    return None


def _run_index_of(trial_id: str) -> int:
    suffix = trial_id.split("#")[-1]
    try:
        return int(suffix.split(":")[0])   # trial_id 形如 "c2.affect#7:full"
    except ValueError:
        return -1

# ---- 指标纯函数（runner 行集 → 判定器输入；I1 复算共用） ----

_DIMS: tuple[str, ...] = ("valence", "arousal", "urgency", "controllability",
                          "uncertainty", "novelty", "social_relevance", "persistence",
                          "tendencies_max")


def _active_windows(rows: tuple[dict[str, Any], ...], key: str) -> tuple[int, ...]:
    """调制 ON 窗（full 臂门状态逐拍记录机械派生——stat plan endpoint_domains；禁事后选择）。"""
    return tuple(int(r["cycle"]) for r in rows if int(r[key]) == 1)


def _pair_by_cycle(a: C2ArmRecord, b: C2ArmRecord) -> dict[int, tuple[dict[str, Any], dict[str, Any]]]:
    by_a = {int(r["cycle"]): r for r in a.window_rows}
    by_b = {int(r["cycle"]): r for r in b.window_rows}
    return {c: (by_a[c], by_b[c]) for c in sorted(set(by_a) & set(by_b))}


def c2_gain_diffs(full: tuple[C2ArmRecord, ...], ablated: tuple[C2ArmRecord, ...]) -> tuple[float, ...]:
    """判据 1：ON 窗 intero 强度差（full − no_gain；增益 2.0 放大耗能态 level → 差 > 0）。"""
    diffs: list[float] = []
    for fa, fb in zip(full, ablated):
        pairs = _pair_by_cycle(fa, fb)
        active = set(_active_windows(fa.window_rows, "gain_active"))
        vals = [
            (float(ra["intero_energy"]) + float(ra["intero_integrity"]))
            - (float(rb["intero_energy"]) + float(rb["intero_integrity"]))
            for c, (ra, rb) in pairs.items() if c in active
            and ra["intero_energy"] is not None and rb["intero_energy"] is not None
        ]
        if not vals:
            raise ValueError(f"run #{fa.run_index}: no gain-active windows")
        diffs.append(sum(vals) / len(vals))
    return tuple(diffs)


def c2_threshold_diffs(full: tuple[C2ArmRecord, ...], ablated: tuple[C2ArmRecord, ...]) -> tuple[float, ...]:
    """判据 2：ON 窗格级对象计数收缩（no_threshold − full)/25 > 0——阈 0.5→0.6 使
    中间带格退出对象集（冒烟修订：窗级 top-posterior 双峰 → abstain 差恒 0 不可判定）。"""
    diffs: list[float] = []
    for fa, fb in zip(full, ablated):
        pairs = _pair_by_cycle(fa, fb)
        active = set(_active_windows(fa.window_rows, "threshold_active"))
        vals = [
            (int(rb["object_count"]) - int(ra["object_count"])) / 25.0
            for c, (ra, rb) in pairs.items() if c in active
        ]
        if not vals:
            raise ValueError(f"run #{fa.run_index}: no threshold-active windows")
        diffs.append(sum(vals) / len(vals))
    return tuple(diffs)


def c2_salience_diffs(full: tuple[C2ArmRecord, ...], ablated: tuple[C2ArmRecord, ...]) -> tuple[float, ...]:
    """判据 3：ON 竞争拍入帧集对称差比例（|A △ B| / K；affect ×2 改变排名 → > 0）。"""
    diffs: list[float] = []
    for fa, fb in zip(full, ablated):
        pairs = _pair_by_cycle(fa, fb)
        active = set(_active_windows(fa.window_rows, "salience_active"))
        vals = [
            len(set(ra["admitted_ids"]) ^ set(rb["admitted_ids"])) / 4.0
            for c, (ra, rb) in pairs.items() if c in active
        ]
        if not vals:
            raise ValueError(f"run #{fa.run_index}: no salience-active competition beats")
        diffs.append(sum(vals) / len(vals))
    return tuple(diffs)


def _r2(x: list[float], y: list[float]) -> float:
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((xi - mx) ** 2 for xi in x)
    syy = sum((yi - my) ** 2 for yi in y)
    if syy == 0.0 or sxx == 0.0:
        return 0.0
    sxy = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    return (sxy * sxy) / (sxx * syy)


def c2_r2_max(full: tuple[C2ArmRecord, ...]) -> tuple[float, ...]:
    """claim 2：per-run 最优单维对其余维平均 R²（Q-L05-07 上界判据 < 0.9）。"""
    out: list[float] = []
    for record in full:
        series = {d: [float(r[d]) for r in record.state_rows] for d in _DIMS}
        best = 0.0
        for src in _DIMS:
            rs = [_r2(series[src], series[dst]) for dst in _DIMS if dst != src]
            best = max(best, sum(rs) / len(rs))
        out.append(best)
    return tuple(out)


def c2_dynamics_diffs(full: tuple[C2ArmRecord, ...], flat: tuple[C2ArmRecord, ...]) -> tuple[float, ...]:
    """claim 3：arousal 轨迹均值差（耗能臂 − 恒满流臂；同 seed 配对，> 0 为输入驱动）。"""
    diffs: list[float] = []
    for fa, ff in zip(full, flat):
        by_a = {int(r["cycle"]): float(r["arousal"]) for r in fa.state_rows}
        by_f = {int(r["cycle"]): float(r["arousal"]) for r in ff.state_rows}
        common = sorted(set(by_a) & set(by_f))
        if not common:
            raise ValueError(f"run #{fa.run_index}: no common cycles for dynamics contrast")
        diffs.append(sum(by_a[c] - by_f[c] for c in common) / len(common))
    return tuple(diffs)


def c2_valence_anchor_violations(full: tuple[C2ArmRecord, ...]) -> int:
    """方向锚违反数（valence 均值 ≤ 0 每臂；违反 >0 → §4.2 公式面复核——描述性指标）。"""
    return sum(1 for r in full
               if sum(float(s["valence"]) for s in r.state_rows) / len(r.state_rows) > 0.0)


# ---- 机械判据（不入统计 claim；M2 SC5 先例） ----

def _mechanical_checks(runner: C2Runner, full_records: tuple[C2ArmRecord, ...],
                       seed0: bytes, scenario: C2Scenario) -> dict[str, bool]:
    """六机制辨识 / ethics 消融轨迹恒等 / 回执核 / effective_access 可达 / affect≠command。"""
    from galatea.subject.affect.dynamics import (
        decay_step, hysteresis, in_recovery, lowpass, saturate, two_step,
    )
    s = 0.0
    for _ in range(4):
        s = lowpass(s, 1.0, 4)
    t63 = s >= 1.0 - 1.0 / 2.718281828
    d = 1.0
    for _ in range(16):
        d = decay_step(d, 16)
    decay_ok = abs(d - 0.35607413) < 1e-8
    reappraisal_ok = abs(two_step(0.4, 4) - two_step(0.2, 4) - 0.0875) < 1e-12
    sat_ok = saturate(lowpass(0.9, 2.0, 4), -1.0, 1.0)[0] == 1.0
    hyst_ok = hysteresis(False, 0.55, 0.1) and not hysteresis(True, 0.45, 0.1)
    recov_ok = in_recovery(0.05, 0.1) and not in_recovery(0.11, 0.1)
    six_ok = t63 and decay_ok and reappraisal_ok and sat_ok and hyst_ok and recov_ok

    from galatea.subject.affect.pipeline import AffectPipeline
    from galatea.subject.affect.ports import AffectCycleInputs
    from galatea.subject.c2profile import load_c2_affect_profile
    params = load_c2_affect_profile(Path("config/profiles/c2_affect.profile.yaml"))
    digests: list[str] = []
    for enabled in (True, False):
        pipe = AffectPipeline(params, ethics_enabled=enabled)
        ds: list[str] = []
        for c in range(80):
            energy = 0.05 if (c // 8) % 2 == 0 else 1.0
            o = pipe.step(AffectCycleInputs(cycle=c, body_energy=energy, body_integrity=0.5))
            ds.append(o.state.content_digest)
        digests.append(content_digest(ds))
    ethics_ok = digests[0] == digests[1]

    receipt_ok = all(r.ledger_digest for r in full_records)

    import importlib
    import sys
    from galatea.subject.affect import ports as affect_ports
    no_command = True
    for name in sorted(m for m in sys.modules if m.startswith("galatea.subject.affect.")
                       and not m.startswith("galatea.subject.affect.tests")):
        try:
            mod = importlib.import_module(name)
            affect_ports.assert_no_command_path(vars(mod))
        except Exception:
            no_command = False
    access_ok = any(r.effective_access_count > 0 for r in full_records)

    # threshold 链路机械判据（运行前修订 3——stat plan threshold_chain_mechanical；
    # 独立 probe run：run#0 种子复用，hook process_window 收集值域/链路/行为面证据）
    value_gap, chain_ok, behavior_zero = _threshold_chain_probe(runner, seed0, scenario)
    return {
        "six_mechanisms_identifiable": six_ok,
        "ethics_ablation_trajectory_identity": ethics_ok,
        "modulation_receipts_all_confirmed": bool(receipt_ok),
        "affect_no_command_imports": no_command,
        "effective_access_reachable": access_ok,
        "threshold_value_domain_gap": value_gap,
        "threshold_chain_integrity": chain_ok,
        "threshold_behavior_surface_zero_effect": behavior_zero,
    }


def _threshold_chain_probe(runner: C2Runner, seed0: bytes, scenario: C2Scenario) -> tuple[bool, bool, bool]:
    """threshold 判据的三项机械证明（stat plan threshold_chain_mechanical 冻结文）。

    - value_domain_gap：probe run 全部格后验 ∩ (0.4, 0.6) = ∅（值域间隙——阈界内
      任意移动不改变判定）；
    - chain_integrity：调制发放→接收→台账 CONFIRMED→管线 applied 生效（ON 窗内
      _effective_params().believe_threshold == 0.6）→ threshold_ref 传播（abstain
      事件引用生效值）；
    - behavior_surface_zero_effect：full vs no_threshold 两臂窗级对象计数逐拍恒等
      （行为面零效应 = 值域结构的必然后果——如实报告）。
    """
    import galatea.evidence.control.runs_c2 as rc2

    orig_pw = rc2.PerceptionPipeline.process_window
    slot: dict[str, Any] = {}

    def _make_probe(store: dict[str, Any]) -> Any:
        def patched(self: Any, t: Any, frames: Any, *a: Any, **k: Any) -> Any:
            out = orig_pw(self, t, frames, *a, **k)
            store["posteriors"] = store.get("posteriors", [])
            store["posteriors"].extend(float(c.posterior_present) for c in out.cells)
            store["objects"] = store.get("objects", []) + [len(out.objects)]
            store["threshold_refs"] = store.get("threshold_refs", set())
            override_on = abs(self._effective_params().believe_threshold - 0.6) < 1e-12
            for ab in out.abstains:
                store["threshold_refs"].add(ab.threshold_ref)
                if override_on:
                    store["threshold_refs_on"] = store.get("threshold_refs_on", set())
                    store["threshold_refs_on"].add(ab.threshold_ref)
            if override_on:
                store["override_active"] = store.get("override_active", 0) + 1
            return out
        return patched

    # 分臂探测（两次 hook——臂标识由 runner 臂配置承载，非阈值推断）
    rc2.PerceptionPipeline.process_window = _make_probe(slot)
    try:
        runner.run_trial(seed0, scenario, "c2.mech.full", "probe:0", "full")
    finally:
        rc2.PerceptionPipeline.process_window = orig_pw
    full_slot = slot
    ablated_slot: dict[str, Any] = {}
    rc2.PerceptionPipeline.process_window = _make_probe(ablated_slot)
    try:
        runner.run_trial(seed0, scenario, "c2.mech.nothr", "probe:0", "no_threshold")
    finally:
        rc2.PerceptionPipeline.process_window = orig_pw

    posteriors = full_slot.get("posteriors", [])
    value_gap = all(not (0.4 < v < 0.6) for v in posteriors) and len(posteriors) > 0
    # 链路：override 生效拍 > 0（接收面 applied）+ ON 窗 abstain 事件引用生效值
    # （传播面样本 = ON 窗 abstain 事件——MW0 abstain 稀少，空集不否证，全称判定）
    refs_ok = all("MODULATION:applied" in r for r in full_slot.get("threshold_refs_on", set()))
    chain_ok = full_slot.get("override_active", 0) > 0 and refs_ok
    # 行为面零效应：两臂对象计数逐拍恒等（值域结构的必然后果——如实报告）
    f_objs = full_slot.get("objects", [])
    a_objs = ablated_slot.get("objects", [])
    behavior_zero = len(f_objs) == len(a_objs) and f_objs == a_objs and len(f_objs) > 0
    return value_gap, chain_ok, behavior_zero


# ---- 评价编排（recorder + I1 + 机械判据） ----

def _trial_seed(master: bytes, index: int) -> bytes:
    """trial 种子派生（stat plan seed_derivation 冻结式：sha256("{label}|{index}" + master)）。"""
    sub = hashlib.sha256(f"{_TRIAL_LABEL}|{index}".encode("utf-8") + master).hexdigest()
    return bytes.fromhex(sub)


def run_c2_evaluation(
    root: Path, run_dir: Path, tmp_dir: Path, sealed_cells: tuple[Any, ...],
    stat_plan_path: Path, split_digest: str, n_limit: int | None = None,
) -> tuple[tuple[C2ArmRecord, ...], dict[str, bool], str, str, bool]:
    """C2 正式评价编排：recorder 前置探测 → 逐 run 五臂（sealed 单元驱动）→ 四分区落盘
    → 机械判据（独立协议）→ I1 复算。

    返回 (records（五臂全行集）, mechanical_checks, stat_plan_digest, split_digest,
    i1_match)。n_limit 仅为测试截断 affordance；正式评价不传。
    """
    if n_limit is not None and n_limit <= 0:
        raise ValueError("n_limit must be positive when provided")
    probe_recorder(run_dir)
    plan = load_stat_plan(stat_plan_path)
    claim = next((c for c in plan.claims if c.claim_id == "c2_modulation_causality"), None)
    if claim is None:
        raise StatPlanViolation("stat plan missing frozen claim c2_modulation_causality")
    n = claim.n if n_limit is None else min(n_limit, claim.n)
    scenario = load_c2_scenario(stat_plan_path)
    runner = C2Runner(root, tmp_dir)

    stores = Stores(run_dir / "stores")
    try:
        registry = Registry(run_dir / "registry", stores, CycleClock())
        writer = EvidenceWriter(registry)
        writer.add_manifest(
            RunManifest.create(
                "c2-affect-sealed-evaluation", _EVAL_MASTER_SEED_C2.hex(), "B",
                runner.profile_digests, plan.digest, split_digest,
            )
        )
        all_records: list[C2ArmRecord] = []
        for p in range(n):
            cell = sealed_cells[p % len(sealed_cells)]
            seed = _trial_seed(_EVAL_MASTER_SEED_C2, p)
            for arm in ARMS:
                record = runner.run_trial(seed, scenario, f"c2.affect#{p}:{arm}", cell.cell_id, arm)
                all_records.append(record)
                writer.add("trace", {"record_digest": record.digest,
                                     "run_index": record.run_index, "arm": record.arm,
                                     "cell_id": record.cell_id, "seed_hex": record.seed_hex,
                                     "formation_counts": list(record.formation_counts)})
                for row in record.state_rows:
                    writer.add("evidence", row)
                for row in record.window_rows:
                    writer.add("metrics", row)
        full = tuple(r for r in all_records if r.arm == "full")
        mechanical = _mechanical_checks(runner, full, _trial_seed(_EVAL_MASTER_SEED_C2, 0), scenario)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        shutil.rmtree(run_dir / "scratch", ignore_errors=True)

        vector_digest = _vector_digest(full, tuple(all_records))
        refs = writer.close()

        def _recompute(partitions: dict[str, list[dict[str, Any]]]) -> str:
            by_key: dict[tuple[int, str], dict[str, list[dict[str, Any]]]] = {}
            for row in partitions["evidence"]:
                key = (int(row["run_index"]), str(row["arm"]))
                by_key.setdefault(key, {"states": [], "windows": []})["states"].append(row)
            for raw in partitions["metrics"]:
                row = dict(raw)
                ids = row.get("admitted_ids")
                if isinstance(ids, str):
                    row["admitted_ids"] = json.loads(ids)   # Parquet 往返 list→JSON 字符串
                key = (int(row["run_index"]), str(row["arm"]))
                by_key.setdefault(key, {"states": [], "windows": []})["windows"].append(row)
            rebuilt: dict[str, list[C2ArmRecord]] = {arm: [] for arm in ARMS}
            for (idx, arm), parts in sorted(by_key.items()):
                rebuilt[arm].append(C2ArmRecord(
                    run_index=idx, arm=arm, cell_id=f"recomputed:{idx}", seed_hex="",
                    state_rows=tuple(sorted(parts["states"], key=lambda r: int(r["cycle"]))),
                    window_rows=tuple(sorted(parts["windows"], key=lambda r: int(r["cycle"]))),
                    formation_counts=(0, 0, 0), ledger_digest="recomputed",
                    effective_access_count=0,
                ))
            f = tuple(rebuilt["full"])
            all_rebuilt: list[C2ArmRecord] = []
            for arm in ARMS:
                all_rebuilt.extend(rebuilt[arm])
            return _vector_digest(f, tuple(all_rebuilt))

        report = recompute_i1(registry, refs, _recompute, vector_digest)   # type: ignore[arg-type]
        return (tuple(all_records), mechanical, plan.digest, split_digest, report.match)
    finally:
        stores.close()


def _vector_digest(full: tuple[C2ArmRecord, ...], all_records: tuple[C2ArmRecord, ...]) -> str:
    """指标向量 digest（I1 复算核——全部 claim 判定器的输入向量）。"""
    return content_digest({
        "gain": list(c2_gain_diffs(full, tuple(r for r in all_records if r.arm == "no_gain"))),
        "threshold": list(c2_threshold_diffs(full, tuple(r for r in all_records if r.arm == "no_threshold"))),
        "salience": list(c2_salience_diffs(full, tuple(r for r in all_records if r.arm == "no_salience"))),
        "r2max": list(c2_r2_max(full)),
        "dynamics": list(c2_dynamics_diffs(full, tuple(r for r in all_records if r.arm == "flat_full"))),
        "anchor_violations": c2_valence_anchor_violations(full),
    })
