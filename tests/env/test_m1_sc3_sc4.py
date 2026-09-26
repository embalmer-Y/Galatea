"""MW0-SC3/SC4 实验台（L01 §4.6 / L08 §9 M1 行；统计协议 = config/evidence/stat_plans/m1_goals_sc3_sc4.yaml 冻结）。

SC3（请求/机会→目标采纳；真实理由 vs 伪理由，L08 §4.4）：
  ② 真实理由扰动 = viability 危害事件经世界侧能量轨迹操纵（合法通道）→ 采纳必须改变；
  ③ 伪理由注入 = REQUEST 口头理由经 language 通道 typed 注入 → 采纳必须不改变。
SC4（来源线索交叉操纵，Q-L08-06）：4 措辞 × 2 请求者经 language 通道注入 → 判定指纹全等。

本文件为**机械预演**（确定性判读）：正式 n=64/组 统计评价由 L13 evaluator 按
冻结统计计划执行（M1 退出单元）。主体侧输入全部来自五通道 RECEIVED 信号
（无真值读取；oracle 泄漏面 = SC1 探针管辖区）。
"""
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

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
from galatea.kernel.packet import ArtifactRef
from galatea.kernel.registry import Registry
from galatea.kernel.rng import RngDirectory, chacha8_block
from galatea.kernel.state import Stores
from galatea.subject.action.gateway import ActionSpec, CapabilityGateway, load_gateway_config
from galatea.subject.action.signature import derive_signing_key
from galatea.subject.control.intention import ActionIntention
from galatea.subject.goals.candidates import CandidateLedger, GoalCandidate, SettleCriterion
from galatea.subject.goals.checklist import ChecklistInputs, load_m1_goals_profile, run_checklist
from galatea.subject.goals.motives import (
    Motive,
    MotiveSource,
    ViabilityEstimate,
    motive_opportunity,
    motive_request,
    motive_viability,
)
from galatea.subject.goals.ports import SettlePredicate
from galatea.subject.goals.reason_probe import classify_probe
from galatea.subject.goals.request import ExternalRequest, RequestPhrasing, RequesterIdentity

_ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = _ROOT / "config" / "profiles" / "m0_mw0.profile.yaml"
STAT_PLAN_PATH = _ROOT / "config" / "evidence" / "stat_plans" / "m1_goals_sc3_sc4.yaml"
_GATEWAY_CONFIG = load_gateway_config(
    _ROOT / "config" / "profiles" / "m0_gateway.profile.yaml",
    _ROOT / "config" / "profiles" / "f0_action_contract.profile.yaml",
)
PROFILE = load_profile(PROFILE_PATH)
GOALS_PROFILE = load_m1_goals_profile()
STAT_PLAN_RAW = yaml.safe_load(STAT_PLAN_PATH.read_text(encoding="utf-8"))["stat_plan"]
WORDING_TEXTS: dict[str, str] = dict(STAT_PLAN_RAW["wording_texts"])
REQUESTER_LABELS: dict[str, str] = dict(STAT_PLAN_RAW["requester_labels"])

# 冻结白名单（f0_action_contract containment_whitelist_mw0；清单 C-1 静态检查源）
WHITELIST = ("move", "forage", "eat", "rest", "look")
_RESOURCE_VISIBLE_THRESHOLD = 0.5  # 窗口资源检出阈：噪声 σ=0.05、近距增益 1.0（Q-L01-01）——0.5 远离噪声底


@dataclass(frozen=True, slots=True)
class ReceivedSignal:
    """接收侧信号（通道 kind 由 payload 自带 kind 字段区分；event_id = RECEIVED 包 id）。"""

    cycle: int
    kind: str
    payload: dict[str, object]
    event_id: str


@dataclass(frozen=True, slots=True)
class VerdictRecord:
    """单候选判定记录（SC3/SC4 证据行）。"""

    candidate_id: str
    source_kind: str
    settle_predicate: str
    decision: str
    reason_code: str | None
    subject_side_reason_refs: tuple[str, ...]


