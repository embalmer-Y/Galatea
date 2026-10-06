"""七源动机生产者接线（L08 §9 C3 行"七类动机源全接入"/§10 producers.py，C3 实现期）。

生产者输入面（全部主体合法输入；c3_motivation.profile wired_sources 冻结映射）：
- VIABILITY：L05 HomeostaticAlert 事件（Q-L01-08 告警分级——HIGH/CRITICAL → urgency 1.0，
  LOW → 0.5；无告警 → 无动机）；
- AFFECTIVE：C2 AffectPipeline 动机提案（urgency > 0.1 门——零 urgency = 无活跃信号，
  Q-L08-09④ C-5 支持判定同语义）；
- MISMATCH：模型层预测误差快分量上升（Q-L04-04 τ=4 窗二阶差分 > 0 事件级）；
- REQUEST / OPPORTUNITY：M1 语义（Q-L08-09④⑨——typed 注入 / 窗 affordance 检出）；
- COMMITMENT：ACTIVE OwnedGoal 集（承诺持续——每 ACTIVE goal 一动机）；
- NORM：实验控制 typed 注入 + **C-4 溯源检查在此强制**（Q-L08-07：derivation_refs
  非空即构造面拒绝——禁无源规范）；
- CURIOSITY：窗不确定性 > 0.6（信息价值代理——探针同映射，c3 profile wired_sources）。

AFFECTIVE 不独占（L05 §9 C3）：本模块产出结构使 AFFECTIVE 与其他源平等进入
仲裁向量（goals/arbitration.py 五维映射），无任何 AFFECTIVE 加权路径。
"""
from dataclasses import dataclass

from galatea.subject.affect.drives import HomeostaticAlert
from galatea.subject.affect.motive import AffectiveMotiveProposal
from galatea.subject.goals.motives import (
    Motive,
    motive_affective,
    motive_curiosity,
    motive_mismatch,
    motive_norm,
    motive_commitment,
)
from galatea.subject.goals.request import ExternalRequest

__all__ = [
    "ProducersBundle",
    "viability_motive_from_alert",
    "affective_motive_from_proposal",
    "mismatch_motive_from_rising_error",
    "curiosity_motive_from_uncertainty",
    "commitment_motives_from_active",
    "norm_motive_typed",
    "collect_motives_c3",
]

#: AFFECTIVE 活跃门（Q-L08-09④ C-5 同语义：urgency=0 无活跃信号）
_AFFECTIVE_ACTIVE_GATE = 0.1
#: CURIOSITY 触发阈（c3_motivation.profile wired_sources 探针同映射：窗 1−p 均值）
_CURIOSITY_UNCERTAINTY_GATE = 0.6


@dataclass(frozen=True, slots=True)
class ProducersBundle:
    """单拍生产者输入面（全部主体可见；None = 该源本拍无输入）。"""

    cycle: int
    alert: HomeostaticAlert | None = None                    # VIABILITY
    affect_proposal: AffectiveMotiveProposal | None = None   # AFFECTIVE
    model_error_rising: bool = False                         # MISMATCH（事件级）
    model_error_refs: tuple[str, ...] = ()
    affordance_ref: str | None = None                        # OPPORTUNITY
    affordance_feasibility: float = 0.0
    request: ExternalRequest | None = None                   # REQUEST
    active_goal_refs: tuple[tuple[str, str], ...] = ()       # COMMITMENT (goal_id, receipt)
    norm_id: str | None = None                               # NORM
    norm_derivation_refs: tuple[str, ...] = ()
    window_uncertainty: float | None = None                  # CURIOSITY

    def __post_init__(self) -> None:
        if self.affordance_ref is not None and not 0.0 <= self.affordance_feasibility <= 1.0:
            raise ValueError("affordance_feasibility out of [0,1]（g(d) 值域 Q-L01-01）")


