"""C4 正式评价 runner（stat plan c4_action_social v1.0 冻结场景；顺延终止条款第五次执行承载）。

臂结构（同 seed 同世界流——差异唯一来源 = 冻结干预面，D-10）：
- battery            六条件 mini-trial（clean/blocked/no_op/sham/fault/uncommanded）→ 概率 agency
- eff_full/eff_ablated   EfferenceCopy 因果（消融 = 不发副本 → 预测不发布 → 轴 3 = None）
- switch_full/switch_clean   REV-0018 R3 切换面扩展（SEEK_HELP/ABANDON/OBSERVE）
- switch_langtwin    run 0 机械判据专用（陈述注入后知觉后验逐位不变，Q-L12-06①）

轴 3（outcome_predicted）操作化（冻结文本"实现轴 = 模型预测非内容对拍"）：
- 命令已授权且副本已发：move 积分预测 vs 持续预测对形成后窗残差比较（积分更优 = Y）；
- 命令被 gateway 类型化拒绝（blocked 型）：命令后果未发生（拒绝主体可见）→ False；
- 无命令提交（uncommanded）：无积分预测（持续预期被世界违反）→ False；
- 消融臂：授权但副本缺席 → None（证据缺失 → UNKNOWN(INSUFFICIENT)，禁补默认）。

blocked 窗实现 = gateway 冻结八检查的 deadline 拒绝面（过期 deadline → DEADLINE_EXPIRED
类型化拒绝；零新机制——blocked 在 M0 冻结语义中经 gateway 检查面显形）。
"""
from __future__ import annotations

import hashlib
import json
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
from galatea.evidence.control.recording import load_recording
from galatea.evidence.recorder.heartbeat import probe_recorder
from galatea.evidence.recorder.manifest import RunManifest
from galatea.evidence.recorder.replay import recompute_i1
from galatea.evidence.recorder.writer import EvidenceWriter
from galatea.evidence.evaluator.statplan import StatPlanViolation, load_stat_plan
from galatea.env.channels.adapter import ChannelBus
from galatea.env.channels.extero import ExteroceptiveChannel
from galatea.env.channels.intero import InteroceptiveChannel
from galatea.env.channels.language_stub import LanguageStubChannel
from galatea.env.channels.outcome import OutcomeChannel
from galatea.env.channels.proprio import ProprioceptiveChannel
from galatea.env.interventions.registry import InterventionRegistry
from galatea.env.profile import MW0Profile, load_profile
from galatea.env.world.dynamics import Command as DynCommand
from galatea.env.world.dynamics import MW0Dynamics
from galatea.env.world.mw0 import MW0World, Primitive
from galatea.subject.action.attribution import AttributionAxes, attribute_action
from galatea.subject.action.efference import issue_efference_copy
from galatea.subject.action.gateway import ActionSpec, CapabilityGateway, load_gateway_config
from galatea.subject.action.metacontrol import MetaControlState, MetaTriggers
from galatea.subject.action.signature import derive_signing_key
from galatea.subject.control.intention import ActionIntention
from galatea.subject.c1profile import load_c1_profile
from galatea.subject.c4profile import load_c4_action_social_profile
from galatea.subject.goals.candidates import GoalCandidate, SettleCriterion
from galatea.subject.goals.checklist import (
    ChecklistInputs,
    ViabilityEstimate,
    default_profile_path,
    load_m1_goals_profile,
    run_checklist,
)
from galatea.subject.goals.lifecycle import GoalLifecycle
from galatea.subject.goals.motives import Motive, MotiveSource
from galatea.subject.goals.ports import SettlePredicate
from galatea.subject.language.help import seek_help_utterance
from galatea.subject.language.parse import parse_language_frame
from galatea.subject.language.replay import ReplayStore
from galatea.subject.models.prediction import predict_window
from galatea.subject.models.world import WorldModel
from galatea.subject.perception.pipeline import PerceptionPipeline
from galatea.subject.sensorium.calibration import bind_calibration
from galatea.subject.sensorium.ingest import (
    CARRIER_EXTERO,
    CARRIER_INTERO,
    CARRIER_LANGUAGE,
    CARRIER_PROPRIO,
)
from galatea.subject.sensorium.pipeline import SensoriumPipeline, audit
from galatea.subject.sensorium.ports import ExtLocalObsFeatures, load_c0_sensorium_profile

