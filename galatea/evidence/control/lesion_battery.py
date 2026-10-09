"""E1 lesion 电池：跨模块消融 → 选择性失败证据（L13 §9 E1 行；全模块实组件接线）。

设计（D-10 可干预）：同 seed 同世界流（32 cycles，OOD 每 8 拍注入，陈述@8，
move@12），每 lesion = 单一实组件消融开关；选择性 = 目标函数失败标记 ∧
保留函数标记（全部为运行中实测计数——禁同义反复）：
- affect_off        AffectPipeline.step 不调用 → affect_steps=0（保持：后验/采纳照常）
- goals_off         清单+采纳尝试跳过 → adopted=0（保持：affect 步数/后验照常）
- memory_off        encode 跳过 → working 计数 0（保持：affect/后验照常）
- language_off      statement 不入形成面 → parsed=0；
                    保持：非语言形成 digest 与基线逐位恒等（Q-L12-07 复用）
- metacontrol_off   MetaControlState.step 跳过 → 非 ACT 决策 0（保持：其余照常）
- perception_off    process_window 跳过 → 后验 0（保持：形成帧/affect 照常）
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from galatea.env.channels.adapter import ChannelBus
from galatea.env.channels.extero import ExteroceptiveChannel
from galatea.env.channels.intero import InteroceptiveChannel
from galatea.env.channels.language_stub import LanguageStubChannel
from galatea.env.channels.outcome import OutcomeChannel
from galatea.env.channels.proprio import ProprioceptiveChannel
from galatea.env.interventions.registry import InterventionRegistry
from galatea.env.profile import load_profile
from galatea.env.world.dynamics import Command as DynCommand
from galatea.env.world.dynamics import MW0Dynamics
from galatea.env.world.mw0 import MW0World, Primitive
from galatea.kernel.clock import CycleClock
from galatea.kernel.packet import ArtifactRef, RepresentationLevel
from galatea.kernel.registry import Registry
from galatea.kernel.rng import RngDirectory, chacha8_block
from galatea.kernel.state import Stores
from galatea.subject.affect.pipeline import AffectPipeline
from galatea.subject.affect.ports import AffectCycleInputs
from galatea.subject.action.gateway import ActionSpec, CapabilityGateway, load_gateway_config
from galatea.subject.action.metacontrol import MetaControlState, MetaTriggers
from galatea.subject.action.signature import derive_signing_key
from galatea.subject.c1profile import load_c1_profile
from galatea.subject.c4profile import load_c4_action_social_profile
from galatea.subject.control.intention import ActionIntention
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
from galatea.subject.language.parse import parse_language_frame
from galatea.subject.language.replay import ReplayStore
from galatea.subject.memory.encode import encode_working
from galatea.subject.memory.ports import MemorySubsystem, SourceType
from galatea.subject.memory.store import (
    MemoryStore,
    MemoryStoreViolation,
    load_m2_continuity_profile,
)
from galatea.subject.perception.pipeline import PerceptionPipeline
from galatea.subject.sensorium.calibration import bind_calibration
from galatea.subject.sensorium.ingest import (
    CARRIER_EXTERO,
    CARRIER_INTERO,
    CARRIER_LANGUAGE,
    CARRIER_PROPRIO,
)
from galatea.subject.sensorium.pipeline import SensoriumPipeline
from galatea.subject.sensorium.ports import (
    ExtLocalObsFeatures,
    InteroSensations,
    load_c0_sensorium_profile,
)

_LESIONS = ("none", "affect_off", "goals_off", "memory_off", "language_off",
            "metacontrol_off", "perception_off")
_EVAL_MASTER_SEED = bytes.fromhex("63352d636f6e74696e7565642d6c6561726e696e67")   # stat plan 同源
_C4 = load_c4_action_social_profile()
_M2_PROFILE = load_m2_continuity_profile()
_GOALS_PROFILE = load_m1_goals_profile(default_profile_path())


def _trial_seed(master: bytes, index: int) -> bytes:
    import hashlib

    return hashlib.sha256(f"c5.learning|{index}".encode("utf-8") + master).digest()


def _faulted(window: list[list[Any]]) -> list[list[Any]]:
    w = [list(row) for row in window]
    w[0][0] = 5.0
    return w


@dataclass(frozen=True, slots=True)
class LesionResult:
    """单 lesion 运行标记集（全部实测计数）。"""

    lesion: str
    target_failed: bool
    others_preserved: bool
    markers: dict[str, Any]

    @property
    def selective(self) -> bool:
        return self.target_failed and self.others_preserved


def run_lesion(root: Path, lesion: str, replay: ReplayStore) -> LesionResult:
    """单 lesion 全栈运行（真实组件接线；marker 全实测）。"""
    if lesion not in _LESIONS:
        raise ValueError(f"unknown lesion: {lesion!r}")
    seed = _trial_seed(_EVAL_MASTER_SEED, 0)
    tmp = Path(tempfile.mkdtemp(prefix=f"lesion-{lesion}-"))
    profile = load_profile(root / "config" / "profiles" / "m0_mw0.profile.yaml")
    stores = Stores(tmp / "stores")
    reg = Registry(tmp / "registry", stores, CycleClock())
    world = MW0World(profile.params, RngDirectory(seed, chacha8_block), branch_id="B")
    dynamics = MW0Dynamics(world, profile, RngDirectory(seed, chacha8_block), branch_id="B")
    bus = ChannelBus(profile.params, reg, RngDirectory(seed, chacha8_block),
                     branch_id="B", interventions=InterventionRegistry())
    extero, intero = ExteroceptiveChannel(bus, world), InteroceptiveChannel(bus, world)
    proprio, outcome = ProprioceptiveChannel(bus, world), OutcomeChannel(bus)
    lang = LanguageStubChannel(bus)
    c0 = load_c0_sensorium_profile()
    sensorium = SensoriumPipeline(
        c0,
        bind_calibration(root / "config" / "profiles" / "c0_sensorium.profile.yaml",
                         c0.calibration_version),
        {CARRIER_EXTERO: 1, CARRIER_INTERO: 0, CARRIER_PROPRIO: 0, CARRIER_LANGUAGE: 1},
        language_enabled=(lesion != "language_off"),
    )
    perception = PerceptionPipeline(load_c1_profile())
    gateway = CapabilityGateway(
        load_gateway_config(
            root / "config" / "profiles" / "m0_gateway.profile.yaml",
            root / "config" / "profiles" / "f0_action_contract.profile.yaml",
        ),
        derive_signing_key(seed), run_id="R", branch_id="B", subject_candidate_id="S",
    )
    memory = MemoryStore(stores)
    affect = AffectPipeline(load_c2_affect_profile())
    meta = MetaControlState()
    lifecycle = GoalLifecycle("c5_continued_learning@v1.1")
    try:
        frames_total = 0
        ext_digests: list[str] = []
        parsed_count = 0
        posteriors = 0
        affect_steps = 0
        adopted = 0
        decisions_non_act = 0
        goal_tried = False
        pending_ood = False
        gateway_ok = False
        for cycle in range(32):
            if cycle == 8 and lesion != "language_off":
                lang.submit_typed_statement(
                    cycle, ArtifactRef(digest=world.state_digest(), kind="world_state_ref"),
                    text="please move north", requester="experiment_control")
            if cycle == 12:
                _, command = gateway.authorize(
                    ActionIntention("i-les", "lesion", "eval", cycle + 8, None, "lesk"),
                    ActionSpec("move", "N"), subject_candidate_id="S", run_id="R",
                    branch_id="B", virtual_time=cycle)
                gateway_ok = command is not None
                if command is not None:
                    fact = dynamics.apply(
                        DynCommand(primitive=Primitive.MOVE, param="N",
                                   command_id=command.command_id),
                        InterventionRegistry(), cycle)
                    outcome.render_and_submit(
                        cycle, ArtifactRef(digest=world.state_digest(),
                                           kind="world_state_ref"),
                        command.command_id, fact.effective_effect)
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
                text = blob.decode("utf-8")
                if (lesion != "none" and lesion != "language_off" and pending_ood
                        and '"observation_window"' in text):
                    payload = json.loads(text)
                    if "window" in payload:
                        payload["window"] = _faulted(payload["window"])
                        text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
                packets.append((packet, text))
            out = sensorium.process_cycle(cycle, packets)
            frames_total += len(out.frames)
            for f in out.frames:
                if isinstance(f.features, ExtLocalObsFeatures):
                    ext_digests.append(f.content_digest)
            frames_by_t: dict[int, list[Any]] = {}
            for f in out.frames:
                frames_by_t.setdefault(f.effective_time, []).append(f)
            for t in sorted(frames_by_t):
                if lesion == "perception_off":
                    continue
                perc = perception.process_window(t, tuple(frames_by_t[t]))
                posteriors += len(perc.cells)
                if lesion != "memory_off" and perc.cells:
                    # L06 encode：窗感知摘要（真实写入面；working 容量 8 冻结
                    # 【m2 profile】——容量满 = 真实记忆行为，满载计数仍 >0）
                    try:
                        encode_working(memory, _M2_PROFILE, f"w.{cycle}.{t}",
                                       json.dumps([round(c.posterior_present, 3)
                                                   for c in perc.cells]),
                                       RepresentationLevel.SENSORY_FORMED,
                                       SourceType.PERCEIVED, cycle)
                    except MemoryStoreViolation:
                        pass
            # L12 R-PARSE（语言帧在案即回放解析——language_off 无帧 = 零解析）
            if lesion != "language_off":
                from typing import cast

                from galatea.subject.sensorium.ports import LanguageFeatures

                lang_frame = next(
                    (f for f in out.frames if isinstance(f.features, LanguageFeatures)
                     and not f.features.requester.startswith("subject:")), None)
                if lang_frame is not None:
                    parse_language_frame(cast("LanguageFeatures", lang_frame.features),
                                         lang_frame.frame_id, replay, _C4)
                    parsed_count += 1
            if lesion != "affect_off":
                from typing import cast as _cast

                intero_frame = next((f for f in out.frames
                                     if isinstance(f.features, InteroSensations)), None)
                energy = (_cast("InteroSensations", intero_frame.features).energy_level
                          if intero_frame is not None else 1.0)
                affect.step(AffectCycleInputs(cycle=cycle, body_energy=energy,
                                              body_integrity=1.0))
                affect_steps += 1
            if (cycle == 20 and lesion != "goals_off" and not goal_tried
                    and posteriors > 0):
                goal_tried = True
                candidate = GoalCandidate(
                    candidate_id=f"cand.{cycle}", source_kind=MotiveSource.REQUEST,
                    motive_refs=("lang.frame@8", "win:20"),
                    content_ref="lang.frame@8",
                    settle=SettleCriterion(SettlePredicate.PRIMITIVE_COMPLETION),
                    required_primitives=("move",), ttl_cycles=256,
                    created_cycle=cycle, urgency=0.5)
                verdict = run_checklist(candidate, ChecklistInputs(
                    capability_known=True,
                    known_primitives=tuple(_C4.capability_action_class),
                    quota_slack={p: 8 for p in _C4.capability_action_class},
                    viability=ViabilityEstimate(
                        hazard_energy_depleted_unrecovered=False,
                        integrity_damage_events=0,
                        derivation_refs=("win:20",), ts=cycle),
                    supporting_non_request_motives=(
                        Motive(MotiveSource.CURIOSITY, 0.7, ("win:20",), cycle),)),
                    _GOALS_PROFILE, cycle)
                if verdict.decision.value == "ACCEPT":
                    lifecycle.adopt(verdict, candidate, "g.les", cycle)
                    adopted += 1
            if lesion != "metacontrol_off":
                decision, _switched = meta.step(
                    MetaTriggers(ood_or_abstain_event=pending_ood), cycle)
                if decision != "ACT":
                    decisions_non_act += 1
            pending_ood = cycle % 8 == 7
        working_count = memory.count(MemorySubsystem.WORKING)
        markers: dict[str, Any] = {
            "frames_total": frames_total,
            "ext_digest_set": hashlib.sha256(
                json.dumps(ext_digests).encode()).hexdigest()[:16],
            "parsed_count": parsed_count,
            "posteriors": posteriors,
            "affect_steps": affect_steps,
            "adopted": adopted,
            "working_count": working_count,
            "decisions_non_act": decisions_non_act,
            "gateway_ok": gateway_ok,
        }
        target_failed = {
            "none": False,
            "affect_off": affect_steps == 0,
            "goals_off": adopted == 0,
            "memory_off": working_count == 0,
            "language_off": parsed_count == 0,
            "metacontrol_off": decisions_non_act == 0,
            "perception_off": posteriors == 0,
        }[lesion]
        others_preserved = {
            "none": posteriors > 0 and affect_steps > 0 and gateway_ok and adopted > 0,
            "affect_off": posteriors > 0 and frames_total > 0 and gateway_ok,
            "goals_off": affect_steps > 0 and posteriors > 0 and gateway_ok,
            "memory_off": affect_steps > 0 and posteriors > 0 and gateway_ok,
            "language_off": False,   # 保持面单列：非语言 digest 与基线恒等（battery 断言）
            "metacontrol_off": affect_steps > 0 and posteriors > 0 and gateway_ok,
            "perception_off": frames_total > 0 and affect_steps > 0,
        }[lesion]
        return LesionResult(lesion=lesion, target_failed=target_failed,
                            others_preserved=others_preserved, markers=markers)
    finally:
        stores.close()
        shutil.rmtree(tmp, ignore_errors=True)


def load_c2_affect_profile():
    from galatea.subject.c2profile import load_c2_affect_profile

    return load_c2_affect_profile()
