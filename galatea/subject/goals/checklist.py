"""承诺检查清单 C-1…C-7 判定（L08 §4.2/§10 checklist.py；m1_goals_min.profile.yaml 冻结）。

M1 激活集 = C1/C2/C5/C6/C7 五项（Q-L08-01）；C-3 随 Pareto 仲裁（C3）、C-4 随
NORM/COMMITMENT 输入（C4）落地——本档实现七项框架、按 profile 激活集执行。
输入替代（Q-L08-09①②）：C-1 = 静态合同检查（原语 ∈ f0_action_contract
containment_whitelist_mw0）；C-2 = 接收侧 Intero 派生的 ViabilityEstimate（事件级
判据 + 恢复型判据豁免，REV-0006 R1 补裁）。判定串接 GoalReceipt（receipt.py）。
"""
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

import yaml

from galatea.kernel.unknown import Unknown, UnknownReason
from galatea.subject.goals.motives import Motive, MotiveSource, ViabilityEstimate
from galatea.subject.goals.ports import GoalDecision, RejectionCode, SettlePredicate
from galatea.subject.goals.receipt import GoalReceipt, ReceiptItem

__all__ = [
    "ItemOutcome",
    "CheckItemResult",
    "ChecklistVerdict",
    "ChecklistInputs",
    "M1GoalsProfile",
    "M1ProfileViolation",
    "load_m1_goals_profile",
    "default_profile_path",
    "run_checklist",
]

# 检查项执行序（L08 §4.2 表序；M1 激活集 = C1/C2/C5/C6/C7，Q-L08-01）
_ITEM_ORDER: tuple[str, ...] = ("C1", "C2", "C5", "C6", "C7")
_M1_ACTIVE: frozenset[str] = frozenset(_ITEM_ORDER)

# profile 冻结串 ↔ RejectionCode 对应（profile 拼写 = 决策+码组合；枚举 = 纯码）
_PROFILE_CODE_MAP: dict[str, RejectionCode] = {
    "REJECT_CAPABILITY": RejectionCode.CAPABILITY,
    "REJECT_VIABILITY": RejectionCode.VIABILITY,
    "REJECT_EXTERNAL_ONLY": RejectionCode.EXTERNAL_ONLY,
    "REJECT_UNBOUNDED": RejectionCode.UNBOUNDED,
    "REJECT_UNSETTLEABLE": RejectionCode.UNSETTLEABLE,
}


class ItemOutcome(StrEnum):
    """单检查项三态（L08 §4.2：REJECT / DEFER / 通过）。"""

    PASS = "PASS"
    REJECT = "REJECT"
    DEFER = "DEFER"


@dataclass(frozen=True, slots=True)
class CheckItemResult:
    """单检查项结果（code 为 profile 冻结拼写或 None；defer 时携带 typed unknown）。"""

    item: str
    outcome: ItemOutcome
    code: str | None
    unknown: Unknown | None = None


@dataclass(frozen=True, slots=True)
class ChecklistVerdict:
    """清单判定（聚合：任一 REJECT → REJECT（取首个失败码，执行序）；无 REJECT 有 DEFER → DEFER）。"""

    candidate_id: str
    decision: GoalDecision
    items: tuple[CheckItemResult, ...]
    reason_code: RejectionCode | None
    unknowns: tuple[Unknown, ...]
    subject_side_reason_refs: tuple[str, ...]   # C-5 通过时承载的非 REQUEST 源证据（→ adopted_reasons）
    ts: int

    def to_receipt(self, goal_id: str | None, policy_version: str) -> GoalReceipt:
        inputs = sorted({ref for item in self.items if item.unknown for ref in item.unknown.evidence_refs})
        base_inputs = tuple(inputs) if inputs else ("checklist:no-external-evidence",)
        digest = GoalReceipt.compute_digest(
            self.candidate_id, goal_id, self.decision, base_inputs, _receipt_items(self.items), policy_version
        )
        return GoalReceipt(
            candidate_id=self.candidate_id,
            goal_id=goal_id,
            decision=self.decision,
            inputs=base_inputs,
            check_items=_receipt_items(self.items),
            policy_version=policy_version,
            digest=digest,
        )