_EVAL_MASTER_SEED_C4 = bytes.fromhex("63342d616374696f6e2d736f6369616c")   # Q-L13-12④ 内嵌
_CARRIER_OUTCOME = "channel.outcome.received.v1"
_BATTERY_CONDITIONS = ("clean", "blocked", "no_op", "sham", "fault", "uncommanded")
_ARMS: tuple[str, ...] = ("battery", "eff_full", "eff_ablated", "switch_full", "switch_clean", "switch_langtwin")


def _faulted_window(window: list[list[Any]]) -> list[list[Any]]:
    """OOD 注入（runs_c3 同构：窗首元素推高出定义域 → 知觉域出）。"""
    w = [list(row) for row in window]
    w[0][0] = 5.0
    return w


def _trial_seed(master: bytes, index: int) -> bytes:
    return hashlib.sha256(f"c4.social|{index}".encode("utf-8") + master).digest()


@dataclass(frozen=True, slots=True)
class C4ArmRecord:
    """单臂运行记录（summary 全 JSON 化供 I1 复算）。"""

    run_index: int
    arm: str
    cell_id: str
    seed_hex: str
    summary: dict[str, Any]
    formation_counts: tuple[int, int, int]

    @property
    def digest(self) -> str:
        return content_digest(json.dumps(self.summary, sort_keys=True, separators=(",", ":")))


