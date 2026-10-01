"""ExperimentRunControl：种子化 trial 编排与运行时边界校验（L13 §2.1-1/§10 control/runs.py）。

职责：运行编排（ExperimentRunControl vs subject loop 分离——本模块驱动 subject 管线，
不实现认知）；分支谱系登记（trial 级 run/seed/场景 digest）；**运行时边界校验**
（ADR-G-0005 口径③兑现：world.apply 前强制 gateway 签名验证，未签名/错签名 =
UnauthorizedCommand，fail closed）；profile digest 记录与一致性断言（ADR-G-0005 R8
在实验控制侧的落地：同一评价内全部 trial 的 profile digest 必须一致）。

M1 主体管线（接收侧动机→候选→五项清单）经本模块组装——主体侧输入仅来自
五通道 RECEIVED 信号（无真值读取；损坏包按 schema 失败语义跳过）。
"""
import hashlib
import json
import re
import shutil
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

from galatea.env.channels.adapter import ChannelBus
from galatea.env.channels.extero import ExteroceptiveChannel
from galatea.env.channels.intero import InteroceptiveChannel
from galatea.env.channels.language_stub import LanguageStubChannel
from galatea.env.channels.outcome import OutcomeChannel
from galatea.env.channels.proprio import ProprioceptiveChannel
from galatea.env.interventions.registry import InterventionRegistry, InterventionViolation
from galatea.env.profile import MW0Profile, RegimeName, load_profile
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
from galatea.kernel.packet import ArtifactRef, RepresentationLevel
from galatea.kernel.registry import Registry
from galatea.kernel.rng import RngDirectory, chacha8_block
from galatea.kernel.state import LineageTable, Stores
from galatea.subject.action.gateway import ActionSpec, CapabilityGateway, load_gateway_config
from galatea.subject.action.signature import derive_signing_key, verify
from galatea.subject.control.intention import ActionIntention
from galatea.subject.goals.candidates import CandidateLedger, GoalCandidate, SettleCriterion
from galatea.subject.goals.checklist import (
    ChecklistInputs,
    ChecklistVerdict,
    load_m1_goals_profile,
    run_checklist,
)
from galatea.subject.goals.motives import (
    Motive,
    MotiveSource,
    ViabilityEstimate,
    motive_opportunity,
    motive_request,
    motive_viability,
)
from galatea.subject.goals.ports import SettlePredicate
from galatea.subject.goals.request import ExternalRequest, RequestPhrasing, RequesterIdentity
from galatea.subject.memory.encode import encode_episodic
from galatea.subject.memory.ports import MemorySubsystem, SourceType
from galatea.subject.memory.retrieve import RetrievalQuery, retrieve
from galatea.subject.memory.store import MemoryStore, load_m2_continuity_profile

__all__ = [
    "TrialScenario",
    "TrialRecord",
    "SubjectTrialRunner",
    "UnauthorizedCommand",
    "ExperimentRunControl",
    "EvaluationData",
    "PathwayFault",
    "SC6Scenario",
    "SC6PairRecord",
    "CarryoverEvaluation",
    "load_sc6_scenario",
]

_WHITELIST = ("move", "forage", "eat", "rest", "look")   # f0_action_contract containment_whitelist_mw0
_RESOURCE_VISIBLE_THRESHOLD = 0.5   # 窗口资源检出阈（噪声 σ=0.05、近距增益 1.0；Q-L01-01）


class UnauthorizedCommand(PermissionError):
    """未签名/错签名命令抵达世界边界（L01 §6/L10 §6：S1，fail closed）。"""


@dataclass(frozen=True, slots=True)
class TrialScenario:
    """trial 场景参数（决策时点/能量轨迹/语句注入；全部经合法输入端口生效）。"""

    cycles: int
    decision_cycle: int
    moves_per_cycle: int = 0          # 世界侧能量轨迹操纵（viability 扰动轴）
    statement: tuple[str, str] | None = None   # (text, requester_label) 经 language 通道 typed 注入


@dataclass(frozen=True, slots=True)
class TrialRecord:
    """单 trial 证据记录（判定 + 谱系；digest = canonical JSON sha256）。"""

    trial_id: str
    seed_hex: str
    scenario: TrialScenario
    verdicts: tuple[tuple[str, str, str, str | None], ...]   # (candidate_id, source, decision, reason_code)
    hazard: bool
    energy_fraction: float
    resource_visible: bool
    profile_digests: tuple[tuple[str, str], ...]   # (profile id, content digest)——R8 匹配基料

    @property
    def digest(self) -> str:
        """内容 digest（**不含 trial_id**——label 非内容；复算比对由此成立）。"""
        return content_digest(
            {
                "seed_hex": self.seed_hex,
                "cycles": self.scenario.cycles,
                "decision_cycle": self.scenario.decision_cycle,
                "moves_per_cycle": self.scenario.moves_per_cycle,
                "statement": list(self.scenario.statement) if self.scenario.statement else None,
                "verdicts": [list(v) for v in self.verdicts],
                "hazard": self.hazard,
                "energy_fraction": self.energy_fraction,
                "resource_visible": self.resource_visible,
                "profile_digests": [list(p) for p in self.profile_digests],
            }
        )


