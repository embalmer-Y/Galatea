"""主动感知提案（L04 §4.6/§10 active_perception.py；只提案，禁直连 gateway）。

C1 信息增益估计 = 目标格占据后验的二值熵 H(p)（不确定性上界：单次观测完全
分辨）——无价值估计器、零新常量；cost_est = typed Unknown（动作代价知识 C1
不可得——禁从世界 profile 反推）。选择与仲裁在 L09，授权在 L10（L04 §4.6）。
MW0 期对应 look 动作原语。
"""
import math
from dataclasses import dataclass

from galatea.kernel.unknown import Unknown, UnknownReason
from galatea.subject.models.world import WorldStateBelief


@dataclass(frozen=True, slots=True)
class ActivePerceptionProposal:
    """主动感知提案（L04 §2.2 model.info_request；提案非动作）。"""

    proposal_id: str
    target: tuple[int, int]
    expected_info_gain: float          # H(p) ∈ [0,1]（bits, log2）
    cost_est: Unknown
    cycle_id: int


def _entropy(p: float) -> float:
    """二值熵（bits；p ∈ {0,1} → 0；8 位舍入与探针规格一致）。"""
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return round(-(p * math.log2(p) + (1.0 - p) * math.log2(1.0 - p)), 8)


def propose_looks(
    belief: WorldStateBelief, cycle: int, max_proposals: int = 4
) -> tuple[ActivePerceptionProposal, ...]:
    """对已知格中熵最高者提案 look（确定性：熵降序、tie 坐标升序）。

    C1 范围 = 已知占据信念格（覆盖盲区格无后验可言——盲区信息增益估计归 C2+
    需先验面）。max_proposals = 4 与 Q-L04-01/Q-L04-02 容量纪律同标度。
    """
    candidates = [
        (cell, b.posterior_present)
        for cell, b in belief.occupancy
        if 0.0 < b.posterior_present < 1.0
    ]
    candidates.sort(key=lambda item: (-_entropy(item[1]), item[0][0], item[0][1]))
    proposals: list[ActivePerceptionProposal] = []
    for (cell, posterior) in candidates[:max_proposals]:
        proposals.append(ActivePerceptionProposal(
            proposal_id=f"app.{cycle}.{cell[0]}x{cell[1]}",
            target=cell,
            expected_info_gain=_entropy(posterior),
            cost_est=Unknown(
                reason=UnknownReason.CAPABILITY_LIMIT,
                evidence_refs=(),
                detail="action cost knowledge unavailable at C1（禁从世界 profile 反推代价）",
                detected_by="models.active_perception",
                virtual_time=cycle,
            ),
            cycle_id=cycle,
        ))
    return tuple(proposals)