class C4Runner:
    """C4 试验台（profiles 全部经冻结 typed loader；INC-11）。"""

    def __init__(self, root: Path, tmp_dir: Path) -> None:
        self._root = root
        self._tmp = tmp_dir
        self._m0_path = root / "config" / "profiles" / "m0_mw0.profile.yaml"
        self._profile: MW0Profile = load_profile(self._m0_path)
        self._c1 = load_c1_profile()
        self._c0 = load_c0_sensorium_profile()
        self._c4 = load_c4_action_social_profile()
        self._calibration = bind_calibration(
            root / "config" / "profiles" / "c0_sensorium.profile.yaml", self._c0.calibration_version
        )
        delays = self._profile.params.channel_delay_cycles
        self._time_basis = {
            CARRIER_EXTERO: int(delays["exteroceptive"]),
            CARRIER_INTERO: int(delays["interoceptive"]),
            CARRIER_PROPRIO: int(delays["proprioceptive"]),
            CARRIER_LANGUAGE: int(delays["language"]),
        }
        self._gateway_config = load_gateway_config(
            root / "config" / "profiles" / "m0_gateway.profile.yaml",
            root / "config" / "profiles" / "f0_action_contract.profile.yaml",
        )
        self._goals_profile = load_m1_goals_profile(default_profile_path())


    @property
    def tmp_path(self) -> Path:
        """评价编排清理专用（INC-13 纪律：mkdtemp 具体路径公开只读）。"""
        return self._tmp
    def profile_digests(self) -> tuple[tuple[str, str], ...]:
        cfg = self._root / "config"
        return (
            ("m0_mw0", content_digest(self._m0_path.read_text(encoding="utf-8"))),
            ("c4_action_social", content_digest(
                (cfg / "profiles" / "c4_action_social.profile.yaml").read_text(encoding="utf-8"))),
            ("c1_perception_models", content_digest(
                (cfg / "profiles" / "c1_perception_models.profile.yaml").read_text(encoding="utf-8"))),
            ("stat_plan_c4", content_digest(
                (cfg / "evidence" / "stat_plans" / "c4_action_social.yaml").read_text(encoding="utf-8"))),
        )

    # —— 公共装配 ————————————————————————————————————————————
    def _harness(self, seed: bytes, tmp_tag: str, *, language: bool,
                 interventions: "InterventionRegistry | None" = None) -> "tuple[Any, ...]":
        trial_dir = self._tmp / tmp_tag
        trial_dir.mkdir(parents=True, exist_ok=True)
        stores = Stores(trial_dir / "stores")
        registry = Registry(trial_dir / "registry", stores, CycleClock())
        world = MW0World(self._profile.params, RngDirectory(seed, chacha8_block), branch_id="B")
        dynamics = MW0Dynamics(world, self._profile, RngDirectory(seed, chacha8_block), branch_id="B")
        interventions = interventions or InterventionRegistry()
        signing = derive_signing_key(seed)
        gateway = CapabilityGateway(self._gateway_config, signing,
                                    run_id="R", branch_id="B", subject_candidate_id="S")
        bus = ChannelBus(self._profile.params, registry, RngDirectory(seed, chacha8_block),
                         branch_id="B", interventions=interventions)
        extero, intero = ExteroceptiveChannel(bus, world), InteroceptiveChannel(bus, world)
        proprio, outcome = ProprioceptiveChannel(bus, world), OutcomeChannel(bus)
        lang = LanguageStubChannel(bus)
        sensorium = SensoriumPipeline(self._c0, self._calibration, self._time_basis,
                                      language_enabled=language)
        perception = PerceptionPipeline(self._c1)
        world_model = WorldModel(self._c1, "R")
        return (stores, registry, world, dynamics, gateway, bus,
                extero, intero, proprio, outcome, lang, sensorium, perception, world_model)

    def _delivery_packets(self, registry: Registry, delivery: Any, *, ood: bool = False,
                          ) -> "tuple[list[tuple[Any, str]], str | None]":
        """投递解码（REV-0014 R1 显式 decode；outcome 单独提取供轴 2；OOD 注入 runs_c3 同构）。"""
        packets: list[tuple[Any, str]] = []
        outcome_effect: str | None = None
        for packet in delivery.packets:
            blob = registry.get(ArtifactRef(digest=packet.payload_ref.digest, kind="payload")).blob
            try:
                json.loads(blob)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            text = blob.decode("utf-8")
            if packet.content_type == _CARRIER_OUTCOME:
                try:
                    outcome_effect = str(json.loads(text).get("effect"))
                except json.JSONDecodeError:
                    outcome_effect = None
                continue
            if ood and '"observation_window"' in text:
                payload = json.loads(text)
                if "window" in payload:
                    payload["window"] = _faulted_window(payload["window"])
                    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            packets.append((packet, text))
        return packets, outcome_effect

    def _consume_windows(self, sensorium: Any, perception: Any, world_model: Any,
                         cycle_out: Any,
                         ) -> "tuple[Any, dict[int, list[float]], dict[int, list[float]]]":
        """窗级两相消费（runs_c1 同构）；返回 (最新 belief, {t: posterior 行}, {t: ext 窗展平})。"""
        frames_by_t: dict[int, list[Any]] = {}
        for frame in cycle_out.frames:
            frames_by_t.setdefault(frame.effective_time, []).append(frame)
        belief = None
        posterior_rows: dict[int, list[float]] = {}
        ext_flat: dict[int, list[float]] = {}
        for t in sorted(frames_by_t):
            frames = tuple(frames_by_t[t])
            perc = perception.process_window(t, frames)
            posterior_rows[t] = [c.posterior_present for c in perc.cells]
            extero_frame = next(
                (f for f in frames if isinstance(f.features, ExtLocalObsFeatures)), None)
            if extero_frame is not None:
                ext_flat[t] = [float(v) for row in extero_frame.features.window for v in row]
                belief = world_model.update(t, perc.cells, (), (), ())
        return belief, posterior_rows, ext_flat

    def _axis3_from(self, move_pred: Any, persist_pred: Any,
                    ext_flat: "dict[int, list[float]]") -> "bool | None":
        """轴 3：积分预测 vs 持续预测（同帧信息状态）对窗 5 残差比较（积分更优 = Y）。"""
        if move_pred is None or persist_pred is None:
            return None
        frame5 = ext_flat.get(5)
        if frame5 is None or len(frame5) != 25:
            return None
        move_vals = [float(v) for row in move_pred.expected_window for v in row]
        persist_vals = [float(v) for row in persist_pred.expected_window for v in row]
        d_move = sum(abs(a - b) for a, b in zip(move_vals, frame5)) / 25.0
        d_persist = sum(abs(a - b) for a, b in zip(persist_vals, frame5)) / 25.0
        return d_move < d_persist

    # —— battery 臂（claim 1）——————————————————————————————
    def run_battery(self, seed: bytes) -> dict[str, Any]:
        conditions = [self._battery_condition(seed, cond) for cond in _BATTERY_CONDITIONS]
        resolved = [c for c in conditions if c["probability"] is not None]
        endpoint_errors = sum(
            1 for c in resolved
            if (c["probability"] == 1.0) != (c["ground_truth"] == "SELF_PRODUCED")
        )
        ece = (
            sum(abs(c["probability"] - (1.0 if c["ground_truth"] == "SELF_PRODUCED" else 0.0))
                for c in resolved) / len(resolved)
        ) if resolved else 1.0
        ambiguous = [c for c in conditions if c["probability"] is None]
        return {
            "conditions": conditions,
            "ece_resolved": ece,
            "endpoint_errors": endpoint_errors,
            "resolved_count": len(resolved),
            "ambiguous_count": len(ambiguous),
            "ambiguous_traced": sum(1 for c in ambiguous if c["unknown_traced"]),
            "sham_kind": next((c["kind"] for c in conditions if c["condition"] == "sham"), None),
            "fault_kind": next((c["kind"] for c in conditions if c["condition"] == "fault"), None),
        }

    def _battery_condition(self, seed: bytes, cond: str) -> dict[str, Any]:
        interventions = InterventionRegistry()
        if cond == "no_op":
            interventions.register(record_id="inoop", kind="no_op", registered_at_cycle=0,
                                   from_cycle=4, to_cycle=4, target_primitive="move")
        elif cond == "sham":
            interventions.register(record_id="isham", kind="sham", registered_at_cycle=0,
                                   from_cycle=4, to_cycle=4, target_primitive="move")
        elif cond == "fault":
            interventions.register(record_id="iflt", kind="fault", registered_at_cycle=0,
                                   from_cycle=5, to_cycle=5)
        harness = self._harness(seed, f"bat-{cond}", language=False, interventions=interventions)
        (stores, registry, world, dynamics, gateway, bus,
         extero, intero, proprio, outcome, _lang, sensorium, perception, world_model) = harness
        try:
            intent_submitted = False
            authorized = False
            rejected = False
            move_pred = persist_pred = None
            ext_flat: dict[int, list[float]] = {}
            receipt_ok = False
            pending_command = None
            for cycle in range(10):
                if cycle == 4 and cond != "uncommanded":
                    intent_submitted = True
                    primitive = "fly" if cond == "blocked" else "move"
                    _, command = gateway.authorize(
                        ActionIntention("i-bat", "c4-eval", "eval", cycle + 8, None, "batk"),
                        ActionSpec(primitive, None if primitive == "fly" else "N"),
                        subject_candidate_id="S", run_id="R", branch_id="B", virtual_time=cycle)
                    if command is not None:
                        authorized = True
                        fact = dynamics.apply(DynCommand(primitive=Primitive.MOVE, param="N",
                                                         command_id=command.command_id),
                                              interventions, cycle)
                        outcome.render_and_submit(cycle,
                            ArtifactRef(digest=world.state_digest(), kind="world_state_ref"),
                            command.command_id, fact.effective_effect)
                        pending_command = command
                        # 预测于本拍投递消费后签发（窗 0 数据在案；issued=4 仍先行于
                        # 效果到达=5——L10 §4.3 时序纪律；见下方 consume 后块）
                    else:
                        rejected = True   # fly 越能力类型化拒绝（主体可见）
                elif cycle == 4 and cond == "uncommanded":
                    world.apply_primitive(Primitive.MOVE, "S", dry_run=False)   # 无命令外源位移
                events = dynamics.step()
                truth_ref = ArtifactRef(digest=world.state_digest(), kind="world_state_ref")
                extero.render_and_submit(cycle, truth_ref)
                intero.render_and_submit(cycle, truth_ref, events)
                proprio.render_and_submit(cycle, truth_ref)
                delivery = bus.deliver(cycle)
                packets, outcome_effect = self._delivery_packets(registry, delivery)
                if outcome_effect is not None and outcome_effect != "none":
                    receipt_ok = True   # 回执状态持久化（不随后续拍覆盖）
                cycle_out = sensorium.process_cycle(cycle, packets)
                audit(cycle_out.frames, cycle_out.formation_receipts, cycle_out.gain_receipts)
                _belief, _rows, ext_flat = self._consume_windows(sensorium, perception,
                                                                 world_model, cycle_out)
                if pending_command is not None:
                    # 同步签发（同 cycle=4）：先持续反事实后积分位移（world model 为
                    # 可变实例——顺序颠倒使两预测同源）
                    persist_pred = predict_window(world_model.advance(5, (), ()),
                                                  self._c1, 5)[0]
                    move_pred = predict_window(world_model.advance(5, (), ("N",)),
                                               self._c1, 5)[0]
                    issue_efference_copy(pending_command, move_pred, issued_cycle=cycle)
                    pending_command = None
            if rejected:
                axis3: bool | None = False       # 类型化拒绝 → 命令后果未发生
            elif cond == "uncommanded":
                axis3 = False                    # 无命令提交 → 无积分预测
            elif not authorized:
                axis3 = None
            else:
                axis3 = self._axis3_from(move_pred, persist_pred, ext_flat)
            axes = AttributionAxes(
                intent_match=intent_submitted,
                receipt_executed=receipt_ok,
                outcome_predicted=axis3,
                evidence_refs=(f"bat:{cond}", "cycle:6"),
                settle_cycle=6,
            )
            attribution = attribute_action(axes, self._c4,
                                           divergence_kind="COERCED" if cond == "uncommanded" else None)
            return {
                "condition": cond,
                "cell": axes.key(),
                "probability": (attribution.probability
                                if isinstance(attribution.probability, float) else None),
                "kind": attribution.attribution_kind.value,
                "unknown_traced": len(attribution.unknowns) > 0,
                "unknown_reason": (attribution.unknowns[0].reason.value
                                   if attribution.unknowns else None),
                "ground_truth": "SELF_PRODUCED" if cond == "clean" else "NOT_SELF",
                "axis3": axis3,
            }
        finally:
            stores.close()

    # —— efference 臂（claim 2）——————————————————————————————
    def run_efference(self, seed: bytes, *, ablated: bool) -> dict[str, Any]:
        harness = self._harness(seed, f"eff-{'ab' if ablated else 'full'}", language=False)
        (stores, registry, world, dynamics, gateway, bus,
         extero, intero, proprio, outcome, _lang, sensorium, perception, world_model) = harness
        try:
            authorized = False
            move_pred = persist_pred = None
            receipt_ok = False
            ext_flat: dict[int, list[float]] = {}
            pending_command = None
            for cycle in range(10):
                if cycle == 4:
                    _, command = gateway.authorize(
                        ActionIntention("i-eff", "c4-eval", "eval", cycle + 8, None, "effk"),
                        ActionSpec("move", "N"),
                        subject_candidate_id="S", run_id="R", branch_id="B", virtual_time=cycle)
                    if command is not None:
                        authorized = True
                        fact = dynamics.apply(DynCommand(primitive=Primitive.MOVE, param="N",
                                                         command_id=command.command_id),
                                              InterventionRegistry(), cycle)
                        outcome.render_and_submit(cycle,
                            ArtifactRef(digest=world.state_digest(), kind="world_state_ref"),
                            command.command_id, fact.effective_effect)
                        pending_command = command
                events = dynamics.step()
                truth_ref = ArtifactRef(digest=world.state_digest(), kind="world_state_ref")
                extero.render_and_submit(cycle, truth_ref)
                intero.render_and_submit(cycle, truth_ref, events)
                proprio.render_and_submit(cycle, truth_ref)
                delivery = bus.deliver(cycle)
                packets, outcome_effect = self._delivery_packets(registry, delivery)
                if outcome_effect is not None and outcome_effect != "none":
                    receipt_ok = True
                cycle_out = sensorium.process_cycle(cycle, packets)
                audit(cycle_out.frames, cycle_out.formation_receipts, cycle_out.gain_receipts)
                _belief, _rows, ext_flat = self._consume_windows(sensorium, perception,
                                                                 world_model, cycle_out)
                if pending_command is not None:
                    persist_pred = predict_window(world_model.advance(5, (), ()),
                                                  self._c1, 5)[0]
                    move_pred = predict_window(world_model.advance(5, (), ("N",)),
                                               self._c1, 5)[0]
                    if not ablated:
                        issue_efference_copy(pending_command, move_pred, issued_cycle=cycle)
                    pending_command = None
            axis3 = (self._axis3_from(move_pred, persist_pred, ext_flat)
                     if authorized and not ablated else None)
            axes = AttributionAxes(
                intent_match=authorized,
                receipt_executed=receipt_ok,
                outcome_predicted=axis3,
                evidence_refs=("eff", "cycle:6"),
                settle_cycle=6,
            )
            attribution = attribute_action(axes, self._c4)
            kind = attribution.attribution_kind.value
            return {
                "self_attribution_correct": 1.0 if kind == "SELF_PRODUCED" else 0.0,
                "kind": kind,
                "axis3": axis3,
            }
        finally:
            stores.close()

    # —— switch 臂（claim 3）——————————————————————————————
    def run_switch(self, seed: bytes, *, full: bool, lang_twin: bool = False,
                   replay: ReplayStore | None = None) -> dict[str, Any]:
        if replay is None:
            raise StatPlanViolation("switch arm requires recording-backed ReplayStore（Q-L12-03）")
        harness = self._harness(seed, f"sw-{'full' if full else 'clean'}", language=True)
        (stores, registry, world, dynamics, gateway, bus,
         extero, intero, proprio, outcome, lang, sensorium, perception, world_model) = harness
        try:
            lifecycle = GoalLifecycle("c4_action_social@v1.0")
            meta = MetaControlState()
            cmd_seq = 0
            goal_id: str | None = None
            capability_pending = False
            help_sent = False
            first_rejection: int | None = None
            goal_achieved = False
            seek_help_fired = 0
            abandon_fired = 0
            observe_count = 0
            posterior_digests: dict[int, str] = {}
            pending_ood = False
            for cycle in range(176):
                # 语言注入（事件级；@12 = 场景设置双臂同置，非处理面）
                if cycle == 12 or (full and cycle == 20) or (lang_twin and cycle == 100):
                    text = ("please move north" if cycle == 12
                            else "please fly north" if cycle == 20 else "there is food nearby")
                    lang.submit_typed_statement(cycle,
                        ArtifactRef(digest=world.state_digest(), kind="world_state_ref"),
                        text=text, requester="experiment_control")
                # 结算面动作尝试（每 16 拍自 30；full 臂 blocked 窗 = 过期 deadline 类型化拒绝）
                if goal_id is not None and not goal_achieved and cycle >= 30 and cycle % 16 == 0:
                    deadline = cycle - 1 if full else cycle + 8
                    _, command = gateway.authorize(
                        ActionIntention(f"i-mv{cmd_seq}", "c4-eval", "eval", deadline, None,
                                        f"mvk{cmd_seq}"),
                        ActionSpec("move", "N"),
                        subject_candidate_id="S", run_id="R", branch_id="B", virtual_time=cycle)
                    cmd_seq += 1
                    if command is None:
                        if full and first_rejection is None:
                            first_rejection = cycle
                    else:
                        fact = dynamics.apply(DynCommand(primitive=Primitive.MOVE, param="N",
                                                         command_id=command.command_id),
                                              InterventionRegistry(), cycle)
                        outcome.render_and_submit(cycle,
                            ArtifactRef(digest=world.state_digest(), kind="world_state_ref"),
                            command.command_id, fact.effective_effect)
                        if fact.effective_effect != "none":
                            goal_achieved = True   # primitive_completion（move 完成回执）
                events = dynamics.step()
                truth_ref = ArtifactRef(digest=world.state_digest(), kind="world_state_ref")
                extero.render_and_submit(cycle, truth_ref)
                intero.render_and_submit(cycle, truth_ref, events)
                proprio.render_and_submit(cycle, truth_ref)
                delivery = bus.deliver(cycle)
                packets, _effect = self._delivery_packets(registry, delivery,
                                                          ood=(full and cycle % 8 == 0))
                cycle_out = sensorium.process_cycle(cycle, packets)
                audit(cycle_out.frames, cycle_out.formation_receipts, cycle_out.gain_receipts)
                _belief, post_rows, _ext = self._consume_windows(sensorium, perception,
                                                                world_model, cycle_out)
                for t, row in post_rows.items():
                    posterior_digests[t] = content_digest(json.dumps(row, sort_keys=True))
                # R-PARSE（事件级触发：LANGUAGE 帧在案；subject 出边界话语的总线回环
                # = harness 伪影，非入站通信——MW0 containment 下不回环为输入）
                lang_frame = next((f for f in cycle_out.frames
                                   if f.modality.value == "LANGUAGE"
                                   and not f.features.requester.startswith("subject:")), None)
                if lang_frame is not None:
                    parsed = parse_language_frame(lang_frame.features, lang_frame.frame_id,
                                                  replay, self._c4)
                    if parsed.kind in ("request", "instruction"):   # L12 §4.3：同走请求面
                        # 原语映射 = 冻结场景文本（stat plan statement_request/
                        # capability_request 原文；帧 ID 不承载语义）
                        req_outcome = self._handle_request(
                            parsed, lang_frame.features.statement_text,
                            post_rows, cycle, lifecycle)
                        if req_outcome == "adopted":
                            goal_id = "g.c4.req"
                        elif req_outcome == "capability_rejected":
                            capability_pending = True
                # 监控面（L09 §4.4 调用方计算；语义 = stat plan trigger_monitor_semantics）
                blocked_over = (
                    goal_id is not None and not goal_achieved and first_rejection is not None
                    and (cycle - first_rejection) >= 128
                )
                decision, switched = meta.step(MetaTriggers(
                    capability_boundary_hit=capability_pending and not help_sent,
                    blocked_over_threshold=blocked_over,
                    ood_or_abstain_event=pending_ood,
                ), cycle)
                if decision == "OBSERVE":
                    observe_count += 1
                if switched and decision == "SEEK_HELP":
                    allowed, _detail = meta.request_help(cycle)
                    if allowed:
                        utt = seek_help_utterance(
                            "capability boundary: requested action fly is not in the frozen "
                            "action contract; seeking guidance",
                            "HELP_CAPABILITY_BOUNDARY", ("fly-rejection",), replay)
                        lang.submit_utterance(cycle,
                            ArtifactRef(digest=world.state_digest(), kind="world_state_ref"),
                            text=utt.text, role="R-SEEKHELP")
                        seek_help_fired += 1
                        help_sent = True
                        capability_pending = False   # 边界已求助（触发清除——stat plan 语义）
                if switched and decision == "ABANDON" and goal_id is not None:
                    lifecycle.release("g.c4.req", (f"blocked-since:{first_rejection}",))
                    abandon_fired += 1
                    goal_id = None
                pending_ood = full and cycle % 8 == 0
            return {
                "seek_help_fired": seek_help_fired,
                "abandon_fired": abandon_fired,
                "observe_count": observe_count,
                "goal_achieved": goal_achieved,
                "posterior_digests": posterior_digests,
            }
        finally:
            stores.close()

    def _handle_request(self, parsed: Any, statement_text: str,
                        post_rows: "dict[int, list[float]]", cycle: int,
                        lifecycle: GoalLifecycle) -> str:
        """request 分型 → 候选 → 清单 → 采纳（C-5 支持动机 = 真实知觉面；fly 越能力 = 拒）。"""
        primitive = "fly" if "fly" in statement_text else "move"
        top = max((v for row in post_rows.values() for v in row), default=0.0)
        if top >= 0.5:
            supporting = (Motive(MotiveSource.OPPORTUNITY, top, (f"win:{cycle}",), cycle),)
        else:
            total = sum(v for row in post_rows.values() for v in row)
            count = max(1, sum(len(r) for r in post_rows.values()))
            unc = 1.0 - total / count
            supporting = ((Motive(MotiveSource.CURIOSITY, unc, (f"win:{cycle}",), cycle),)
                          if unc > 0.6 else ())
        candidate = GoalCandidate(
            candidate_id=f"cand.{cycle}", source_kind=MotiveSource.REQUEST,
            motive_refs=(parsed.text_ref, *(m.evidence_refs[0] for m in supporting)),
            content_ref=parsed.text_ref,
            settle=SettleCriterion(SettlePredicate.PRIMITIVE_COMPLETION),
            required_primitives=(primitive,), ttl_cycles=256, created_cycle=cycle, urgency=0.5)
        inputs = ChecklistInputs(
            capability_known=True,
            known_primitives=tuple(self._c4.capability_action_class),
            quota_slack={p: 8 for p in self._c4.capability_action_class},
            viability=ViabilityEstimate(hazard_energy_depleted_unrecovered=False,
                                        integrity_damage_events=0,
                                        derivation_refs=(f"win:{cycle}",), ts=cycle),
            supporting_non_request_motives=supporting,
        )
        verdict = run_checklist(candidate, inputs, self._goals_profile, cycle)
        if verdict.decision.value == "ACCEPT":
            lifecycle.adopt(verdict, candidate, "g.c4.req", cycle)
            return "adopted"
        if verdict.decision.value == "REJECT" and primitive == "fly":
            return "capability_rejected"
        return "deferred"