class SubjectTrialRunner:
    """生产 trial 运行器（M1 主体 = 接收侧动机 → 候选 → 五项清单）。

    冻结物在构造时加载一次并计算 digest（R8：同一 runner 的全部 trial 共享
    同一 profile 实例集——评价内一致性由此机械保证）。
    """

    def __init__(self, root: Path, tmp_dir: Path) -> None:
        self._m0_profile_path = root / "config" / "profiles" / "m0_mw0.profile.yaml"
        self._profile = load_profile(self._m0_profile_path)
        self._goals_profile = load_m1_goals_profile()
        self._gateway_config = load_gateway_config(
            root / "config" / "profiles" / "m0_gateway.profile.yaml",
            root / "config" / "profiles" / "f0_action_contract.profile.yaml",
        )
        self._tmp_dir = tmp_dir
        self._profile_digests: tuple[tuple[str, str], ...] = (
            ("m0_mw0", content_digest(self._m0_profile_path.read_text(encoding="utf-8"))),
            ("m1_goals_min", content_digest(
                (root / "config" / "profiles" / "m1_goals_min.profile.yaml").read_text(encoding="utf-8")
            )),
        )

    @property
    def profile_digests(self) -> tuple[tuple[str, str], ...]:
        return self._profile_digests

    @property
    def mw0_profile(self) -> MW0Profile:
        """冻结世界 profile（SC6 regime 继承在其 typed params 上派生）。"""
        return self._profile

    def run_trial(self, seed: bytes, scenario: TrialScenario, trial_id: str) -> TrialRecord:
        """运行单 trial：世界→gateway（运行时签名校验）→通道→接收侧→清单判定。

        每 trial 独立 registry/stores 子目录（隔离事件序列）；结束先关三库连接
        （Windows 句柄锁会阻止删除）再清理目录——证据以 TrialRecord digest 与
        可复算种子承载，不依赖 blob 留存。
        """
        trial_dir = self._tmp_dir / re.sub(r"[^A-Za-z0-9_-]", "_", trial_id)
        trial_dir.mkdir(parents=True, exist_ok=True)
        stores = Stores(trial_dir / "stores")
        try:
            record = self._run_trial_in(seed, scenario, trial_id, trial_dir, stores)
        finally:
            stores.close()
            shutil.rmtree(trial_dir, ignore_errors=True)
        return record

    def _run_trial_in(
        self, seed: bytes, scenario: TrialScenario, trial_id: str, trial_dir: Path, stores: Stores
    ) -> TrialRecord:
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
        language = LanguageStubChannel(bus)

        received: list[tuple[int, str, dict[str, Any], str]] = []
        move_seq = 0
        for cycle in range(scenario.cycles):
            for _ in range(scenario.moves_per_cycle):
                key = f"m{move_seq}"
                move_seq += 1
                intention = ActionIntention(
                    intention_id=f"i-{key}", selected_proposal_id="trial", arbitration_trace="eval",
                    deadline=cycle + gateway.config.deadline_default_cycles,
                    budget_hint=None, idempotency_key=key,
                )
                decision, command = gateway.authorize(
                    intention, ActionSpec("move", "N"),
                    subject_candidate_id="S", run_id="R", branch_id="B", virtual_time=cycle,
                )
                if command is None:
                    raise UnauthorizedCommand(
                        f"trial {trial_id}: move command rejected at {decision.reason_code}"
                    )
                # 运行时边界校验（ADR-G-0005 口径③）：world.apply 前强制签名验证，fail closed
                if not verify(
                    signing_key, command.gateway_signature,
                    command_id=command.command_id, requested_action=command.requested_action,
                    budget=command.budget, deadline=command.deadline,
                    idempotency_key=command.idempotency_key,
                ):
                    raise UnauthorizedCommand(f"trial {trial_id}: signature verification failed")
                fact = dynamics.apply(
                    DynCommand(primitive=Primitive.MOVE, param="N", command_id=command.command_id),
                    InterventionRegistry(), cycle,
                )
                outcome.render_and_submit(
                    cycle, ArtifactRef(digest=world.state_digest(), kind="world_state_ref"),
                    command.command_id, fact.effective_effect,
                )
            if scenario.statement is not None:
                if scenario.decision_cycle < 2:
                    raise ValueError("statement requires decision_cycle >= 2（language 延迟 1 拍）")
                if cycle == 0:
                    language.submit_typed_statement(
                        cycle, ArtifactRef(digest=world.state_digest(), kind="world_state_ref"),
                        text=scenario.statement[0], requester=scenario.statement[1],
                    )
            events = dynamics.step()
            truth_ref = ArtifactRef(digest=world.state_digest(), kind="world_state_ref")
            extero.render_and_submit(cycle, truth_ref)
            intero.render_and_submit(cycle, truth_ref, events)
            proprio.render_and_submit(cycle, truth_ref)
            delivery = bus.deliver(cycle)
            for packet in delivery.packets:
                blob = registry.get(ArtifactRef(digest=packet.payload_ref.digest, kind="payload")).blob
                try:
                    payload = json.loads(blob)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue   # 传输损坏 → 主体侧不可解析（schema 失败语义），不补零
                received.append((cycle, str(payload["kind"]), payload, packet.event_id))

        estimate, opportunity, request = self._context_from_received(received, scenario.decision_cycle)
        verdicts = self._run_checklist(estimate, opportunity, request, scenario.decision_cycle)
        window_peak = self._latest_window_peak(received, scenario.decision_cycle)
        return TrialRecord(
            trial_id=trial_id,
            seed_hex=seed.hex(),
            scenario=scenario,
            verdicts=verdicts,
            hazard=estimate.hazard_energy_depleted_unrecovered,
            energy_fraction=self._latest_energy(received, scenario.decision_cycle),
            resource_visible=window_peak > _RESOURCE_VISIBLE_THRESHOLD,
            profile_digests=self._profile_digests,
        )

    # ---- 接收侧 → 主体管线（与 tests/env/test_m1_sc3_sc4.py 同一语义；生产版）----

    @staticmethod
    def _latest_energy(received: list[tuple[int, str, dict[str, Any], str]], decision_cycle: int) -> float:
        for cycle, kind, payload, _eid in reversed(received):
            if kind == "interoceptive_state" and cycle <= decision_cycle:
                return float(payload["energy"])  # type: ignore[arg-type]
        raise AssertionError("interoceptive signal must be delivered")

    @staticmethod
    def _latest_window_peak(received: list[tuple[int, str, dict[str, Any], str]], decision_cycle: int) -> float:
        for cycle, kind, payload, _eid in reversed(received):
            if kind == "observation_window" and cycle <= decision_cycle:
                window = [[float(v) for v in row] for row in payload["window"]]  # type: ignore[arg-type]
                return max(max(row) for row in window)
        return 0.0

    @staticmethod
    def _context_from_received(
        received: list[tuple[int, str, dict[str, Any], str]], decision_cycle: int
    ) -> tuple[ViabilityEstimate, Motive | None, ExternalRequest | None]:
        intero = next(
            (s for s in reversed(received) if s[1] == "interoceptive_state" and s[0] <= decision_cycle), None
        )
        extero = next(
            (s for s in reversed(received) if s[1] == "observation_window" and s[0] <= decision_cycle), None
        )
        statement = next(
            (s for s in reversed(received) if s[1] == "typed_statement" and s[0] <= decision_cycle), None
        )
        if intero is None:
            raise AssertionError("interoceptive signal must be delivered before decision")
        depleted_on_record = any(
            kind == "interoceptive_state" and "energy_depleted" in [str(e) for e in payload["events"]]
            for cycle, kind, payload, _eid in received
            if cycle <= decision_cycle
        )
        energy = float(intero[2]["energy"])
        estimate = ViabilityEstimate(
            hazard_energy_depleted_unrecovered=depleted_on_record and energy == 0.0,
            integrity_damage_events=0,   # M1 不判危（Q-L08-09②）
            derivation_refs=(intero[3],),
            ts=decision_cycle,
        )
        opportunity: Motive | None = None
        if extero is not None:
            window = [[float(v) for v in row] for row in extero[2]["window"]]  # type: ignore[arg-type]
            peak = max(max(row) for row in window)
            if peak > _RESOURCE_VISIBLE_THRESHOLD:
                opportunity = motive_opportunity(
                    affordance_ref=extero[3], feasibility_est=min(1.0, peak),
                    evidence_refs=(extero[3],), ts=decision_cycle,
                )
        request: ExternalRequest | None = None
        if statement is not None:
            text = str(statement[2]["text"])
            requester_label = str(statement[2]["requester"])
            request = ExternalRequest(
                content_ref=f"stmt.{statement[3]}",
                requester=RequesterIdentity(requester_label),
                phrasing=RequestPhrasing.NEUTRAL,   # SC4 判定不依赖 phrasing（指纹不变性已验）
                phrasing_text=text,
                received_refs=(statement[3],),
            )
        return estimate, opportunity, request

    def _run_checklist(
        self, estimate: ViabilityEstimate, opportunity: Motive | None,
        request: ExternalRequest | None, decision_cycle: int,
    ) -> tuple[tuple[str, str, str, str | None], ...]:
        candidates: list[GoalCandidate] = [
            GoalCandidate(
                candidate_id="c.recovery", source_kind=MotiveSource.VIABILITY,
                motive_refs=motive_viability(estimate).evidence_refs, content_ref="goal.eat",
                settle=SettleCriterion(SettlePredicate.ENERGY_AT_LEAST, 0.5),
                required_primitives=("eat",),
                ttl_cycles=self._goals_profile.ttl_cycles,
                created_cycle=decision_cycle, urgency=motive_viability(estimate).urgency,
            )
        ]
        if opportunity is not None:
            candidates.append(
                GoalCandidate(
                    candidate_id="c.explore", source_kind=MotiveSource.OPPORTUNITY,
                    motive_refs=opportunity.evidence_refs, content_ref="goal.explore",
                    settle=SettleCriterion(SettlePredicate.PRIMITIVE_COMPLETION),
                    required_primitives=("look",),
                    ttl_cycles=self._goals_profile.ttl_cycles,
                    created_cycle=decision_cycle, urgency=opportunity.urgency,
                )
            )
        if request is not None:
            candidates.append(
                GoalCandidate(
                    candidate_id="c.request", source_kind=MotiveSource.REQUEST,
                    motive_refs=motive_request(request, decision_cycle).evidence_refs,
                    content_ref=request.content_ref,
                    settle=SettleCriterion(SettlePredicate.ENERGY_AT_LEAST, 0.5),
                    required_primitives=("eat",),
                    ttl_cycles=self._goals_profile.ttl_cycles,
                    created_cycle=decision_cycle, urgency=motive_request(request, decision_cycle).urgency,
                )
            )
        ledger = CandidateLedger(
            ttl_cycles=self._goals_profile.ttl_cycles, max_per_batch=self._goals_profile.max_per_batch
        )
        kept = ledger.submit_batch(tuple(candidates), decision_cycle)
        inputs = ChecklistInputs(
            capability_known=True, known_primitives=_WHITELIST,
            quota_slack={"look": 3, "eat": 3}, viability=estimate,
            supporting_non_request_motives=tuple(
                m for m in (motive_viability(estimate), opportunity) if m is not None
            ),
        )
        records: list[tuple[str, str, str, str | None]] = []
        for cand in kept:
            verdict: ChecklistVerdict = run_checklist(cand, inputs, self._goals_profile, decision_cycle)
            records.append(
                (cand.candidate_id, cand.source_kind.value, verdict.decision.value,
                 verdict.reason_code.value if verdict.reason_code else None)
            )
        return tuple(records)


