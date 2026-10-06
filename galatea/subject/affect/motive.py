"""AffectiveMotive 提案构造（L05 §2.2/§10 motive.py，C2 实现期）。

类型隔离（L05 §7 contract："AffectiveMotive 不是 OwnedGoal（类型分离）"）：
本模块产 **提案**（affect 侧类型，不 import 下游 L08——上游禁反向依赖）；
L08 在 C3 接线时由提案构造其 Motive 源之一（**不得**独占，L05 §9 C3 行）。
情感不直达执行：提案只携带 urgency 与证据引用，无命令面。
"""
from dataclasses import dataclass

from galatea.subject.affect.state import FunctionalExperientialState

__all__ = ["AffectiveMotiveProposal", "build_motive_proposal"]


@dataclass(frozen=True, slots=True)
class AffectiveMotiveProposal:
    """情感动机提案（类型上与 OwnedGoal 隔离——无 goal 字段、无承诺语义、无执行面）。"""

    proposal_id: str
    urgency: float                    # = 感受态 urgency（同一值，不新造标量）
    evidence_refs: tuple[str, ...]
    state_digest: str                 # 发布时感受态 digest（可审计绑定）
    issued_at: int

    def __post_init__(self) -> None:
        if not 0.0 <= self.urgency <= 1.0:
            raise ValueError(f"urgency out of [0,1]: {self.urgency!r}")
        if not self.evidence_refs:
            raise ValueError("evidence_refs required（L05 §2.2 aff.motive 合同）")


def build_motive_proposal(
    state: FunctionalExperientialState, evidence_refs: tuple[str, ...]
) -> AffectiveMotiveProposal:
    """确定性构造（urgency = state.urgency；id = state_id 派生）。"""
    return AffectiveMotiveProposal(
        proposal_id=f"affective_motive.{state.t_eff}",
        urgency=state.urgency,
        evidence_refs=evidence_refs,
        state_digest=state.content_digest,
        issued_at=state.t_eff,
    )
