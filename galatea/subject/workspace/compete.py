"""竞争打分、调制因子应用与容量淘汰（L07 §4.1/§10 compete.py）。

打分 = Σ w_c·component（w_c 等权 1:1:1:1:1，Q-L07-02①）；affect 分量可被 L05
有界调制因子缩放（[0.5,2.0]，Q-L07-02②——**只调分量权重禁指定内容**③）；
tie-break (score desc, sponsor_module, proposal_id) 跨平台确定性；
容量 K 淘汰必入 RejectionLog（禁静默丢弃）；去重（DUPLICATE）判定窗状态由
pipeline 持有（recurse.py），本函数只消费 duplicate_ids。
"""
from dataclasses import dataclass

from galatea.kernel.digest import content_digest
from galatea.subject.affect.modulation import ModulationField, ModulationReceiptRecord, ModulationTarget
from galatea.subject.c2profile import C2WorkspaceParams
from galatea.subject.workspace.ports import RejectionReason
from galatea.subject.workspace.propose import WorkspaceProposal

__all__ = [
    "ScoredProposal",
    "RejectedProposal",
    "WorkspaceFaceMismatch",
    "score_proposal",
    "consume_salience_modulation",
    "compete",
    "competition_digest",
]


class WorkspaceFaceMismatch(ValueError):
    """非本档调制投递（端口路由错配）。"""


@dataclass(frozen=True, slots=True)
class ScoredProposal:
    """打分结果（competition_trace 载体）。"""

    proposal_id: str
    score: float
    components_used: tuple[float, float, float, float, float]   # 打分时生效五分量
    rank: int | None
    admitted: bool
    reason: str = ""


@dataclass(frozen=True, slots=True)
class RejectedProposal:
    """淘汰留痕（L07 §2.2 RejectionLog）。"""

    proposal_id: str
    reason: RejectionReason
    score: float


def consume_salience_modulation(field: ModulationField, cycle: int) -> ModulationReceiptRecord:
    """WORKSPACE salience 调制消费面（三类调制第三类——L07 侧接收 + 回执）。

    因子界 [0.5,2.0]（Q-L07-02②）；越界 clip + CLIPPED；回执回传 affect 台账
    （无回执调制 = 未发生，L05 §4.4）。
    """
    if field.target is not ModulationTarget.WORKSPACE or field.dimension != "salience.affect":
        raise WorkspaceFaceMismatch(
            f"not a workspace salience modulation: {field.target.value}/{field.dimension}")
    lo, hi = (0.5, 2.0)
    applied = min(max(field.requested_value, lo), hi)
    return ModulationReceiptRecord(
        modulation_id=field.modulation_id, accepted=True, applied_value=applied,
        bound_check="IN_BOUND" if applied == field.requested_value else "CLIPPED",
        received_at=cycle,
    )


def score_proposal(
    p: WorkspaceProposal, params: C2WorkspaceParams, affect_factor: float,
) -> tuple[float, tuple[float, float, float, float, float]]:
    """打分（等权 + affect 分量调制缩放——调制只改分量不改内容）。"""
    s = p.salience
    affect_scaled = min(1.0, s.affect * affect_factor)   # 分量自身域 [0,1] 饱和
    comps = (s.goal_relevance, affect_scaled, s.novelty, s.uncertainty, s.info_value)
    score = sum(w * c for w, c in zip(params.weights, comps))
    return score, comps


def compete(
    proposals: tuple[WorkspaceProposal, ...],
    params: C2WorkspaceParams,
    affect_factor: float,
    duplicate_ids: frozenset[str],
) -> tuple[tuple[WorkspaceProposal, ...], tuple[ScoredProposal, ...], tuple[RejectedProposal, ...]]:
    """竞争 → (入选提案按名次, 全量 trace, 淘汰日志)——单遍确定性。

    trace 序 = (rank 升序（未入选排后）, proposal_id 升序)。
    """
    scored_entries: list[tuple[float, tuple[float, float, float, float, float], WorkspaceProposal, str]] = []
    for p in proposals:
        score, comps = score_proposal(p, params, affect_factor)
        if p.proposal_id in duplicate_ids:
            scored_entries.append((score, comps, p, RejectionReason.DUPLICATE.value))
        elif score <= 0.0:
            scored_entries.append((score, comps, p, RejectionReason.LOW_SALIENCE.value))
        else:
            scored_entries.append((score, comps, p, ""))
    candidates = sorted(
        ((e[0], e[2]) for e in scored_entries if not e[3]),
        key=lambda sp: (-sp[0], sp[1].sponsor_module, sp[1].proposal_id),
    )
    admitted = candidates[: params.capacity_k]
    overflow = candidates[params.capacity_k:]
    rank_map = {p.proposal_id: i for i, (_, p) in enumerate(admitted)}
    trace: list[ScoredProposal] = []
    rejections: list[RejectedProposal] = []
    for score, p in overflow:
        rejections.append(RejectedProposal(p.proposal_id, RejectionReason.OVER_CAPACITY, score))
    for score, comps, p, reason in scored_entries:
        if reason:
            trace.append(ScoredProposal(p.proposal_id, score, comps, None, False, reason))
            rejections.append(RejectedProposal(p.proposal_id, RejectionReason(reason), score))
        else:
            trace.append(ScoredProposal(
                p.proposal_id, score, comps, rank_map.get(p.proposal_id),
                p.proposal_id in rank_map,
                "" if p.proposal_id in rank_map else RejectionReason.OVER_CAPACITY.value,
            ))
    trace.sort(key=lambda t: (0 if t.admitted else 1, t.rank if t.rank is not None else 1 << 30,
                              t.proposal_id))
    return (tuple(p for _, p in admitted), tuple(trace), tuple(rejections))


def competition_digest(trace: tuple[ScoredProposal, ...]) -> str:
    """竞争轨迹 digest（bit-exact 重放载体）。"""
    return content_digest([[t.proposal_id, round(t.score, 12), t.rank, t.admitted, t.reason]
                           for t in trace])