@dataclass(frozen=True, slots=True)
class EvaluationData:
    """评价数据集（trial 记录 + 一致性断言结果）。"""

    claim_id: str
    records: tuple[TrialRecord, ...]
    profile_digest_uniform: bool     # R8：同一评价内 profile digest 全体一致

    @property
    def recompute_ok(self) -> bool:
        """复算标志：trial digest 唯一性 + profile 一致（确定性重放由 digest 链承载）。"""
        return self.profile_digest_uniform and len({r.digest for r in self.records}) == len(self.records)


# ==========================================================================
# SC6 正式 runner（REV-0009 R9 三点保真度；m2_continuity_carryover 首评前置）
#
# 保真度①regime 网格继承：round1/round2 世界以 sealed 网格单元的 regime 派生
#（typed params 构造期替换——min_dwell 语义只辖 mid-episode 切换，不辖场景构造）；
# 保真度②naive 断连经 fault：记忆通路断连 = PathwayFault 注册记录（检索 →
# fault_missing_signal typed unknown），非 Python 层 None——trace 分区留记录，
# 且两臂共享同一 round1 记忆库（memory_items_digest 恒等 ⇒ P12 数据面证明）；
# 保真度③ITT 流驱动臂构造：(l13, branch-assign) 冻结流按 episode 开始分配臂身份，
# 按分配分析（as-assigned），round1 单次运行两臂共享（分配不可见性 = 结构性）。
# ==========================================================================