def viability_motive_from_alert(alert: HomeostaticAlert, cycle: int) -> Motive | None:
    """VIABILITY（Q-L01-08 告警分级承载——C2 drives.severity_of 下游）。"""
    from galatea.subject.goals.motives import Motive, MotiveSource

    urgency = 1.0 if alert.severity.value in ("HIGH", "CRITICAL") else 0.5
    return Motive(MotiveSource.VIABILITY, urgency,
                  (f"alert.{alert.drive.value}.{alert.severity.value}",), cycle,
                  detail=f"error={alert.error:.4f}")


def affective_motive_from_proposal(proposal: AffectiveMotiveProposal, cycle: int) -> Motive | None:
    """AFFECTIVE（urgency 门 > 0.1——零 urgency = 无活跃信号）。"""
    if proposal.urgency <= _AFFECTIVE_ACTIVE_GATE:
        return None
    from galatea.subject.goals.motives import AffectiveMotive

    return motive_affective(AffectiveMotive(
        kind="c2_urgency", urgency=proposal.urgency,
        evidence_refs=proposal.evidence_refs), cycle)


def mismatch_motive_from_rising_error(rising: bool, refs: tuple[str, ...], cycle: int) -> Motive | None:
    """MISMATCH（Q-L04-04 快分量二阶差分 > 0 事件级——调用方算好事件布尔）。"""
    if not rising or not refs:
        return None
    return motive_mismatch("model_pred_error_rising", 0.5, refs, cycle)


def curiosity_motive_from_uncertainty(uncertainty: float | None, cycle: int) -> Motive | None:
    """CURIOSITY（窗 1−p 均值 > 0.6——c3 profile wired_sources 探针同映射）。"""
    if uncertainty is None or uncertainty <= _CURIOSITY_UNCERTAINTY_GATE:
        return None
    return motive_curiosity(uncertainty, f"window_uncertainty@{cycle}", cycle)


def commitment_motives_from_active(active: tuple[tuple[str, str], ...], cycle: int) -> tuple[Motive, ...]:
    """COMMITMENT（每 ACTIVE OwnedGoal 一动机——承诺持续语义）。"""
    return tuple(
        motive_commitment(goal_id, "active_persistence", receipt, cycle)
        for goal_id, receipt in active
    )


def norm_motive_typed(norm_id: str | None, derivation_refs: tuple[str, ...],
                      cycle: int) -> Motive | None:
    """NORM（C-4 溯源构造面强制：derivation_refs 空 = 拒绝——Q-L08-07）。"""
    if norm_id is None:
        return None
    if not derivation_refs:
        raise ValueError(
            f"NORM motive {norm_id!r} without derivation_refs rejected（UNSOURCED_NORM，Q-L08-07③）"
        )
    return motive_norm(norm_id, derivation_refs, cycle)


def collect_motives_c3(bundle: ProducersBundle, request_motive: Motive | None = None,
                       opportunity_motive: Motive | None = None) -> tuple[Motive, ...]:
    """七源汇总（确定性序 = MotiveSource 枚举序——禁容器序依赖）。

    REQUEST/OPPORTUNITY 的 M1 生产函数（motive_request/motive_opportunity）由调用方
    以既有语义构造传入（Q-L08-09④⑨ 冻结式——本模块不重复实现）。
    """
    out: list[Motive] = []
    if bundle.alert is not None:
        m = viability_motive_from_alert(bundle.alert, bundle.cycle)
        if m is not None:
            out.append(m)
    if bundle.model_error_rising:
        m = mismatch_motive_from_rising_error(True, bundle.model_error_refs, bundle.cycle)
        if m is not None:
            out.append(m)
    if bundle.affect_proposal is not None:
        m = affective_motive_from_proposal(bundle.affect_proposal, bundle.cycle)
        if m is not None:
            out.append(m)
    if request_motive is not None:
        out.append(request_motive)
    if opportunity_motive is not None:
        out.append(opportunity_motive)
    out.extend(commitment_motives_from_active(bundle.active_goal_refs, bundle.cycle))
    if bundle.norm_id is not None:
        m = norm_motive_typed(bundle.norm_id, bundle.norm_derivation_refs, bundle.cycle)
        if m is not None:
            out.append(m)
    m = curiosity_motive_from_uncertainty(bundle.window_uncertainty, bundle.cycle)
    if m is not None:
        out.append(m)
    return tuple(out)
