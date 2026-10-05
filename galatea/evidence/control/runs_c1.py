"""C1 正式评价 runner（stat plan c1_perception_models v1.0；顺延终止条款首次执行）。

场景（冻结于统计计划 scenario 节）：40 cycles 真实 MW0+ChannelBus 流——请求动作
（gateway 签名路径 + outcome 回执）与无命令外源位移（world.apply_primitive 直施、
无任何主体可见动作信号——判据 3 的 efference 缺席操纵）冻结编排；主体平面 =
sensorium → perception → world/body 模型（生产实现，非测试替身）。

时序（T1 先行发布语义，stat plan 冻结）：窗 t 于 delivery t+4 关闭（W_align=4）；
窗 t 处理仅消费 cycle ≤ t+1 的动作；prediction(t+1) 自更新后状态发布，其 MSE 在
窗 t+1 帧到达时结算（预测与目标窗严格对齐）。外源位移永不进入消费流（无回执；
位姿陈旧不可再同步 = Q-L04-09 持续性语义的诚实后果）。

纪律：主体侧输入仅五通道 RECEIVED（真值快照为 evaluator 侧记录，主体不可见）；
全部行落 recorder 四分区（I1 = 只读复算 bit-exact）；解离 = 机械判据双跑
（输入面故障 → 形成结构恒等 + 知觉选择性失败）。
"""
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

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
from galatea.evidence.evaluator.sealed import GridCell
from galatea.evidence.evaluator.statplan import StatPlanViolation, load_stat_plan
from galatea.evidence.recorder.heartbeat import probe_recorder
from galatea.evidence.recorder.manifest import RunManifest
from galatea.evidence.recorder.replay import recompute_i1
from galatea.evidence.recorder.writer import EvidenceWriter
from galatea.kernel.clock import CycleClock
from galatea.kernel.digest import content_digest
from galatea.kernel.packet import ArtifactRef
from galatea.kernel.registry import Registry
from galatea.kernel.rng import RngDirectory, chacha8_block
from galatea.kernel.state import Stores
from galatea.subject.action.gateway import ActionSpec, CapabilityGateway, load_gateway_config
from galatea.subject.action.signature import derive_signing_key, verify
from galatea.subject.c1profile import C1Profile, load_c1_profile
from galatea.subject.control.intention import ActionIntention
from galatea.subject.models.body import build_body_belief
from galatea.subject.models.prediction import predict_window
from galatea.subject.models.world import WorldModel
from galatea.subject.perception.pipeline import PerceptionPipeline
from galatea.subject.sensorium.calibration import bind_calibration
from galatea.subject.sensorium.ingest import CARRIER_INTERO, CARRIER_PROPRIO
from galatea.subject.sensorium.pipeline import SensoriumPipeline, audit
from galatea.subject.sensorium.ports import (
    ExtLocalObsFeatures,
    InteroSensations,
    load_c0_sensorium_profile,
)

__all__ = [
    "C1Scenario", "load_c1_scenario", "C1RunRecord", "C1ModelsRunner", "run_c1_evaluation",
    "c1_accuracy_diffs", "c1_world_mse_diffs", "c1_criterion_diffs", "c1_ece_samples",
]

_EVAL_MASTER_SEED_C1 = b"c1-models-sealed"   # Q-L13-12① 同族：run 主种子（stat plan 内嵌 hex）
_TRIAL_LABEL = "c1.models"
_CARRIER_EXTERO = "channel.exteroceptive.received.v1"
_CARRIER_OUTCOME = "channel.outcome.received.v1"

#: 判据 2 扰动映射（评估侧反事实；N↔S、E↔W 置换——stat plan scramble_control）
_SCRAMBLE_MAP: dict[str, tuple[int, int]] = {"N": (0, -1), "S": (0, 1), "E": (-1, 0), "W": (1, 0)}