_HAZARD_CONTENT = "hazard:energy_depleted"   # round1 危害经历内容锚（stat plan 场景冻结同源）
_SEALED_MASTER_SEED_HEX = "19" * 32          # Q-L13-11：sealed 分割主种子（运行前冻结，任意但先于结果钉死）


@dataclass(frozen=True, slots=True)
class PathwayFault:
    """记忆携带通路断连的 fault 记录（control-plane；检索失败语义 = MissingSignal）。

    与 env InterventionRegistry 分离——通道 fault 消费不查 target，混用会误伤
    全部通道投递（两臂观测轨迹必须恒同，唯一差异 = 通路断连本身）。
    """

    record_id: str
    target: str                       # "memory.carryover"
    registered_at_cycle: int
    from_cycle: int
    to_cycle: int
    kind: str = "fault"               # Q-L01-09⑦：丢失仅经 fault

    def __post_init__(self) -> None:
        if self.from_cycle <= self.registered_at_cycle:
            raise InterventionViolation("pathway fault must take effect after registration（先注册后生效）")

    def digest(self) -> str:
        return content_digest(
            {"record_id": self.record_id, "target": self.target, "kind": self.kind,
             "window": [self.from_cycle, self.to_cycle]}
        )


@dataclass(frozen=True, slots=True)
class SC6Scenario:
    """SC6 场景冻结参数（stat plan scenario 节的 typed 视图，fail-closed 读取）。"""

    round1_cycles: int
    round1_moves: int
    round2_cycles: int
    round2_decision: int
    fault_from: int
    fault_to: int