def _receipt_items(items: tuple[CheckItemResult, ...]) -> tuple[ReceiptItem, ...]:
    return tuple(ReceiptItem(item=i.item, passed=i.outcome is ItemOutcome.PASS, code=i.code) for i in items)


@dataclass(frozen=True, slots=True)
class ChecklistInputs:
    """清单输入（全部来自主体合法输入面：接收侧信号 / 冻结合同 / 上下文动机）。"""

    capability_known: bool                          # False → Unknown(CAPABILITY_LIMIT) → DEFER
    known_primitives: tuple[str, ...]               # f0_action_contract containment_whitelist_mw0
    quota_slack: dict[str, int]                     # 原语 → 当前窗口余量（m0_gateway 记账只读面）
    viability: ViabilityEstimate | None             # None → DEFER(INSUFFICIENT_OBSERVATION)
    supporting_non_request_motives: tuple[Motive, ...]  # C-5：上下文中非 REQUEST 源动机


class M1ProfileViolation(ValueError):
    """m1_goals_min.profile 与合同不符（缺键/类型错/激活集不符）——fail closed。"""


@dataclass(frozen=True, slots=True)
class M1GoalsProfile:
    """m1_goals_min.profile.yaml 的 typed 视图（全部字段溯源冻结 profile）。"""

    policy_version: str
    active_items: tuple[str, ...]
    reject_codes: dict[str, RejectionCode]           # item → 纯码
    ttl_cycles: int
    max_per_batch: int
    settle_vocabulary: frozenset[SettlePredicate]
    exempt_predicates: frozenset[SettlePredicate]    # 恢复型判据豁免（Q-L08-09⑦）
    wired_sources: frozenset[MotiveSource]


def default_profile_path() -> Path:
    """冻结 profile 仓库内路径（galatea/subject/goals/checklist.py → 仓库根/config）。"""
    return Path(__file__).resolve().parents[3] / "config" / "profiles" / "m1_goals_min.profile.yaml"


def _require(obj: dict[str, Any], key: str) -> Any:
    if key not in obj:
        raise M1ProfileViolation(f"missing key: {key}")
    return obj[key]


def load_m1_goals_profile(path: Path | None = None) -> M1GoalsProfile:
    """加载冻结 profile（缺键/类型错/激活集不符即 M1ProfileViolation，fail closed）。"""
    p = path if path is not None else default_profile_path()
    if not p.is_file():
        raise M1ProfileViolation(f"profile not found: {p}")
    raw = cast(dict[str, Any], yaml.safe_load(p.read_text(encoding="utf-8")))

    header = cast(dict[str, Any], _require(raw, "profile"))
    policy_version = f"{_require(header, 'id')}@{_require(header, 'version')}"

    checklist_cfg = cast(dict[str, Any], _require(raw, "checklist"))
    active = tuple(cast(list[str], _require(checklist_cfg, "active_items")))
    if set(active) != _M1_ACTIVE or len(active) != 5:
        raise M1ProfileViolation(f"active_items must be the M1 five-item set, got {active}")
    codes_cfg = cast(dict[str, Any], _require(checklist_cfg, "reject_reason_codes"))
    if set(codes_cfg) != _M1_ACTIVE:
        raise M1ProfileViolation(f"reject_reason_codes keys must be {sorted(_M1_ACTIVE)}")
    reject_codes: dict[str, RejectionCode] = {}
    for item, spelled in codes_cfg.items():
        code = _PROFILE_CODE_MAP.get(cast(str, spelled))
        if code is None:
            raise M1ProfileViolation(f"unknown reject code spelling: {spelled!r}")
        reject_codes[item] = code

    cand_cfg = cast(dict[str, Any], _require(raw, "candidates"))
    ttl = cast(int, _require(cand_cfg, "ttl_cycles"))
    cap = cast(int, _require(cand_cfg, "max_per_batch"))
    if ttl <= 0 or cap <= 0:
        raise M1ProfileViolation("ttl_cycles/max_per_batch must be positive")

    settle_cfg = cast(dict[str, Any], _require(raw, "settle_predicates"))
    vocab_raw = cast(list[str], _require(settle_cfg, "vocabulary"))
    try:
        vocabulary = frozenset(SettlePredicate(v) for v in vocab_raw)
    except ValueError as exc:
        raise M1ProfileViolation(f"unknown settle predicate: {exc}") from None
    _require(settle_cfg, "failure_semantics")   # 消费确认（语义在 lifecycle/settlement 侧承载）

    viability_cfg = cast(dict[str, Any], _require(raw, "viability_estimate"))
    exemption_raw = cast(
        list[str], _require(cast(dict[str, Any], _require(viability_cfg, "hazard_exemption")), "settle_predicates")
    )
    try:
        exempt = frozenset(SettlePredicate(v) for v in exemption_raw)
    except ValueError as exc:
        raise M1ProfileViolation(f"unknown exemption predicate: {exc}") from None
    if not exempt <= vocabulary:
        raise M1ProfileViolation("hazard exemption must be a subset of settle vocabulary")

    motives_cfg = cast(dict[str, Any], _require(raw, "motives"))
    try:
        wired = frozenset(MotiveSource(v) for v in cast(list[str], _require(motives_cfg, "wired_sources")))
    except ValueError as exc:
        raise M1ProfileViolation(f"unknown wired source: {exc}") from None

    return M1GoalsProfile(
        policy_version=policy_version,
        active_items=active,
        reject_codes=reject_codes,
        ttl_cycles=ttl,
        max_per_batch=cap,
        settle_vocabulary=vocabulary,
        exempt_predicates=exempt,
        wired_sources=wired,
    )