def load_c4_scenario(stat_plan_path: Path) -> dict[str, Any]:
    if not stat_plan_path.is_file():
        raise StatPlanViolation(f"stat plan not found: {stat_plan_path}")
    raw = cast(dict[str, Any], yaml.safe_load(stat_plan_path.read_text(encoding="utf-8")))
    return cast(dict[str, Any], cast(dict[str, Any], raw["stat_plan"])["scenario"])


def mechanical_checks(records: tuple[C4ArmRecord, ...]) -> dict[str, bool]:
    """机械判据（不入统计 claim）：端点零错误/歧义留痕/消融对比/langtwin 后验恒等。"""
    battery = [r for r in records if r.arm == "battery"]
    eff_full = [r for r in records if r.arm == "eff_full"]
    eff_ab = [r for r in records if r.arm == "eff_ablated"]
    checks: dict[str, bool] = {}
    checks["battery_endpoint_zero_error"] = all(
        r.summary["endpoint_errors"] == 0 for r in battery) and bool(battery)
    checks["battery_ambiguous_trace_full"] = all(
        r.summary["ambiguous_count"] == r.summary["ambiguous_traced"] for r in battery)
    checks["fault_cell_unknown_not_self"] = all(
        r.summary["fault_kind"] == "UNKNOWN" for r in battery)
    checks["sham_cell_unknown"] = all(
        r.summary["sham_kind"] == "UNKNOWN" for r in battery)
    checks["eff_full_self_ablated_unknown"] = all(
        r.summary["self_attribution_correct"] == 1.0 for r in eff_full) and all(
        r.summary["kind"] == "UNKNOWN" for r in eff_ab)
    for idx in sorted({r.run_index for r in records}):
        clean = next((r for r in records if r.arm == "switch_clean" and r.run_index == idx), None)
        twin = next((r for r in records if r.arm == "switch_langtwin" and r.run_index == idx), None)
        if clean is not None and twin is not None:
            shared = set(clean.summary["posterior_digests"]) & set(twin.summary["posterior_digests"])
            checks[f"langtwin_posterior_bit_exact#{idx}"] = bool(shared) and all(
                clean.summary["posterior_digests"][t] == twin.summary["posterior_digests"][t]
                for t in shared)
    return checks