def load_sc6_scenario(stat_plan_path: Path) -> SC6Scenario:
    """场景冻结读取（stat plan digest 由 load_stat_plan 钉死后再读本节）。"""
    import yaml

    if not stat_plan_path.is_file():
        raise StatPlanViolation(f"stat plan not found: {stat_plan_path}")
    raw = cast(dict[str, Any], yaml.safe_load(stat_plan_path.read_text(encoding="utf-8")))
    header = cast(dict[str, Any], raw["stat_plan"])
    scenario = cast(dict[str, Any], header["scenario"])
    round1 = cast(dict[str, Any], scenario["round1"])
    round2 = cast(dict[str, Any], scenario["round2"])
    fault_from, fault_to = (int(x) for x in cast(list[Any], round2["fault_window_cycles"]))
    return SC6Scenario(
        round1_cycles=int(round1["cycles"]),
        round1_moves=int(round1["moves_per_cycle"]),
        round2_cycles=int(round2["cycles"]),
        round2_decision=int(round2["decision_cycle"]),
        fault_from=fault_from,
        fault_to=fault_to,
    )


@dataclass(frozen=True, slots=True)
class SC6PairRecord:
    """单配对证据记录（同种子跨臂；digest 不含 pair_index——label 非内容）。"""

    pair_index: int
    cell_id: str
    regime: str
    seed_hex: str
    assigned_arm: str                      # ITT 分配身份（as-assigned 记账）
    carry_aware: bool
    naive_aware: bool
    carry_mode: str                        # retrieved | fault_missing_signal | empty_unknown
    naive_mode: str
    memory_items_digest: str               # round1 记忆库内容 digest（两臂共享 ⇒ 恒等）
    intero_blocked_ok: bool                # 感知退化核验：fault 窗口内 intero 未到达
    pathway_fault_ref: str

    @property
    def digest(self) -> str:
        return content_digest(
            {
                "cell_id": self.cell_id, "regime": self.regime, "seed_hex": self.seed_hex,
                "assigned_arm": self.assigned_arm,
                "carry_aware": self.carry_aware, "naive_aware": self.naive_aware,
                "carry_mode": self.carry_mode, "naive_mode": self.naive_mode,
                "memory_items_digest": self.memory_items_digest,
                "intero_blocked_ok": self.intero_blocked_ok,
                "pathway_fault_ref": self.pathway_fault_ref,
            }
        )

    def to_row(self) -> dict[str, Any]:
        return {
            "pair_index": self.pair_index, "cell_id": self.cell_id, "regime": self.regime,
            "seed_hex": self.seed_hex, "assigned_arm": self.assigned_arm,
            "carry_aware": self.carry_aware, "naive_aware": self.naive_aware,
            "carry_mode": self.carry_mode, "naive_mode": self.naive_mode,
            "memory_items_digest": self.memory_items_digest,
            "intero_blocked_ok": self.intero_blocked_ok,
            "pathway_fault_ref": self.pathway_fault_ref,
        }

    def trace_rows(self) -> tuple[dict[str, Any], dict[str, Any]]:
        """每臂一行 trace（P12 数据探针消费：digest 恒等 + naive 断连机制）。"""
        return (
            {"pair_index": self.pair_index, "arm": "carry_memory", "role": (
                "assigned" if self.assigned_arm == "carry_memory" else "control"),
             "pathway_mode": self.carry_mode, "memory_items_digest": self.memory_items_digest,
             "pathway_fault_record_id": ""},
            {"pair_index": self.pair_index, "arm": "naive", "role": (
                "assigned" if self.assigned_arm == "naive" else "control"),
             "pathway_mode": self.naive_mode, "memory_items_digest": self.memory_items_digest,
             "pathway_fault_record_id": self.pathway_fault_ref},
        )


@dataclass(frozen=True, slots=True)
class CarryoverEvaluation:
    """carryover 首评数据集（判定器输入 + I1 复算 + 谱系绑定）。"""

    claim_id: str
    pairs: tuple[SC6PairRecord, ...]
    carry_aware: tuple[bool, ...]
    naive_aware: tuple[bool, ...]
    assignment_balance: tuple[int, int]        # (carry_memory, naive) ITT 分配计数
    profile_digests: tuple[tuple[str, str], ...]
    stat_plan_digest: str
    split_digest: str
    recorder_refs: tuple[tuple[str, str], ...]  # (partition, blob digest)
    i1_match: bool

    @property
    def vector_digest(self) -> str:
        return content_digest({"carry": list(self.carry_aware), "naive": list(self.naive_aware)})

    @property
    def recompute_ok(self) -> bool:
        """复算标志 = I1 bit-exact（recorder 数据 → 指标复算）。"""
        return self.i1_match


def _derive_regime_profile(profile: MW0Profile, regime: str) -> MW0Profile:
    """保真度①：regime 继承 = 构造期 typed params 派生。

    digest 保持冻结 profile 身份；regime 覆盖来自冻结 sealed 网格单元（场景参数，
    非 profile 改写）；min_dwell 辖 mid-episode 切换，不辖场景构造。
    """
    if regime not in {r.value for r in RegimeName}:
        raise ValueError(f"sealed cell regime not in frozen regime set: {regime!r}")
    return replace(profile, params=replace(profile.params, initial_regime=regime))


