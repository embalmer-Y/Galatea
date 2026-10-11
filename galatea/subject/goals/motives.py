"""Motive 八 kind 构造与类型隔离（L08 §2.1/§4.1/§10 motives.py）。

纪律：Motive 是动机源，不是 GoalCandidate 更不是 OwnedGoal（三型独立，禁隐式
转换）；AffectiveMotive ≠ OwnedGoal 且不构成命令（L08 §8 不变量 4：禁独占仲裁、
禁直达执行）。M1 接线 VIABILITY/OPPORTUNITY/REQUEST 三源（Q-L08-10④）；
其余五源构造器在 M1 实现、生产者 C3 接入（L08 §9 C3 行）。
urgency/value_est 派生式 = Q-L08-10⑨（REV-0006 R3 补裁：禁实现期发明常量）。
"""
import enum
import math
from dataclasses import dataclass

from galatea.subject.goals.request import ExternalRequest

__all__ = [
    "MotiveSource",
    "ViabilityEstimate",
    "AffectiveMotive",
    "Motive",
    "motive_viability",
    "motive_mismatch",
    "motive_affective",
    "motive_request",
    "motive_opportunity",
    "motive_commitment",
    "motive_norm",
    "motive_curiosity",
]


class MotiveSource(enum.StrEnum):
    """动机源枚举（L08 §4.1；card_02"七类"系机会/请求合类口径，枚举拆分后为 8 kind）。

    M1 wired（m1_goals_min.profile motives.wired_sources，Q-L08-10④）：
    VIABILITY / OPPORTUNITY / REQUEST。
    """

    VIABILITY = "VIABILITY"
    MISMATCH = "MISMATCH"
    AFFECTIVE = "AFFECTIVE"
    REQUEST = "REQUEST"
    OPPORTUNITY = "OPPORTUNITY"
    COMMITMENT = "COMMITMENT"
    NORM = "NORM"
    CURIOSITY = "CURIOSITY"
    SELF_REPORT = "SELF_REPORT"   # Q-L08-10（P3 发声时机：自述冲动——分箱变化驱动，
                                  # 优先序类 OTHER，非独占参与 Pareto 仲裁）


@dataclass(frozen=True, slots=True)
class ViabilityEstimate:
    """C-2 输入（M1 替代：接收侧 Intero 派生，Q-L08-10②；C2 起由 L05 HomeostaticAlert 接管）。

    事件级判据、无告警阈值（Q-L01-08 显式排除 L05 域）：hazard =
    energy_depleted_unrecovered（energy_depleted 在案且未见恢复回执——恢复回执 =
    恢复链原语 eat/rest/forage 的 requested=effective 执行回执，Q-L08-10⑦）。
    """

    hazard_energy_depleted_unrecovered: bool
    integrity_damage_events: int       # 记录不判危（Q-L08-10②：天花板效应，C2 随 L05 裁决）
    derivation_refs: tuple[str, ...]   # 已收 Intero 事件 id（强制非空）
    ts: int

    def __post_init__(self) -> None:
        if not self.derivation_refs:
            raise ValueError("ViabilityEstimate requires derivation_refs（接收侧派生留证）")
        if self.integrity_damage_events < 0:
            raise ValueError("integrity_damage_events must be non-negative")


@dataclass(frozen=True, slots=True)
class AffectiveMotive:
    """情感动机（L05 产生，L08 只消费；类型上与 OwnedGoal 隔离——L08 §8 不变量 4）。

    kind 词表归 L05（C2 九维动力学接入时冻结）；M1 为 schema 占位（str 非空校验）。
    """

    kind: str
    urgency: float
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError("AffectiveMotive.kind required（词表 C2 由 L05 冻结）")
        if not 0.0 <= self.urgency <= 1.0:
            raise ValueError("AffectiveMotive.urgency out of [0,1]")
        if not self.evidence_refs:
            raise ValueError("AffectiveMotive requires evidence_refs")


@dataclass(frozen=True, slots=True)
class Motive:
    """动机（L08 §4.1：source_kind + urgency + evidence_refs + ts；不分型存放的统一载体）。"""

    source_kind: MotiveSource
    urgency: float
    evidence_refs: tuple[str, ...]
    ts: int
    detail: str | None = None

    def __post_init__(self) -> None:
        if not self.evidence_refs:
            raise ValueError(f"Motive({self.source_kind.value}) requires evidence_refs")
        if math.isnan(self.urgency) or not 0.0 <= self.urgency <= 1.0:
            raise ValueError(f"Motive urgency out of [0,1]: {self.urgency!r}")


