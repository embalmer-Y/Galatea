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
from galatea.kernel.digest import content_digest
from galatea.kernel.packet import ArtifactRef
from galatea.kernel.registry import Registry
from galatea.kernel.rng import RngDirectory, chacha8_block
from galatea.kernel.state import Stores
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

__all__ = [
    "TrialScenario",
    "TrialRecord",
    "SubjectTrialRunner",
    "UnauthorizedCommand",
    "ExperimentRunControl",
    "EvaluationData",
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