@dataclass(frozen=True, slots=True)
class C1Scenario:
    """场景冻结参数（stat plan scenario 节 typed 视图，fail-closed）。"""

    cycles: int
    moves: dict[int, str]
    rests: tuple[int, ...]
    uncommanded: dict[int, str]

    def post_move_windows(self) -> tuple[int, ...]:
        """判别窗 = 请求位移发生的窗（模型已积分位移、持续基线未积分）。"""
        return tuple(sorted(self.moves))

    def criterion1_windows(self) -> tuple[int, ...]:
        """判据 1 对照窗 = {u: ∃rest ∈ [u−2,u] ∧ 无 rest == u}（陈旧预测跨过 rest、
        当前预测未跨过——real(u)=|frame(u−1)−frame(u)| 只含 cycle u 的变化）。"""
        out: list[int] = []
        for u in range(self.cycles):
            lagged = any(u - 2 <= r <= u for r in self.rests)
            real = any(r == u for r in self.rests)
            if lagged and not real:
                out.append(u)
        return tuple(out)

    def requested_phase(self) -> tuple[int, ...]:
        """判据 3 对照臂 = 请求位移窗（模型已积分；stat plan 冻结）。"""
        return self.post_move_windows()

    def coercion_phase(self) -> tuple[int, ...]:
        """判据 3 处理臂 = 外源位移窗（无回执 → 模型未积分、预测退化为持续）。"""
        return tuple(sorted(self.uncommanded))


def load_c1_scenario(stat_plan_path: Path) -> C1Scenario:
    """场景冻结读取（stat plan digest 由 load_stat_plan 钉死后再读本节）。"""
    if not stat_plan_path.is_file():
        raise StatPlanViolation(f"stat plan not found: {stat_plan_path}")
    raw = cast(dict[str, Any], yaml.safe_load(stat_plan_path.read_text(encoding="utf-8")))
    header = cast(dict[str, Any], raw["stat_plan"])
    scenario = cast(dict[str, Any], header["scenario"])
    moves_raw = cast(dict[str, Any], scenario["action_schedule"]["moves"])
    uncmd_raw = cast(dict[str, Any], scenario["uncommanded_displacement"]["cycles"])
    return C1Scenario(
        cycles=int(scenario["cycles"]),
        moves={int(k): str(v) for k, v in moves_raw.items()},
        rests=tuple(int(x) for x in cast(list[Any], scenario["action_schedule"]["rests"])),
        uncommanded={int(k): str(v) for k, v in uncmd_raw.items()},
    )


@dataclass(frozen=True, slots=True)
class C1RunRecord:
    """单 run 证据记录（行集 + profile 绑定；指标由行集纯函数派生——I1 可复算）。"""

    run_index: int
    cell_id: str
    regime: str
    seed_hex: str
    window_rows: tuple[dict[str, Any], ...]     # 逐窗：后验/真值/窗值/预测 MSE/身体预测-帧值（判据 1 同行承载）
    pose_ambiguous: bool
    formation_counts: tuple[int, int, int]      # (frames, formation_receipts, gain_receipts)

    @property
    def digest(self) -> str:
        return content_digest({
            "run_index": self.run_index, "cell_id": self.cell_id, "seed_hex": self.seed_hex,
            "windows": list(self.window_rows),
            "pose_ambiguous": self.pose_ambiguous,
        })