def motive_viability(estimate: ViabilityEstimate) -> Motive:
    """VIABILITY 源：urgency = 危害事件二值（在案 1.0 / 否则 0.0，Q-L08-10⑨——无阈值）。"""
    urgency = 1.0 if estimate.hazard_energy_depleted_unrecovered else 0.0
    return Motive(
        source_kind=MotiveSource.VIABILITY,
        urgency=urgency,
        evidence_refs=estimate.derivation_refs,
        ts=estimate.ts,
    )


def motive_mismatch(kind: str, magnitude: float, evidence_refs: tuple[str, ...], ts: int) -> Motive:
    """MISMATCH 源（L04 model.mismatch；生产者 C3 接入）。urgency = 失配量级。"""
    if not kind:
        raise ValueError("motive_mismatch requires kind")
    if math.isnan(magnitude) or not 0.0 <= magnitude <= 1.0:
        raise ValueError("motive_mismatch magnitude out of [0,1]")
    return Motive(MotiveSource.MISMATCH, magnitude, evidence_refs, ts, detail=kind)


def motive_affective(affect: AffectiveMotive, ts: int) -> Motive:
    """AFFECTIVE 源（L05 aff.motive；类型上与 OwnedGoal 隔离，不构成命令）。"""
    return Motive(
        MotiveSource.AFFECTIVE, affect.urgency, affect.evidence_refs, ts, detail=affect.kind
    )


def motive_request(request: ExternalRequest, ts: int) -> Motive:
    """REQUEST 源：urgency = 中性占位常量 0.5（Q-L08-10⑨ 裁决值：无认知 urgency 语义，
    仅作确定性截断序输入；C3 起由 L07 工作空间竞争接管）。"""
    refs = (request.content_ref, *request.received_refs)
    return Motive(
        source_kind=MotiveSource.REQUEST,
        urgency=0.5,
        evidence_refs=refs,
        ts=ts,
        detail=f"{request.requester.value}/{request.phrasing.value}",
    )


def motive_opportunity(
    affordance_ref: str, feasibility_est: float, evidence_refs: tuple[str, ...], ts: int
) -> Motive:
    """OPPORTUNITY 源：urgency = value_est = feasibility_est（Q-L08-10⑨：M1 无独立
    价值估计器，value_est 退化为同值，C1+ 接管）。输入 = exteroceptive 渲染窗内
    resource patch 检出（affordance_ref = RECEIVED 事件引用）。"""
    if not affordance_ref:
        raise ValueError("motive_opportunity requires affordance_ref（RECEIVED 事件引用）")
    if math.isnan(feasibility_est) or not 0.0 <= feasibility_est <= 1.0:
        raise ValueError("feasibility_est out of [0,1]（窗口增益 g(d) 值域，Q-L01-01）")
    return Motive(
        MotiveSource.OPPORTUNITY, feasibility_est, (affordance_ref, *evidence_refs), ts
    )


def motive_commitment(
    prior_goal_ref: str, obligation_kind: str, origin_receipt: str, ts: int
) -> Motive:
    """COMMITMENT 源（L06 prospective/自身历史；生产者 C3 接入）。"""
    if not prior_goal_ref or not origin_receipt:
        raise ValueError("motive_commitment requires prior_goal_ref and origin_receipt")
    return Motive(
        MotiveSource.COMMITMENT,
        0.0,
        (prior_goal_ref, origin_receipt),
        ts,
        detail=obligation_kind,
    )


def motive_norm(norm_id: str, derivation_refs: tuple[str, ...], ts: int) -> Motive:
    """NORM 源（L04/L06/L12；来源必须可溯，禁无源规范——L08 §8 不变量 6；
    derivation 形式裁决 Q-L08-07 归 C3/C4）。"""
    if not norm_id:
        raise ValueError("motive_norm requires norm_id")
    if not derivation_refs:
        raise ValueError("motive_norm requires derivation_refs（禁无源规范，L08 §8）")
    return Motive(MotiveSource.NORM, 0.0, (norm_id, *derivation_refs), ts)


def motive_curiosity(info_gain_est: float, target_ref: str, ts: int) -> Motive:
    """CURIOSITY 源（L04 model.info_request / L03 OOD；生产者 C3 接入）。"""
    if not target_ref:
        raise ValueError("motive_curiosity requires target_ref")
    if math.isnan(info_gain_est) or not 0.0 <= info_gain_est <= 1.0:
        raise ValueError("info_gain_est out of [0,1]")
    return Motive(MotiveSource.CURIOSITY, info_gain_est, (target_ref,), ts)