def _consult_carryover_pathway(
    store: MemoryStore, faults: tuple[PathwayFault, ...], query_cycle: int, m2_profile: Any
) -> tuple[bool, str]:
    """携带通路咨询：fault 活跃 → MissingSignal 语义（失明）；否则检索判定。"""
    if any(f.from_cycle <= query_cycle <= f.to_cycle for f in faults):
        return False, "fault_missing_signal"
    result = retrieve(store, m2_profile, RetrievalQuery(MemorySubsystem.EPISODIC, query_cycle))
    if isinstance(result, tuple):
        return any(r.content_ref == _HAZARD_CONTENT for r in result), "retrieved"
    return False, "empty_unknown"   # 空命中 = typed Unknown → not-aware（禁静默，计划 unknown_handling）


def _memory_items_digest(store: MemoryStore) -> str:
    items = store.list_subsystem(MemorySubsystem.EPISODIC)
    return content_digest(sorted((i.item_id, i.content_ref, i.created_cycle) for i in items))


def seal_split_master_seed() -> bytes:
    """sealed 分割主种子（Q-L13-11 冻结常数；bytes 形式）。"""
    return bytes.fromhex(_SEALED_MASTER_SEED_HEX)
class ExperimentRunControl:
    """claim 评价编排（冻结统计计划驱动）：种子枚举、臂/cell 分配、trial 收集。

    种子枚举（非采样）：master_seed 与 (claim, arm/cell, trial_index) 的 HKDF 派生——
    完全确定性、可复算、跨 claim 独立。
    """

    def __init__(self, runner: SubjectTrialRunner, master_seed: bytes = b"m1-first-evaluation") -> None:
        self._runner = runner
        self._master = master_seed

    def _trial_seed(self, label: str, index: int) -> bytes:
        sub = hashlib.sha256(f"{label}|{index}".encode("utf-8") + self._master).hexdigest()
        return bytes.fromhex(sub)

    def run_real_vs_pseudo(
        self, n_per_arm: int, pseudo_statement: tuple[str, str]
    ) -> tuple[EvaluationData, EvaluationData, EvaluationData]:
        """SC3 三臂：healthy（decision@20）vs depleted（decision@52，100-move 枯竭）
        vs depleted+伪理由注入（REQUEST 口头理由经 language 通道，决策前已投递）。

        配对设计：伪臂**复用 depleted 臂的种子**（同世界实现/同损坏流，唯一差异 =
        注入语句）——惰性判据（非 REQUEST 判定指纹恒等）因而是配对内比较。
        """
        healthy = self._run_arm("sc3.healthy", n_per_arm, TrialScenario(cycles=24, decision_cycle=20, moves_per_cycle=2))
        depleted = self._run_arm("sc3.depleted", n_per_arm, TrialScenario(cycles=56, decision_cycle=52, moves_per_cycle=2))
        pseudo = self._run_arm(
            "sc3.pseudo", n_per_arm,
            TrialScenario(cycles=56, decision_cycle=52, moves_per_cycle=2, statement=pseudo_statement),
            seed_label="sc3.depleted",
        )
        return healthy, depleted, pseudo

    def run_wording_cells(
        self, n_per_cell: int, cells: tuple[tuple[str, str], ...]
    ) -> dict[tuple[str, str], EvaluationData]:
        """SC4 析因 cell：(phrasing, requester_label) × n_per_cell（语句文本 = 冻结计划）。"""
        out: dict[tuple[str, str], EvaluationData] = {}
        for phrasing, label in cells:
            scenario = TrialScenario(
                cycles=4, decision_cycle=2, statement=(phrasing, label),
            )
            out[(phrasing, label)] = self._run_arm(f"sc4.{phrasing}.{label}", n_per_cell, scenario)
        return out

    def _run_arm(self, label: str, n: int, scenario: TrialScenario, seed_label: "str | None" = None) -> EvaluationData:
        records = tuple(
            self._runner.run_trial(self._trial_seed(seed_label or label, i), scenario, f"{label}#{i}") for i in range(n)
        )
        digests = {r.profile_digests for r in records}
        return EvaluationData(claim_id=label, records=records, profile_digest_uniform=len(digests) == 1)

    # ---- SC6 正式 runner（m2_continuity_carryover 首评；REV-0009 R9 三点保真度）----

    def _itt_assignment(self, n: int) -> tuple[str, ...]:
        """ITT 分配（Q-G00-11 冻结流 (l13, branch-assign)；episode 开始、主体不可见）。"""
        rng = RngDirectory(self._master, chacha8_block)
        stream = rng.stream("B", "l13", "branch-assign")
        return tuple("carry_memory" if stream.next_uint64() % 2 == 0 else "naive" for _ in range(n))

    def run_carryover(
        self, sealed_cells: tuple[GridCell, ...], run_dir: Path, stat_plan_path: Path, split_digest: str,
        n_limit: int | None = None,
    ) -> CarryoverEvaluation:
        """carryover 正式评价：recorder 前置探测 → ITT 分配 → 逐配对运行 → 四分区落盘 → I1 复算。

        sealed 单元驱动场景（保真度①）；两臂共享 round1 记忆库、断连仅经 PathwayFault
        （保真度②）；(l13, branch-assign) 驱动臂身份按分配记账（保真度③）。
        n_limit 仅为测试截断 affordance（0/负数即拒）；正式评价不传——n = 计划冻结值。
        """
        if n_limit is not None and n_limit <= 0:
            raise ValueError("n_limit must be positive when provided")
        probe_recorder(run_dir)   # recorder 故障即停（L13 §4.2）
        plan = load_stat_plan(stat_plan_path)
        claim = next((c for c in plan.claims if c.claim_id == "m2_continuity_carryover"), None)
        if claim is None:
            raise StatPlanViolation("stat plan missing frozen claim m2_continuity_carryover")
        n = claim.n if n_limit is None else min(n_limit, claim.n)
        scenario = load_sc6_scenario(stat_plan_path)
        assignment = self._itt_assignment(n)
        m2_profile = load_m2_continuity_profile()

        stores = Stores(run_dir / "stores")
        try:
            registry = Registry(run_dir / "registry", stores, CycleClock())
            writer = EvidenceWriter(registry)
            writer.add_manifest(
                RunManifest.create(
                    "m2-carryover-first-evaluation", self._master.hex(), "B",
                    self._runner.profile_digests, plan.digest, split_digest,
                )
            )
            scratch = run_dir / "scratch"
            pairs: list[SC6PairRecord] = []
            for p in range(n):
                cell = sealed_cells[p % len(sealed_cells)]
                seed = self._trial_seed("sc6.carryover", p)
                pair = self._run_sc6_pair(
                    p, cell, seed, assignment[p], scenario, m2_profile, scratch / f"pair{p:03d}"
                )
                pairs.append(pair)
                writer.add("evidence", pair.to_row())
                for trace_row in pair.trace_rows():
                    writer.add("trace", trace_row)
            shutil.rmtree(scratch, ignore_errors=True)

            carry = tuple(record.carry_aware for record in pairs)
            naive = tuple(record.naive_aware for record in pairs)
            vector_digest = content_digest({"carry": list(carry), "naive": list(naive)})
            writer.add("metrics", {"n": n, "vector_digest": vector_digest,
                                   "carry_aware_count": sum(carry), "naive_aware_count": sum(naive)})
            refs = writer.close()

            def _recompute(partitions: dict[str, list[dict[str, Any]]]) -> str:
                rows = sorted(partitions["evidence"], key=lambda r: int(r["pair_index"]))
                return content_digest(
                    {"carry": [bool(r["carry_aware"]) for r in rows],
                     "naive": [bool(r["naive_aware"]) for r in rows]}
                )

            report = recompute_i1(registry, refs, _recompute, vector_digest)   # type: ignore[arg-type]
            return CarryoverEvaluation(
                claim_id=claim.claim_id,
                pairs=tuple(pairs),
                carry_aware=carry,
                naive_aware=naive,
                assignment_balance=(assignment.count("carry_memory"), assignment.count("naive")),
                profile_digests=self._runner.profile_digests,
                stat_plan_digest=plan.digest,
                split_digest=split_digest,
                recorder_refs=tuple((name, ref.digest) for name, ref in sorted(refs.items())),
                i1_match=report.match,
            )
        finally:
            stores.close()

    def _run_sc6_pair(
        self, pair_index: int, cell: GridCell, seed: bytes, assigned_arm: str,
        scenario: SC6Scenario, m2_profile: Any, base: Path,
    ) -> SC6PairRecord:
        """单配对：round1（经历轮，regime 继承）一次运行，两臂共享其记忆库。"""
        if assigned_arm not in ("carry_memory", "naive"):
            raise ValueError(f"unknown ITT arm: {assigned_arm!r}")
        round1_dir = base / "round1"
        round1_dir.mkdir(parents=True, exist_ok=True)
        round1_stores = Stores(round1_dir / "stores")
        try:
            store = self._run_sc6_round1(seed, cell.regime, scenario, m2_profile, round1_dir, round1_stores)
            memory_digest = _memory_items_digest(store)
            fault = PathwayFault(
                record_id=f"pf.{pair_index:03d}", target="memory.carryover",
                registered_at_cycle=0, from_cycle=1, to_cycle=scenario.round2_cycles - 1,
            )
            carry_aware, carry_mode, intero_c = self._run_sc6_round2(
                seed, cell.regime, scenario, m2_profile, store, (), base / "round2-carry"
            )
            naive_aware, naive_mode, intero_n = self._run_sc6_round2(
                seed, cell.regime, scenario, m2_profile, store, (fault,), base / "round2-naive"
            )
            return SC6PairRecord(
                pair_index=pair_index, cell_id=cell.cell_id, regime=cell.regime,
                seed_hex=seed.hex(), assigned_arm=assigned_arm,
                carry_aware=carry_aware, naive_aware=naive_aware,
                carry_mode=carry_mode, naive_mode=naive_mode,
                memory_items_digest=memory_digest,
                intero_blocked_ok=intero_c and intero_n,
                pathway_fault_ref=fault.digest(),
            )
        finally:
            round1_stores.close()

    def _run_sc6_round1(
        self, seed: bytes, regime: str, scenario: SC6Scenario, m2_profile: Any, base: Path, stores: Stores
    ) -> MemoryStore:
        """经历轮（stat plan 场景冻结）：枯竭轨迹 + T6/危害编码 + episode 边界 checkpoint。"""
        profile = _derive_regime_profile(self._runner.mw0_profile, regime)
        store = MemoryStore(stores)
        lineage = LineageTable()
        world = MW0World(profile.params, RngDirectory(seed, chacha8_block), branch_id="B")
        dynamics = MW0Dynamics(world, profile, RngDirectory(seed, chacha8_block), branch_id="B")
        clock = CycleClock()
        registry = Registry(base / "registry", stores, clock)
        bus = ChannelBus(profile.params, registry, RngDirectory(seed, chacha8_block),
                         branch_id="B", interventions=InterventionRegistry())
        extero = ExteroceptiveChannel(bus, world)
        intero = InteroceptiveChannel(bus, world)
        proprio = ProprioceptiveChannel(bus, world)
        boundary_anchor = "ckpt.round1"
        move_seq = 0
        hazard_recorded = False
        for cycle in range(scenario.round1_cycles):
            for _ in range(scenario.round1_moves):
                dynamics.apply(
                    DynCommand(primitive=Primitive.MOVE, param="N", command_id=f"r1m{move_seq}"),
                    InterventionRegistry(), cycle,
                )
                move_seq += 1
            events = dynamics.step()
            truth_ref = ArtifactRef(digest=world.state_digest(), kind="world_state_ref")
            extero.render_and_submit(cycle, truth_ref)
            intero.render_and_submit(cycle, truth_ref, events)
            proprio.render_and_submit(cycle, truth_ref)
            delivery = bus.deliver(cycle)
            packet_digests = [p.payload_ref.digest[:16] for p in delivery.packets]
            if packet_digests and cycle % 64 == 0:   # T6 节拍编码（M2 冻结策略）
                encode_episodic(
                    store, m2_profile, f"r1.recv.{cycle}", f"recv:{cycle}:{'+'.join(packet_digests)}",
                    RepresentationLevel.RECEIVED, SourceType.SELF_GENERATED, cycle,
                    lineage_refs=(boundary_anchor,),
                )
            for event in events:
                if event.kind == "energy_depleted":
                    encode_episodic(
                        store, m2_profile, "r1.hazard.energy_depleted", _HAZARD_CONTENT,
                        RepresentationLevel.RECEIVED, SourceType.SELF_GENERATED, cycle,
                        lineage_refs=(boundary_anchor,),
                    )
                    hazard_recorded = True
            clock.advance()
        if not hazard_recorded:
            raise AssertionError("round1 scenario must deterministically produce energy_depleted")
        stores.checkpoint(
            checkpoint_id=boundary_anchor, lineage=lineage, parent_checkpoint_id=None,
            branch_id="B", virtual_time=scenario.round1_cycles,
            rng_directory=RngDirectory(seed, chacha8_block), profile_ref=profile.ref(),
        )
        return store

    def _run_sc6_round2(
        self, seed: bytes, regime: str, scenario: SC6Scenario, m2_profile: Any,
        store: MemoryStore, faults: tuple[PathwayFault, ...], base: Path,
    ) -> tuple[bool, str, bool]:
        """退化感知轮：intero 通道 fault 窗口覆盖决策点；通路咨询 = _consult_carryover_pathway。"""
        profile = _derive_regime_profile(self._runner.mw0_profile, regime)
        base.mkdir(parents=True, exist_ok=True)
        stores = Stores(base / "stores")
        try:
            world = MW0World(profile.params, RngDirectory(seed, chacha8_block), branch_id="B")
            dynamics = MW0Dynamics(world, profile, RngDirectory(seed, chacha8_block), branch_id="B")
            clock = CycleClock()
            interventions = InterventionRegistry()
            interventions.register(
                record_id="iflt", kind="fault", registered_at_cycle=0,
                from_cycle=scenario.fault_from, to_cycle=scenario.fault_to,
            )
            registry = Registry(base / "registry", stores, clock)
            bus = ChannelBus(profile.params, registry, RngDirectory(seed, chacha8_block),
                             branch_id="B", interventions=interventions)
            extero = ExteroceptiveChannel(bus, world)
            intero = InteroceptiveChannel(bus, world)
            proprio = ProprioceptiveChannel(bus, world)
            received_kinds: set[str] = set()
            for cycle in range(scenario.round2_cycles):
                events = dynamics.step()
                truth_ref = ArtifactRef(digest=world.state_digest(), kind="world_state_ref")
                extero.render_and_submit(cycle, truth_ref)
                intero.render_and_submit(cycle, truth_ref, events)
                proprio.render_and_submit(cycle, truth_ref)
                delivery = bus.deliver(cycle)
                if scenario.fault_from <= cycle <= scenario.fault_to:
                    for packet in delivery.packets:
                        blob = registry.get(
                            ArtifactRef(digest=packet.payload_ref.digest, kind="payload")
                        ).blob
                        try:
                            payload = json.loads(blob)
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            continue
                        received_kinds.add(str(payload["kind"]))
            intero_blocked_ok = "interoceptive_state" not in received_kinds
            aware, mode = _consult_carryover_pathway(store, faults, scenario.round2_decision, m2_profile)
            return aware, mode, intero_blocked_ok
        finally:
            stores.close()