def run_c4_evaluation(
    root: Path, run_dir: Path, tmp_dir: Path, sealed_cells: tuple[Any, ...],
    stat_plan_path: Path, split_digest: str, recording_path: Path,
    n_limit: int | None = None,
) -> tuple[tuple[C4ArmRecord, ...], dict[str, bool], str, str, bool]:
    """C4 正式评价编排（五臂 + 机械判据 + I1；recording = Q-L12-03 录制文件）。"""
    if n_limit is not None and n_limit <= 0:
        raise ValueError("n_limit must be positive when provided")
    probe_recorder(run_dir)
    plan = load_stat_plan(stat_plan_path)
    claim = next((c for c in plan.claims if c.claim_id == "c4_efference_attribution_loop"), None)
    if claim is None:
        raise StatPlanViolation("stat plan missing frozen claim c4_efference_attribution_loop")
    n = claim.n if n_limit is None else min(n_limit, claim.n)
    runner = C4Runner(root, tmp_dir)
    replay = load_recording(recording_path)

    stores = Stores(run_dir / "stores")
    try:
        registry = Registry(run_dir / "registry", stores, CycleClock())
        writer = EvidenceWriter(registry)
        writer.add_manifest(RunManifest.create(
            "c4-action-social-sealed-evaluation", _EVAL_MASTER_SEED_C4.hex(), "B",
            runner.profile_digests(), plan.digest, split_digest))
        all_records: list[C4ArmRecord] = []
        for p in range(n):
            cell = sealed_cells[p % len(sealed_cells)]
            seed = _trial_seed(_EVAL_MASTER_SEED_C4, p)
            for arm in _ARMS:
                if arm == "battery":
                    summary = runner.run_battery(seed)
                elif arm == "eff_full":
                    summary = runner.run_efference(seed, ablated=False)
                elif arm == "eff_ablated":
                    summary = runner.run_efference(seed, ablated=True)
                elif arm == "switch_full":
                    summary = runner.run_switch(seed, full=True, replay=replay)
                elif arm == "switch_clean":
                    summary = runner.run_switch(seed, full=False, replay=replay)
                else:
                    summary = runner.run_switch(seed, full=False, lang_twin=True, replay=replay)
                record = C4ArmRecord(
                    run_index=p, arm=arm, cell_id=cell.cell_id,
                    seed_hex=seed.hex(), summary=summary, formation_counts=(0, 0, 0))
                all_records.append(record)
                writer.add("trace", {
                    "record_digest": record.digest, "run_index": p, "arm": arm,
                    "cell_id": cell.cell_id, "seed_hex": record.seed_hex,
                    "summary_digest": record.digest,
                })
                writer.add("evidence", {
                    "run_index": p, "arm": arm, "cycle": -1,
                    "summary": json.dumps(summary, sort_keys=True, separators=(",", ":")),
                })
        mechanical = mechanical_checks(tuple(all_records))
        shutil.rmtree(tmp_dir, ignore_errors=True)
        shutil.rmtree(run_dir / "scratch", ignore_errors=True)

        eff_full = tuple(r for r in all_records if r.arm == "eff_full")
        vector_digest = content_digest(json.dumps(
            [r.summary for r in eff_full], sort_keys=True, default=str))
        refs = writer.close()

        def _recompute(partitions: dict[str, list[dict[str, Any]]]) -> str:
            rows = [json.loads(r["summary"]) for r in partitions["evidence"]
                    if json.loads(r["summary"]).get("self_attribution_correct") is not None
                    and r.get("arm") == "eff_full"]
            return content_digest(json.dumps(rows, sort_keys=True, default=str))

        report = recompute_i1(registry, refs, _recompute, vector_digest)   # type: ignore[arg-type]
        return (tuple(all_records), mechanical, plan.digest, split_digest, report.match)
    finally:
        stores.close()


def cleanup_runner_tmp(runner: "C4Runner") -> None:
    """I3/评价编排清理专用（INC-13 纪律：仅删 mkdtemp 具体路径——禁仓库根字面量）。"""
    import shutil as _shutil

    _shutil.rmtree(runner.tmp_path, ignore_errors=True)