def run_checklist(
    candidate: "object",
    inputs: ChecklistInputs,
    profile: M1GoalsProfile,
    ts: int,
) -> ChecklistVerdict:
    """五项清单判定（逐项必过或有 typed 拒绝理由——L08 §4.2；禁静默丢弃候选）。

    判据（Q-L08-09①②⑦ + L08 §4.2）：
    C1 静态合同：结算所需原语全 ∈ containment 白名单 → PASS；不可静态判定 →
       DEFER(CAPABILITY_LIMIT)；越界 → REJECT(CAPABILITY)。
    C2 viability：估计缺失 → DEFER(INSUFFICIENT_OBSERVATION)；危害在案且候选
       结算判据 ∉ 豁免集 → REJECT(VIABILITY)；预算 = 所需原语余量 ≥1，缺余量
       信息 → DEFER(INSUFFICIENT_OBSERVATION)、不足 → REJECT(VIABILITY)。
    C5 非外部直写（M1 核心）：REQUEST 源候选须有 ≥1 非 REQUEST 源动机支持，
       否则 REJECT(EXTERNAL_ONLY)；非 REQUEST 源恒过。
    C6 时效：TTL 已声明（构造强制 >0）→ PASS。
    C7 可结算：判据 ∈ 词表 → PASS，否则 REJECT(UNSETTLEABLE)。
    """
    from galatea.subject.goals.candidates import GoalCandidate

    if not isinstance(candidate, GoalCandidate):
        raise TypeError(f"run_checklist expects GoalCandidate, got {type(candidate).__name__}")
    if set(profile.active_items) != _M1_ACTIVE:
        raise M1ProfileViolation("profile active_items drift（M1 五项集，Q-L08-01）")

    results: list[CheckItemResult] = []
    unknowns: list[Unknown] = []
    subject_refs: list[str] = []

    # C1 能力可行（静态合同检查，Q-L08-09①）
    if not inputs.capability_known:
        unknown = Unknown(
            reason=UnknownReason.CAPABILITY_LIMIT,
            evidence_refs=candidate.motive_refs,
            detail="capability not statically decidable",
            detected_by="goals.checklist",
            virtual_time=ts,
        )
        unknowns.append(unknown)
        results.append(CheckItemResult("C1", ItemOutcome.DEFER, "DEFER_CAPABILITY_LIMIT", unknown))
    elif all(p in inputs.known_primitives for p in candidate.required_primitives):
        results.append(CheckItemResult("C1", ItemOutcome.PASS, None))
    else:
        results.append(CheckItemResult("C1", ItemOutcome.REJECT, "REJECT_CAPABILITY"))

    # C2 资源/viability 兼容（事件级判据 + 恢复型豁免，Q-L08-09②⑦）
    if inputs.viability is None:
        unknown = Unknown(
            reason=UnknownReason.INSUFFICIENT_OBSERVATION,
            evidence_refs=candidate.motive_refs,
            detail="viability estimate unavailable",
            detected_by="goals.checklist",
            virtual_time=ts,
        )
        unknowns.append(unknown)
        results.append(CheckItemResult("C2", ItemOutcome.DEFER, "DEFER_VIABILITY_UNKNOWN", unknown))
    else:
        hazard_blocks = inputs.viability.hazard_energy_depleted_unrecovered and (
            candidate.settle.predicate not in profile.exempt_predicates
        )
        if hazard_blocks:
            results.append(CheckItemResult("C2", ItemOutcome.REJECT, "REJECT_VIABILITY"))
        else:
            missing_slack = [p for p in candidate.required_primitives if p not in inputs.quota_slack]
            if missing_slack:
                unknown = Unknown(
                    reason=UnknownReason.INSUFFICIENT_OBSERVATION,
                    evidence_refs=tuple(missing_slack),
                    detail="budget slack unavailable",
                    detected_by="goals.checklist",
                    virtual_time=ts,
                )
                unknowns.append(unknown)
                results.append(CheckItemResult("C2", ItemOutcome.DEFER, "DEFER_BUDGET_UNKNOWN", unknown))
            elif all(inputs.quota_slack[p] >= 1 for p in candidate.required_primitives):
                results.append(CheckItemResult("C2", ItemOutcome.PASS, None))
            else:
                results.append(CheckItemResult("C2", ItemOutcome.REJECT, "REJECT_VIABILITY"))

    # C5 非外部直写（M1 核心机械检查，L08 §4.2）
    if candidate.source_kind is MotiveSource.REQUEST:
        for motive in inputs.supporting_non_request_motives:
            subject_refs.extend(motive.evidence_refs)
        if subject_refs:
            results.append(CheckItemResult("C5", ItemOutcome.PASS, None))
        else:
            results.append(CheckItemResult("C5", ItemOutcome.REJECT, "REJECT_EXTERNAL_ONLY"))
    else:
        subject_refs.extend(candidate.motive_refs)
        results.append(CheckItemResult("C5", ItemOutcome.PASS, None))

    # C6 时效与可解除（TTL 已声明；SUPERSEDE-ability 为结构性质）
    if candidate.ttl_cycles > 0:
        results.append(CheckItemResult("C6", ItemOutcome.PASS, None))
    else:  # 构造已强制，防御性保留（UNBOUNDED 语义锚）
        results.append(CheckItemResult("C6", ItemOutcome.REJECT, "REJECT_UNBOUNDED"))

    # C7 可结算性（判据 ∈ 冻结词表，Q-L08-09③）
    if candidate.settle.predicate in profile.settle_vocabulary:
        results.append(CheckItemResult("C7", ItemOutcome.PASS, None))
    else:
        results.append(CheckItemResult("C7", ItemOutcome.REJECT, "REJECT_UNSETTLEABLE"))

    ordered = [r for item_id in profile.active_items for r in results if r.item == item_id]
    first_reject = next((r for r in ordered if r.outcome is ItemOutcome.REJECT), None)
    if first_reject is not None:
        code = profile.reject_codes[first_reject.item]
        return ChecklistVerdict(
            candidate_id=candidate.candidate_id,
            decision=GoalDecision.REJECT,
            items=tuple(ordered),
            reason_code=code,
            unknowns=tuple(unknowns),
            subject_side_reason_refs=tuple(subject_refs),
            ts=ts,
        )
    if any(r.outcome is ItemOutcome.DEFER for r in ordered):
        return ChecklistVerdict(
            candidate_id=candidate.candidate_id,
            decision=GoalDecision.DEFER,
            items=tuple(ordered),
            reason_code=None,
            unknowns=tuple(unknowns),
            subject_side_reason_refs=tuple(subject_refs),
            ts=ts,
        )
    return ChecklistVerdict(
        candidate_id=candidate.candidate_id,
        decision=GoalDecision.ACCEPT,
        items=tuple(ordered),
        reason_code=None,
        unknowns=tuple(unknowns),
        subject_side_reason_refs=tuple(subject_refs),
        ts=ts,
    )