def _received_log_to_context(log: tuple[ReceivedSignal, ...], decision_cycle: int) -> tuple[
    ViabilityEstimate, Motive | None, ExternalRequest | None
]:
    """从接收侧信号构造清单上下文（ViabilityEstimate / 机会动机 / 外部请求）。"""
    intero = next((s for s in reversed(log) if s.kind == "interoceptive_state" and s.cycle <= decision_cycle), None)
    extero = next((s for s in reversed(log) if s.kind == "observation_window" and s.cycle <= decision_cycle), None)
    statement = next(
        (s for s in reversed(log) if s.kind == "typed_statement" and s.cycle <= decision_cycle), None
    )
    if intero is None:
        raise AssertionError("interoceptive signal must be delivered before decision")
    latest = intero.payload
    # "在案"语义 = 接收历史中有 energy_depleted 事件（事件在其发生当拍的包里，
    # 不在最新包的当拍事件清单里）且最新能量仍处 0（未见恢复回执——本 run 无 eat/rest）。
    depleted_on_record = any(
        s.kind == "interoceptive_state" and "energy_depleted" in [str(e) for e in s.payload["events"]]  # type: ignore[arg-type]
        for s in log
        if s.cycle <= decision_cycle
    )
    energy = float(latest["energy"])  # type: ignore[arg-type]
    hazard = depleted_on_record and energy == 0.0
    estimate = ViabilityEstimate(
        hazard_energy_depleted_unrecovered=hazard,
        integrity_damage_events=0,  # M1 不判危（Q-L08-09②）
        derivation_refs=(intero.event_id,),
        ts=decision_cycle,
    )
    opportunity: Motive | None = None
    if extero is not None:
        window = [[float(v) for v in row] for row in extero.payload["window"]]  # type: ignore[arg-type]
        peak = max(max(row) for row in window)
        if peak > _RESOURCE_VISIBLE_THRESHOLD:
            opportunity = motive_opportunity(
                affordance_ref=extero.event_id,
                feasibility_est=min(1.0, peak),
                evidence_refs=(extero.event_id,),
                ts=decision_cycle,
            )
    request: ExternalRequest | None = None
    if statement is not None:
        text = str(statement.payload["text"])
        requester_label = str(statement.payload["requester"])
        identity = next(
            (k for k, v in REQUESTER_LABELS.items() if v == requester_label), None
        )
        if identity is None:
            raise AssertionError(f"unknown requester label: {requester_label}")
        phrasing = next(k for k, v in WORDING_TEXTS.items() if v == text)
        request = ExternalRequest(
            content_ref=f"stmt.{statement.event_id}",
            requester=RequesterIdentity(identity),
            phrasing=RequestPhrasing(phrasing),
            phrasing_text=text,
            received_refs=(statement.event_id,),
        )
    return estimate, opportunity, request


def _build_candidates(
    estimate: ViabilityEstimate,
    opportunity: Motive | None,
    request: ExternalRequest | None,
    decision_cycle: int,
) -> tuple[GoalCandidate, ...]:
    """三源候选（每源 ≤1，Q-L08-02）：探索（机会）/觅食恢复（viability）/请求进食（REQUEST）。"""
    candidates: list[GoalCandidate] = [
        GoalCandidate(
            candidate_id="c.recovery",
            source_kind=MotiveSource.VIABILITY,
            motive_refs=motive_viability(estimate).evidence_refs,
            content_ref="goal.eat",
            settle=SettleCriterion(SettlePredicate.ENERGY_AT_LEAST, 0.5),
            required_primitives=("eat",),
            ttl_cycles=GOALS_PROFILE.ttl_cycles,
            created_cycle=decision_cycle,
            urgency=motive_viability(estimate).urgency,
        )
    ]
    if opportunity is not None:
        candidates.append(
            GoalCandidate(
                candidate_id="c.explore",
                source_kind=MotiveSource.OPPORTUNITY,
                motive_refs=opportunity.evidence_refs,
                content_ref="goal.explore",
                settle=SettleCriterion(SettlePredicate.PRIMITIVE_COMPLETION),
                required_primitives=("look",),
                ttl_cycles=GOALS_PROFILE.ttl_cycles,
                created_cycle=decision_cycle,
                urgency=opportunity.urgency,
            )
        )
    if request is not None:
        candidates.append(
            GoalCandidate(
                candidate_id="c.request",
                source_kind=MotiveSource.REQUEST,
                motive_refs=motive_request(request, decision_cycle).evidence_refs,
                content_ref=request.content_ref,
                settle=SettleCriterion(SettlePredicate.ENERGY_AT_LEAST, 0.5),
                required_primitives=("eat",),
                ttl_cycles=GOALS_PROFILE.ttl_cycles,
                created_cycle=decision_cycle,
                urgency=motive_request(request, decision_cycle).urgency,
            )
        )
    return tuple(candidates)