class C1ModelsRunner:
    """C1 单 run 运行器（生产主体栈 + 真实通道流；冻结场景编排）。"""

    def __init__(self, root: Path, tmp_dir: Path) -> None:
        self._root = root
        self._tmp = tmp_dir
        self._m0_path = root / "config" / "profiles" / "m0_mw0.profile.yaml"
        self._profile: MW0Profile = load_profile(self._m0_path)
        self._c1: C1Profile = load_c1_profile()
        self._c0 = load_c0_sensorium_profile()
        self._calibration = bind_calibration(
            root / "config" / "profiles" / "c0_sensorium.profile.yaml", self._c0.calibration_version
        )
        delays = self._profile.params.channel_delay_cycles
        self._time_basis = {
            _CARRIER_EXTERO: int(delays["exteroceptive"]),
            CARRIER_INTERO: int(delays["interoceptive"]),
            CARRIER_PROPRIO: int(delays["proprioceptive"]),
        }
        self._gateway_config = load_gateway_config(
            root / "config" / "profiles" / "m0_gateway.profile.yaml",
            root / "config" / "profiles" / "f0_action_contract.profile.yaml",
        )
        self._profile_digests: tuple[tuple[str, str], ...] = (
            ("m0_mw0", content_digest(self._m0_path.read_text(encoding="utf-8"))),
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

    def run_trial(
        self, seed: bytes, scenario: C1Scenario, trial_id: str, cell_id: str,
        extero_fault_from: int | None = None,
    ) -> C1RunRecord:
        """单 run；extero_fault_from = 解离机械判据的输入面故障注入点（None = 完好）。"""
        trial_dir = self._tmp / re.sub(r"[^A-Za-z0-9_-]", "_", trial_id)
        trial_dir.mkdir(parents=True, exist_ok=True)
        stores = Stores(trial_dir / "stores")
        try:
            return self._run_in(seed, scenario, trial_id, cell_id, trial_dir, stores, extero_fault_from)
        finally:
            stores.close()
            shutil.rmtree(trial_dir, ignore_errors=True)

    def _run_in(
        self, seed: bytes, scenario: C1Scenario, trial_id: str, cell_id: str,
        trial_dir: Path, stores: Stores, extero_fault_from: int | None,
    ) -> C1RunRecord:
        registry = Registry(trial_dir / "registry", stores, CycleClock())
        world = MW0World(self._profile.params, RngDirectory(seed, chacha8_block), branch_id="B")
        dynamics = MW0Dynamics(world, self._profile, RngDirectory(seed, chacha8_block), branch_id="B")
        signing_key = derive_signing_key(seed)
        gateway = CapabilityGateway(
            self._gateway_config, signing_key, run_id="R", branch_id="B", subject_candidate_id="S"
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
        world_real = WorldModel(self._c1, "R")
        world_scram = WorldModel(self._c1, "R.scram", direction_vectors=_SCRAMBLE_MAP)

        pending_actions: list[tuple[int, str]] = []     # 请求位移（主体平面：自身命令）
        pending_receipts: list[tuple[int, str]] = []    # (action_cycle, effect)
        truth_snaps: dict[int, tuple[tuple[int, int], tuple[bool, ...]]] = {}
        pending_preds: dict[int, dict[str, Any]] = {}   # target_t → {pred, pred_scram, mask}
        prev_window: list[float] | None = None
        window_rows: list[dict[str, Any]] = []
        body_preds: dict[int, tuple[float, float]] = {}   # target_t → (energy, integrity)
        formation_counts = (0, 0, 0)
        pose_ambiguous = False
        cmd_seq = 0

        for delivery in range(scenario.cycles):
            # —— 请求动作（gateway 签名路径；回执经 outcome 通道延迟 1）——
            if delivery in scenario.moves:
                direction = scenario.moves[delivery]
                key = f"c1m{cmd_seq}"
                cmd_seq += 1
                intention = ActionIntention(
                    intention_id=f"i-{key}", selected_proposal_id="c1-eval",
                    arbitration_trace="eval", deadline=delivery + 8,
                    budget_hint=None, idempotency_key=key,
                )
                decision, command = gateway.authorize(
                    intention, ActionSpec("move", direction),
                    subject_candidate_id="S", run_id="R", branch_id="B", virtual_time=delivery,
                )
                if command is None:
                    raise RuntimeError(f"{trial_id}: move command rejected: {decision.reason_code}")
                if not verify(
                    signing_key, command.gateway_signature,
                    command_id=command.command_id, requested_action=command.requested_action,
                    budget=command.budget, deadline=command.deadline,
                    idempotency_key=command.idempotency_key,
                ):
                    raise RuntimeError(f"{trial_id}: signature verification failed")
                fact = dynamics.apply(
                    DynCommand(primitive=Primitive.MOVE, param=direction, command_id=command.command_id),
                    InterventionRegistry(), delivery,
                )
                outcome.render_and_submit(
                    delivery, ArtifactRef(digest=world.state_digest(), kind="world_state_ref"),
                    command.command_id, fact.effective_effect,
                )
                pending_actions.append((delivery, direction))
            elif delivery in scenario.rests:
                key = f"c1r{cmd_seq}"
                cmd_seq += 1
                intention = ActionIntention(
                    intention_id=f"i-{key}", selected_proposal_id="c1-eval",
                    arbitration_trace="eval", deadline=delivery + 8,
                    budget_hint=None, idempotency_key=key,
                )
                decision, command = gateway.authorize(
                    intention, ActionSpec("rest", None),
                    subject_candidate_id="S", run_id="R", branch_id="B", virtual_time=delivery,
                )
                if command is None:
                    raise RuntimeError(f"{trial_id}: rest command rejected: {decision.reason_code}")
                fact = dynamics.apply(
                    DynCommand(primitive=Primitive.REST, param=None, command_id=command.command_id),
                    InterventionRegistry(), delivery,
                )
                outcome.render_and_submit(
                    delivery, ArtifactRef(digest=world.state_digest(), kind="world_state_ref"),
                    command.command_id, fact.effective_effect,
                )
            # —— 无命令外源位移（判据 3 操纵；无 EffectFact/无回执/无主体可见信号）——
            if delivery in scenario.uncommanded:
                world.apply_primitive(Primitive.MOVE, scenario.uncommanded[delivery])

            events = dynamics.step()
            truth_ref = ArtifactRef(digest=world.state_digest(), kind="world_state_ref")
            extero.render_and_submit(delivery, truth_ref)
            intero.render_and_submit(delivery, truth_ref, events)
            proprio.render_and_submit(delivery, truth_ref)
            truth_snaps[delivery] = _truth_snapshot(world, self._profile.params.grid_size)
            delivered = bus.deliver(delivery)
            packets: list[tuple[Any, str]] = []
            for packet in delivered.packets:
                if packet.content_type == _CARRIER_OUTCOME:
                    blob = registry.get(
                        ArtifactRef(digest=packet.payload_ref.digest, kind="payload")
                    ).blob
                    try:
                        payload = json.loads(blob)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue    # 回执损坏 → 主体不可读（schema 失败语义；缺失即无回执）
                    effect = str(payload["effect"])
                    if effect.startswith("move_") and effect.endswith("_arrived"):
                        pending_receipts.append((delivery - 1, effect))   # 延迟 1 → action_cycle
                    continue
                blob = registry.get(ArtifactRef(digest=packet.payload_ref.digest, kind="payload")).blob
                try:
                    payload = json.loads(blob)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue    # 传输损坏 → 主体侧不可解析（schema 失败语义），不补零
                if (
                    extero_fault_from is not None and delivery >= extero_fault_from
                    and payload.get("kind") == "observation_window"
                ):
                    payload = {"kind": "observation_window", "window": _faulted_window(payload["window"])}
                    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
                # REV-0014 R1：registry blob 恒为 bytes（kernel/registry.py）——必须显式
                # decode；str(bytes) 产生 repr 包装使每一包被判损坏（提交态序列化回归，
                # 评审实证 run#0 修复后 digest 与归档 bit-exact 恒等）
                text_payload = blob.decode("utf-8")
                packets.append((packet, text_payload))
            cycle_out = sensorium.process_cycle(delivery, packets)
            formation_counts = (
                formation_counts[0] + len(cycle_out.frames),
                formation_counts[1] + len(cycle_out.formation_receipts),
                formation_counts[2] + len(cycle_out.gain_receipts),
            )
            audit(cycle_out.frames, cycle_out.formation_receipts, cycle_out.gain_receipts)
            frames_by_t: dict[int, list[Any]] = {}
            for frame in cycle_out.frames:
                frames_by_t.setdefault(frame.effective_time, []).append(frame)

            run_index = _run_index_of(trial_id)
            for t in sorted(frames_by_t):
                frames = tuple(frames_by_t[t])
                extero_frame = next((f for f in frames if f.modality.value == "EXT_LOCAL_OBS"), None)
                intero_frame = next((f for f in frames if f.modality.value == "INTERO"), None)
                body_frame = (
                    (intero_frame.features.energy_level, intero_frame.features.integrity_level)
                    if intero_frame is not None and isinstance(intero_frame.features, InteroSensations)
                    else None
                )
                if extero_frame is None or not isinstance(extero_frame.features, ExtLocalObsFeatures):
                    continue    # 损坏致窗帧缺失 → 该窗不入统计（unknown_handling）
                window_vals = [float(v) for row in extero_frame.features.window for v in row]
                perc = perception.process_window(t, frames)
                # （1）结算到期的预测：prediction(t) vs 窗 t 实际值（严格对齐）
                pending = pending_preds.pop(t, None)
                snap = truth_snaps.get(t)
                posterior_by_offset = {(c.dx, c.dy): c.posterior_present for c in perc.cells}
                posteriors = [posterior_by_offset.get((c - 2, r - 2)) for r in range(5) for c in range(5)]
                body_pred = body_preds.get(t)
                row: dict[str, Any] = {
                    "run_index": run_index, "t": t,
                    "posteriors": posteriors,
                    "truth": list(snap[1]) if snap is not None else [None] * 25,
                    "window": window_vals,
                    "body_frame": list(body_frame) if body_frame else None,
                    "body_pred": list(body_pred) if body_pred else None,
                    "pred": pending["pred"] if pending else None,
                    "pred_scram": pending["pred_scram"] if pending else None,
                    "mask": pending["mask"] if pending else None,
                    "prev_window": prev_window,
                    "mse_model_overlap": None, "mse_persist_overlap": None,
                    "mse_model_full": None, "mse_scram_full": None,
                    "peak": max(window_vals),
                }
                if pending is not None and pending["pred"] is not None:
                    row["mse_model_overlap"] = _mse(pending["pred"], window_vals, pending["mask"])
                    row["mse_persist_overlap"] = _mse(prev_window, window_vals, pending["mask"])
                    row["mse_model_full"] = _mse(pending["pred"], window_vals, None)
                    row["mse_scram_full"] = (
                        _mse(pending["pred_scram"], window_vals, None)
                        if pending["pred_scram"] is not None else None
                    )
                window_rows.append(row)
                # （2）两相消费（渲染时序对齐）：合并相 = 动作 ≤t（窗 t 渲染前发生）；
                # 推进相 = 动作 ==t+1（窗 t+1 渲染前发生——预测位姿面）
                merge_actions = [(c, d) for c, d in pending_actions if c <= t]
                advance_actions = [(c, d) for c, d in pending_actions if c == t + 1]
                pending_actions = [(c, d) for c, d in pending_actions if c > t + 1]
                merge_receipts = [e for ac, e in pending_receipts if ac <= t]
                advance_receipts = [e for ac, e in pending_receipts if ac == t + 1]
                pending_receipts = [(ac, e) for ac, e in pending_receipts if ac > t + 1]
                belief_real = world_real.update(
                    t, perc.cells, tuple(merge_receipts), (), tuple(d for _, d in merge_actions)
                )
                belief_scram = world_scram.update(
                    t, perc.cells, tuple(merge_receipts), (), tuple(d for _, d in merge_actions)
                )
                pose_ambiguous = pose_ambiguous or len(belief_real.pose_candidates) > 1
                # （3）推进至窗 t+1 位姿（渲染前动作积分）→ 发布 prediction(t+1)
                belief_real = world_real.advance(
                    t + 1, tuple(advance_receipts), tuple(d for _, d in advance_actions)
                )
                belief_scram = world_scram.advance(
                    t + 1, tuple(advance_receipts), tuple(d for _, d in advance_actions)
                )
                pred_next = predict_window(belief_real, self._c1, t + 1)
                scram_next = predict_window(belief_scram, self._c1, t + 1)
                pose_next = belief_real.pose_candidates[0].position
                known_next = world_real.known_cells()
                pending_preds[t + 1] = {
                    "pred": (
                        [float(v) for r_ in pred_next[0].expected_window for v in r_]
                        if pred_next and pred_next[0].expected_window is not None else None
                    ),
                    "pred_scram": (
                        [float(v) for r_ in scram_next[0].expected_window for v in r_]
                        if scram_next and scram_next[0].expected_window is not None else None
                    ),
                    "mask": [
                        (pose_next[0] + c - 2, pose_next[1] + r_ - 2) in known_next
                        for r_ in range(5) for c in range(5)
                    ],
                }
                body = _body_belief_values(frames)
                if body is not None:
                    body_preds[t + 1] = body
                prev_window = window_vals

        return C1RunRecord(
            run_index=_run_index_of(trial_id),
            cell_id=cell_id,
            regime=cell_id.split(":")[0],
            seed_hex=seed.hex(),
            window_rows=tuple(window_rows),
            pose_ambiguous=pose_ambiguous,
            formation_counts=formation_counts,
        )


def _faulted_window(window: list[list[Any]]) -> list[list[Any]]:
    """输入面故障注入：窗[0][0] = 5.0（域出；形成层无域检 → 照常成帧，知觉 OOD）。"""
    corrupted = [list(row) for row in window]
    corrupted[0][0] = 5.0
    return corrupted


def _run_index_of(trial_id: str) -> int:
    suffix = trial_id.split("#")[-1]
    try:
        return int(suffix)
    except ValueError:
        return -1    # 解离机械判据双跑（不进入指标向量）


def _body_belief_values(frames: tuple[Any, ...]) -> tuple[float, float] | None:
    """内感受/本体感受帧 → 身体持续性预测值（T1 先行；预测目标 = 下一窗）。"""
    intero = next((f for f in frames if f.modality.value == "INTERO"), None)
    proprio = next((f for f in frames if f.modality.value == "PROPRIO"), None)
    if intero is None:
        return None
    belief = build_body_belief(intero, proprio, "body.eval", intero.effective_time)
    return (belief.energy_belief, belief.integrity_belief)


def _truth_snapshot(world: MW0World, grid_size: int) -> tuple[tuple[int, int], tuple[bool, ...]]:
    """evaluator 侧真值快照（主体不可见）：body_pos + 25 格 resource 在场（行优先窗序）。"""
    bx, by = world.body_cell_pos()
    flags: list[bool] = []
    for r in range(5):
        for c in range(5):
            dx, dy = c - 2, r - 2
            cell = ((bx + dx) % grid_size, (by + dy) % grid_size)
            flags.append(world.grid_kind(cell) == "resource")
    return ((bx, by), tuple(flags))


def _mse(pred: list[float] | None, actual: list[float], mask: list[bool] | None) -> float | None:
    if pred is None:
        return None
    pairs = [
        (p, a) for p, a, m in zip(pred, actual, mask if mask is not None else [True] * len(actual))
        if m
    ]
    if not pairs:
        return None
    return sum((p - a) ** 2 for p, a in pairs) / len(pairs)


# ---- 指标纯函数（runner 行集 → 判定器输入；I1 复算共用） ----

def c1_ece_samples(records: tuple[C1RunRecord, ...]) -> tuple[tuple[float, bool], ...]:
    """校准样本：(posterior, truth_present)；域出格（posterior None）剔除（unknown_handling）。"""
    out: list[tuple[float, bool]] = []
    for record in records:
        for row in record.window_rows:
            for posterior, truth in zip(row["posteriors"], row["truth"]):
                if posterior is None or truth is None:
                    continue
                out.append((float(posterior), bool(truth)))
    return tuple(out)


def c1_accuracy_diffs(records: tuple[C1RunRecord, ...]) -> tuple[float, ...]:
    """per-run 准确率差：model（posterior ≥ 0.5 判 present）− 多数类基线（恒判 absent）。"""
    diffs: list[float] = []
    for record in records:
        model_correct = 0
        base_correct = 0
        n = 0
        for row in record.window_rows:
            for posterior, truth in zip(row["posteriors"], row["truth"]):
                if posterior is None or truth is None:
                    continue
                model_correct += int((float(posterior) >= 0.5) == bool(truth))
                base_correct += int(not bool(truth))
                n += 1
        if n == 0:
            raise ValueError(f"run #{record.run_index}: no calibration samples（unknown_handling 违约）")
        diffs.append(model_correct / n - base_correct / n)
    return tuple(diffs)


def c1_world_mse_diffs(records: tuple[C1RunRecord, ...], scenario: C1Scenario) -> tuple[float, ...]:
    """per-run MSE 差（判别窗 = 请求位移窗）：persistence − model（重叠格；>0 为模型优）。"""
    windows = set(scenario.post_move_windows())
    diffs: list[float] = []
    for record in records:
        pairs = [
            (row["mse_persist_overlap"], row["mse_model_overlap"])
            for row in record.window_rows
            if row["t"] in windows and row["mse_model_overlap"] is not None
        ]
        if not pairs:
            raise ValueError(f"run #{record.run_index}: no post-move MSE pairs")
        diffs.append(sum(p - m for p, m in pairs) / len(pairs))
    return tuple(diffs)


def c1_criterion_diffs(
    records: tuple[C1RunRecord, ...], scenario: C1Scenario
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
    """三判据 per-run 配对差（stat plan 冻结式；全部 >0 为模型/跟踪优）。"""
    crit1_windows = set(scenario.criterion1_windows())
    req_windows = set(scenario.requested_phase())
    coe_windows = set(scenario.coercion_phase())
    crit1: list[float] = []
    crit2: list[float] = []
    crit3: list[float] = []
    for record in records:
        # 判据 1：|pred(u−2)−frame(u)| − |pred(u)−frame(u)|（L1，energy+integrity）
        body_by_t = {int(r["t"]): r for r in record.window_rows}
        diffs1: list[float] = []
        for u in sorted(crit1_windows):
            current = body_by_t.get(u)
            stale = body_by_t.get(u - 2)
            if current is None or stale is None:
                continue    # 帧缺失（损坏）→ 剔除留痕（unknown_handling）
            if (current["body_pred"] is None or current["body_frame"] is None
                    or stale["body_pred"] is None):
                continue    # 预测源/陈旧源窗帧缺失（损坏面）
            real = abs(current["body_pred"][0] - current["body_frame"][0]) + abs(
                current["body_pred"][1] - current["body_frame"][1])
            lagged = abs(stale["body_pred"][0] - current["body_frame"][0]) + abs(
                stale["body_pred"][1] - current["body_frame"][1])
            diffs1.append(lagged - real)
        if not diffs1:
            raise ValueError(f"run #{record.run_index}: no criterion-1 contrast windows")
        crit1.append(sum(diffs1) / len(diffs1))
        # 判据 2：全窗 MSE（扰动映射 − 真实映射），判别窗
        windows = set(scenario.post_move_windows())
        diffs2 = [
            row["mse_scram_full"] - row["mse_model_full"]
            for row in record.window_rows
            if row["t"] in windows and row["mse_scram_full"] is not None
        ]
        if not diffs2:
            raise ValueError(f"run #{record.run_index}: no criterion-2 pairs")
        crit2.append(sum(diffs2) / len(diffs2))
        # 判据 3：模型预测误差（重叠格）请求位移窗 vs 外源位移窗，条件 peak ≥ 0.1（冻结阈）
        req = [row["mse_model_overlap"] for row in record.window_rows
               if row["t"] in req_windows and row["mse_model_overlap"] is not None
               and row["peak"] >= 0.1]
        coe = [row["mse_model_overlap"] for row in record.window_rows
               if row["t"] in coe_windows and row["mse_model_overlap"] is not None
               and row["peak"] >= 0.1]
        if not req or not coe:
            raise ValueError(f"run #{record.run_index}: criterion-3 conditioning emptied a phase")
        crit3.append(sum(coe) / len(coe) - sum(req) / len(req))
    return tuple(crit1), tuple(crit2), tuple(crit3)


# ---- 评价编排（recorder + I1 + 解离机械判据） ----

def _trial_seed(master: bytes, index: int) -> bytes:
    """trial 种子派生（stat plan seed_derivation 冻结式：sha256("{label}|{index}" + master)）。"""
    sub = __import__("hashlib").sha256(f"{_TRIAL_LABEL}|{index}".encode("utf-8") + master).hexdigest()
    return bytes.fromhex(sub)


def run_c1_evaluation(
    root: Path, run_dir: Path, tmp_dir: Path, sealed_cells: tuple[GridCell, ...],
    stat_plan_path: Path, split_digest: str, n_limit: int | None = None,
) -> tuple[tuple[C1RunRecord, ...], dict[str, bool], str, str, bool]:
    """C1 正式评价编排：recorder 前置探测 → 逐 run（sealed 单元驱动）→ 四分区落盘
    → 解离机械判据双跑（run#0 种子复用）→ I1 复算。

    返回 (records, mechanical_checks, stat_plan_digest, split_digest, i1_match)。
    n_limit 仅为测试截断 affordance（0/负数即拒）；正式评价不传。
    """
    if n_limit is not None and n_limit <= 0:
        raise ValueError("n_limit must be positive when provided")
    probe_recorder(run_dir)
    plan = load_stat_plan(stat_plan_path)
    claim = next((c for c in plan.claims if c.claim_id == "c1_perception_tracking"), None)
    if claim is None:
        raise StatPlanViolation("stat plan missing frozen claim c1_perception_tracking")
    n = claim.n if n_limit is None else min(n_limit, claim.n)
    scenario = load_c1_scenario(stat_plan_path)
    runner = C1ModelsRunner(root, tmp_dir)

    stores = Stores(run_dir / "stores")
    try:
        registry = Registry(run_dir / "registry", stores, CycleClock())
        writer = EvidenceWriter(registry)
        writer.add_manifest(
            RunManifest.create(
                "c1-models-sealed-evaluation", _EVAL_MASTER_SEED_C1.hex(), "B",
                runner.profile_digests, plan.digest, split_digest,
            )
        )
        records: list[C1RunRecord] = []
        for p in range(n):
            cell = sealed_cells[p % len(sealed_cells)]
            seed = _trial_seed(_EVAL_MASTER_SEED_C1, p)
            record = runner.run_trial(
                seed, scenario, f"c1.models#{p}", cell.cell_id
            )
            records.append(record)
            writer.add("evidence", _run_summary_row(record))
            for row in record.window_rows:
                writer.add("trace", row)
        # —— 解离机械判据双跑（run#0 种子；输入面故障严格下游于形成）——
        seed0 = _trial_seed(_EVAL_MASTER_SEED_C1, 0)
        intact = runner.run_trial(seed0, scenario, "c1.dissoc.intact", sealed_cells[0].cell_id)
        faulted = runner.run_trial(
            seed0, scenario, "c1.dissoc.fault", sealed_cells[0].cell_id, extero_fault_from=4
        )
        mechanical = _dissociation_checks(intact, faulted)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        shutil.rmtree(run_dir / "scratch", ignore_errors=True)

        # 指标向量 digest（I1 复算核）
        acc = c1_accuracy_diffs(tuple(records))
        mse = c1_world_mse_diffs(tuple(records), scenario)
        c1v, c2v, c3v = c1_criterion_diffs(tuple(records), scenario)
        vector_digest = content_digest({
            "accuracy": list(acc), "mse": list(mse),
            "crit1": list(c1v), "crit2": list(c2v), "crit3": list(c3v),
        })
        writer.add("metrics", {
            "n": n, "vector_digest": vector_digest,
            "dissociation": {k: bool(v) for k, v in mechanical.items()},
        })
        refs = writer.close()

        def _recompute(partitions: dict[str, list[dict[str, Any]]]) -> str:
            rows = sorted(
                partitions["trace"],
                key=lambda r: (int(r["run_index"]), int(r["t"])),
            )
            rebuilt_records = _rebuild_records(rows)
            acc2 = c1_accuracy_diffs(rebuilt_records)
            mse2 = c1_world_mse_diffs(rebuilt_records, scenario)
            a2, b2, c_2 = c1_criterion_diffs(rebuilt_records, scenario)
            return content_digest({
                "accuracy": list(acc2), "mse": list(mse2),
                "crit1": list(a2), "crit2": list(b2), "crit3": list(c_2),
            })

        report = recompute_i1(registry, refs, _recompute, vector_digest)   # type: ignore[arg-type]
        return (
            tuple(records), mechanical, plan.digest, split_digest, report.match,
        )
    finally:
        stores.close()


def _run_summary_row(record: C1RunRecord) -> dict[str, Any]:
    return {
        "run_index": record.run_index, "cell_id": record.cell_id, "regime": record.regime,
        "seed_hex": record.seed_hex, "pose_ambiguous": record.pose_ambiguous,
        "formation_counts": list(record.formation_counts), "digest": record.digest,
    }


_LIST_FIELDS: tuple[str, ...] = (
    "posteriors", "truth", "window", "pred", "pred_scram", "mask",
    "prev_window", "body_frame", "body_pred",
)


def _decode_row(row: dict[str, Any]) -> dict[str, Any]:
    """Parquet/DuckDB 回读的 list 列为 JSON 字符串 → 解码（float64 数值面保持）。"""
    out: dict[str, Any] = {}
    for key, value in row.items():
        if key in _LIST_FIELDS and isinstance(value, str):
            out[key] = json.loads(value)
        else:
            out[key] = value
    return out


def _rebuild_records(window_rows: list[dict[str, Any]]) -> tuple[C1RunRecord, ...]:
    """I1 复算重建：trace 行 → C1RunRecord 行集（最小字段面，指标纯函数消费）。"""
    by_run: dict[int, list[dict[str, Any]]] = {}
    for raw in window_rows:
        row = _decode_row(raw)
        by_run.setdefault(int(row["run_index"]), []).append(row)
    return tuple(
        C1RunRecord(
            run_index=idx, cell_id=f"recomputed:{idx}", regime="recomputed", seed_hex="",
            window_rows=tuple(by_run[idx]),
            pose_ambiguous=False, formation_counts=(0, 0, 0),
        )
        for idx in sorted(by_run)
    )


def _dissociation_checks(intact: C1RunRecord, faulted: C1RunRecord) -> dict[str, bool]:
    """解离机械断言（stat plan dissociation_mechanical；M2 SC5 先例——机械判据不入统计 claim）。

    - formation_intact: 输入面故障下形成结构恒等（帧/回执/增益回执计数逐项相等，
      audit 双跑通过——形成义务无条件，fault 不上溯）
    - perception_selective_failure: 故障面 abstain 产成立且无对象信念；完好面有对象信念
    - degraded_confidence_drop: 故障面无任何 post posterior≥0.5 对象（置信面选择性塌缩）
    """
    formation_intact = intact.formation_counts == faulted.formation_counts
    intact_objects = sum(1 for row in intact.window_rows if row["posteriors"] and any(
        p is not None and p >= 0.5 for p in row["posteriors"]
    ))
    # 故障窗域 = effective t ≥ 3（fault 自 delivery 4 注入 → t≥3 窗全部带域出值）
    faulted_objects = sum(1 for row in faulted.window_rows
                          if row["t"] >= 3 and row["posteriors"] and any(
                              p is not None and p >= 0.5 for p in row["posteriors"]
                          ))
    return {
        "formation_intact": formation_intact,
        "intact_has_objects": intact_objects > 0,
        "faulted_no_objects": faulted_objects == 0,
    }