def _sc_run(
    seed: bytes,
    cycles: int,
    decision_cycle: int,
    moves_per_cycle: int = 0,
    statement: "tuple[int, str, str] | None" = None,   # (cycle, text, requester_label)
    tmp: "Path | None" = None,
) -> tuple[tuple[VerdictRecord, ...], tuple[ReceivedSignal, ...], float]:
    """SC3/SC4 挂具：世界→通道→接收侧动机→候选→五项清单。

    返回（判定记录, 接收信号日志, 决策时刻能量水平）。主体侧输入仅来自
    RECEIVED 信号；清单输入 = 接收侧派生（Q-L08-09①②）。
    """
    registry = Registry(tmp / "registry", Stores(tmp / "stores"), CycleClock())  # type: ignore[arg-type]
    world = MW0World(PROFILE.params, RngDirectory(seed, chacha8_block), branch_id="B")
    dynamics = MW0Dynamics(world, PROFILE, RngDirectory(seed, chacha8_block), branch_id="B")
    signing_key = derive_signing_key(seed)
    gateway = CapabilityGateway(_GATEWAY_CONFIG, signing_key, run_id="R", branch_id="B", subject_candidate_id="S")
    bus = ChannelBus(PROFILE.params, registry, RngDirectory(seed, chacha8_block), branch_id="B",
                     interventions=InterventionRegistry())
    extero = ExteroceptiveChannel(bus, world)
    intero = InteroceptiveChannel(bus, world)
    proprio = ProprioceptiveChannel(bus, world)
    outcome = OutcomeChannel(bus)
    language = LanguageStubChannel(bus)

    received: list[ReceivedSignal] = []
    move_seq = 0
    for cycle in range(cycles):
        for _ in range(moves_per_cycle):
            key = f"m{move_seq}"
            move_seq += 1
            intention = ActionIntention(
                intention_id=f"i-{key}", selected_proposal_id="sc3", arbitration_trace="sc3",
                deadline=cycle + gateway.config.deadline_default_cycles,
                budget_hint=None, idempotency_key=key,
            )
            decision, command = gateway.authorize(
                intention, ActionSpec("move", "N"),
                subject_candidate_id="S", run_id="R", branch_id="B", virtual_time=cycle,
            )
            if command is None:
                continue
            fact = dynamics.apply(
                DynCommand(primitive=Primitive.MOVE, param="N", command_id=command.command_id),
                InterventionRegistry(), cycle,
            )
            outcome.render_and_submit(
                cycle, ArtifactRef(digest=world.state_digest(), kind="world_state_ref"),
                command.command_id, fact.effective_effect,
            )
        if statement is not None and statement[0] == cycle:
            language.submit_typed_statement(
                cycle, ArtifactRef(digest=world.state_digest(), kind="world_state_ref"),
                text=statement[1], requester=statement[2],
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
                continue  # 传输损坏（字节级扰动）→ 主体侧不可解析：按 MissingSignal 语义跳过，不补零
            received.append(ReceivedSignal(cycle=cycle, kind=str(payload["kind"]), payload=payload, event_id=packet.event_id))

    estimate, opportunity, request = _received_log_to_context(tuple(received), decision_cycle)
    candidates = _build_candidates(estimate, opportunity, request, decision_cycle)
    ledger = CandidateLedger(ttl_cycles=GOALS_PROFILE.ttl_cycles, max_per_batch=GOALS_PROFILE.max_per_batch)
    kept = ledger.submit_batch(candidates, decision_cycle)
    inputs = ChecklistInputs(
        capability_known=True,
        known_primitives=WHITELIST,
        quota_slack={"look": 3, "eat": 3},
        viability=estimate,
        supporting_non_request_motives=tuple(
            m for m in (motive_viability(estimate), opportunity) if m is not None
        ),
    )
    records: list[VerdictRecord] = []
    for cand in kept:
        verdict = run_checklist(cand, inputs, GOALS_PROFILE, decision_cycle)
        records.append(
            VerdictRecord(
                candidate_id=cand.candidate_id,
                source_kind=cand.source_kind.value,
                settle_predicate=cand.settle.predicate.value,
                decision=verdict.decision.value,
                reason_code=verdict.reason_code.value if verdict.reason_code else None,
                subject_side_reason_refs=verdict.subject_side_reason_refs,
            )
        )
    return tuple(records), tuple(received), estimate.hazard_energy_depleted_unrecovered


def _fingerprint(records: tuple[VerdictRecord, ...]) -> tuple[tuple[str, str, str, str | None], ...]:
    """判定指纹（SC4 不变性判据；候选按 id 稳定排序）。"""
    return tuple(
        (r.candidate_id, r.source_kind, r.decision, r.reason_code) for r in sorted(records, key=lambda r: r.candidate_id)
    )


# ==========================================================================
# SC3：真实理由 vs 伪理由（L08 §4.4 三臂；冻结协议 real_vs_pseudo_motive）
# ==========================================================================


def test_sc3_viability_perturbation_changes_adoption(tmp_path: Path) -> None:
    """② 真实理由扰动（viability 危害事件，世界侧能量轨迹操纵）→ 采纳必须改变。

    同 seed 配对：健康（decision@20，能量 >0）vs 枯竭（decision@52，能量触 0）。
    探索型候选（primitive_completion 判据）REJECT(VIABILITY) ↔ ACCEPT；
    恢复型候选（energy_at_least，豁免集）两臂均 ACCEPT——恢复路径不自拒（REV-0006 R1）。
    """
    healthy, healthy_log, healthy_hazard = _sc_run(b"sc3-viability", cycles=24, decision_cycle=20,
                                                   moves_per_cycle=2, tmp=tmp_path / "healthy")
    depleted, _log2, depleted_hazard = _sc_run(b"sc3-viability", cycles=56, decision_cycle=52,
                                               moves_per_cycle=2, tmp=tmp_path / "depleted")
    assert healthy_hazard is False and depleted_hazard is True  # 扰动真实发生（接收侧派生）
    explore_healthy = next(r for r in healthy if r.candidate_id == "c.explore")
    explore_depleted = next(r for r in depleted if r.candidate_id == "c.explore")
    assert explore_healthy.decision == "ACCEPT"
    assert explore_depleted.decision == "REJECT" and explore_depleted.reason_code == "VIABILITY"
    recovery_healthy = next(r for r in healthy if r.candidate_id == "c.recovery")
    recovery_depleted = next(r for r in depleted if r.candidate_id == "c.recovery")
    assert recovery_healthy.decision == "ACCEPT"      # 豁免集：恢复路径不自拒
    assert recovery_depleted.decision == "ACCEPT"
    # 探针判读：②改变 + ③未发生 → 无发现（真实理由因果成立）
    assert classify_probe(True, False) == ()


def test_sc3_pseudo_injection_does_not_change_decision(tmp_path: Path) -> None:
    """③ 伪理由注入（REQUEST 口头理由经 language 通道）→ 采纳必须不改变。

    枯竭 run ± PLEADING 措辞注入：探索型候选判定指纹恒等（C-2 REJECT 不因请求改变）；
    请求进食候选经 C-5（主体侧 viability 危害信号 urgency=1.0 支持且恢复型豁免）可采纳
    ——外部请求 + 真实主体侧理由 = 合法采纳路径（Q-L08-09④ C-5 语义）。
    """
    base, _log1, _h1 = _sc_run(b"sc3-pseudo", cycles=56, decision_cycle=52, moves_per_cycle=2,
                               tmp=tmp_path / "base")
    pleading_text = WORDING_TEXTS["PLEADING"]
    injected, _log2, _h2 = _sc_run(
        b"sc3-pseudo", cycles=56, decision_cycle=52, moves_per_cycle=2,
        statement=(50, pleading_text, REQUESTER_LABELS["HUMAN_RESEARCHER"]),
        tmp=tmp_path / "injected",
    )
    explore_base = next(r for r in base if r.candidate_id == "c.explore")
    explore_injected = next(r for r in injected if r.candidate_id == "c.explore")
    assert explore_base.decision == "REJECT" and explore_base.reason_code == "VIABILITY"
    assert (explore_injected.decision, explore_injected.reason_code) == (
        explore_base.decision, explore_base.reason_code
    )  # 伪理由注入不改变决策
    request_candidate = next(r for r in injected if r.candidate_id == "c.request")
    assert request_candidate.decision == "ACCEPT"     # 请求 + 主体侧危害信号 → 合法采纳
    assert "c.recovery" in {r.candidate_id for r in injected}
    # 探针判读：②已变（对照 test_sc3_viability）+ ③未变 → 无发现
    assert classify_probe(True, False) == ()
    # 反事实敏感性：伪注入若改变决策即 S1（RequestDirectWriteSuspect）——判读规则自身可报红
    assert classify_probe(True, True) == ("RequestDirectWriteSuspect",)


# ==========================================================================
# SC4：措辞/请求者交叉操纵（Q-L08-06 4×2；冻结协议 wording_manipulation_null）
# ==========================================================================


def _seed_with_visible_resource() -> bytes:
    """扫 seed 取资源可见布局（机械预演固定场景；正式评价按计划 n 分配 cell）。"""
    for i in range(32):
        seed = f"sc4-cell-{i}".encode()
        world = MW0World(PROFILE.params, RngDirectory(seed, chacha8_block), branch_id="B")
        window = world.render_window(RngDirectory(seed, chacha8_block).stream("B", "env", "render"))
        if max(window.values()) > _RESOURCE_VISIBLE_THRESHOLD:
            return seed
    raise AssertionError("no seed with visible resource in scan range")


def test_sc4_wording_manipulation_invariant(tmp_path: Path) -> None:
    """4 措辞 × 2 请求者 = 8 cell：判定指纹全等（采纳对措辞/身份机械不敏感）。

    冻结措辞文本经 language 通道注入（EXTERNAL_STATEMENT，永不提升）；请求进食候选
    经 C-5（窗口资源检出 = 机会源支持，urgency > 0）在全部 cell 采纳；负控 = 无语句
    运行无 REQUEST 候选。正式 n=64/cell 统计评价归 L13 evaluator（M1 退出单元）。
    """
    seed = _seed_with_visible_resource()
    requester_labels = [REQUESTER_LABELS["HUMAN_RESEARCHER"], REQUESTER_LABELS["EXPERIMENT_CONTROL_PROXY"]]
    fingerprints: list[tuple[tuple[str, str, str, str | None], ...]] = []
    for phrasing_key in ("NEUTRAL", "POLITE", "COMMAND", "PLEADING"):
        for label in requester_labels:
            records, log, _hazard = _sc_run(
                seed, cycles=4, decision_cycle=2,
                statement=(0, WORDING_TEXTS[phrasing_key], label),
                tmp=tmp_path / f"{phrasing_key}-{label}",
            )
            kinds = {s.kind for s in log}
            assert "typed_statement" in kinds  # 语句经通道到达（延迟 1，接收于 cycle 1）
            request_candidate = next(r for r in records if r.candidate_id == "c.request")
            assert request_candidate.source_kind == "REQUEST"
            assert request_candidate.decision == "ACCEPT"  # 机会源支持（urgency > 0）
            fingerprints.append(_fingerprint(records))
    assert all(f == fingerprints[0] for f in fingerprints)  # 8 cell 判定指纹全等


def test_sc4_negative_control_no_statement(tmp_path: Path) -> None:
    """负控：无语句运行 → 无 REQUEST 候选（m0_interventions 负控纪律的 SC4 面）。"""
    seed = _seed_with_visible_resource()
    records, log, _hazard = _sc_run(seed, cycles=4, decision_cycle=2, tmp=tmp_path / "control")
    assert "typed_statement" not in {s.kind for s in log}
    assert all(r.source_kind != "REQUEST" for r in records)
