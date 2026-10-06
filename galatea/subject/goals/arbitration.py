"""Pareto 仲裁与七源动机生产者接线（L08 §4.3/§9 C3 行/§10 arbitration.py，C3 实现期）。

裁决承载（c3_motivation.profile v1.0 + Q-L08-03/04 行内补裁）：
- 五维齐向向量（viability_benefit, norm_satisfaction, info_value,
  affective_consistency, cost_inverse）等权 1:1:1:1:1；**front = 支配判定**
  （非加权和——权重仅 front 内 tie-break）；
- 分量承载映射 = 源类型确定性映射（Q-L08-03② 实现补裁）：viability 维承载
  {VIABILITY(事件二值), OPPORTUNITY, MISMATCH, COMMITMENT, REQUEST}（urgency），
  norm/info/affect 维各自独占源；cost_inverse = 0.5 占位（MW0 无成本估计器，
  Q-L01-09⑥ schema 占位先例）；
- 优先序（Q-L08-04）：VIABILITY > NORM > COMMITMENT > OTHER；
  tie-break (priority_class, pareto_score desc, candidate_id asc)；零 RNG；
- ArbitrationTrace 必留 dropped[] 与理由（理由敏感性反事实基础）；
- C-3 冲突检测 = front>1（多源共存待仲裁）。
"""
from dataclasses import dataclass, field

from galatea.kernel.digest import content_digest
from galatea.subject.goals.motives import Motive, MotiveSource

__all__ = [
    "CandidateVector",
    "ArbitrationTrace",
    "conflict_fronts",
    "pareto_front",
    "priority_class_of",
    "arbitrate",
    "vector_of",
]

#: Pareto 五维（Q-L08-03；成本以 (1−cost) 归一为收益向——本表 cost_inverse 恒 0.5 占位）
_DIMS: tuple[str, ...] = ("viability_benefit", "norm_satisfaction", "info_value",
                          "affective_consistency", "cost_inverse")
_COST_PLACEHOLDER = 0.5       # Q-L01-09⑥ schema 占位先例（MW0 无成本估计器）
_VIABILITY_CARRIER: frozenset[MotiveSource] = frozenset({
    MotiveSource.VIABILITY, MotiveSource.OPPORTUNITY, MotiveSource.MISMATCH,
    MotiveSource.COMMITMENT, MotiveSource.REQUEST,
})

#: 优先序类（Q-L08-04）：VIABILITY > NORM > COMMITMENT > OTHER
_PRIORITY_RANK: dict[str, int] = {"VIABILITY": 0, "NORM": 1, "COMMITMENT": 2, "OTHER": 3}


@dataclass(frozen=True, slots=True)
class CandidateVector:
    """候选向量（五维齐向 [0,1]；绑定动机引用——审计面）。"""

    candidate_id: str
    source_kind: MotiveSource
    vector: tuple[float, ...]          # 五维，齐向收益
    motive_ref: str                    # 产生该候选的 Motive 证据锚

    def __post_init__(self) -> None:
        if len(self.vector) != 5:
            raise ValueError("CandidateVector requires exactly 5 dims（Q-L08-03）")
        for v in self.vector:
            if not 0.0 <= v <= 1.0:
                raise ValueError(f"vector dim out of [0,1]: {v!r}")


def vector_of(candidate_id: str, motive: Motive) -> CandidateVector:
    """源类型确定性分量映射（Q-L08-03② 实现补裁——见模块 docstring 表）。"""
    src = motive.source_kind
    viability = motive.urgency if src in _VIABILITY_CARRIER else 0.0
    norm = 1.0 if src is MotiveSource.NORM else 0.0
    info = motive.urgency if src is MotiveSource.CURIOSITY else 0.0
    aff = motive.urgency if src is MotiveSource.AFFECTIVE else 0.0
    return CandidateVector(
        candidate_id=candidate_id, source_kind=src,
        vector=(viability, norm, info, aff, _COST_PLACEHOLDER),
        motive_ref=f"motive.{src.value}@{motive.ts}",
    )


def pareto_front(vectors: dict[str, tuple[float, ...]]) -> tuple[str, ...]:
    """支配判定（Q-L08-03③：v 支配 u ⟺ ∀i v_i ≥ u_i ∧ ∃i v_i > u_i；front = 未被支配集）。"""
    ids = list(vectors)
    front: list[str] = []
    for v in ids:
        dominated = any(
            all(vectors[o][i] >= vectors[v][i] for i in range(len(vectors[v])))
            and any(vectors[o][i] > vectors[v][i] for i in range(len(vectors[v])))
            for o in ids if o != v
        )
        if not dominated:
            front.append(v)
    return tuple(sorted(front))


def priority_class_of(src: MotiveSource) -> str:
    """源 → 优先序类（Q-L08-04：VIABILITY/NORM/COMMITMENT 直映，其余 OTHER）。"""
    if src is MotiveSource.VIABILITY:
        return "VIABILITY"
    if src is MotiveSource.NORM:
        return "NORM"
    if src is MotiveSource.COMMITMENT:
        return "COMMITMENT"
    return "OTHER"


@dataclass(frozen=True, slots=True)
class ArbitrationTrace:
    """仲裁轨迹（L08 §4.3：dropped[] 与理由必留——理由敏感性反事实基础）。"""

    cycle: int
    front: tuple[str, ...]
    dropped: tuple[tuple[str, str], ...]     # (candidate_id, reason)
    picked: str | None
    picked_reason: str
    conflict: bool                            # C-3：front>1 = 多源共存待仲裁
    content_digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "content_digest", content_digest({
            "cycle": self.cycle, "front": list(self.front),
            "dropped": [list(d) for d in self.dropped],
            "picked": self.picked, "reason": self.picked_reason,
            "conflict": self.conflict,
        }))


def conflict_fronts(candidates: tuple[CandidateVector, ...]) -> tuple[str, ...]:
    """C-3 冲突检测（事件级：front > 1 = 多源共存待仲裁；单候选无冲突）。"""
    if not candidates:
        return ()
    return pareto_front({c.candidate_id: c.vector for c in candidates})


def arbitrate(candidates: tuple[CandidateVector, ...], cycle: int) -> ArbitrationTrace:
    """仲裁（front → 优先序全序 tie-break；dropped 留痕；零 RNG——Q-L08-04③）。"""
    if not candidates:
        return ArbitrationTrace(
            cycle=cycle, front=(), dropped=(), picked=None,
            picked_reason="no_candidates", conflict=False,
        )
    vec_map = {c.candidate_id: c.vector for c in candidates}
    front = pareto_front(vec_map)
    scores: dict[str, float] = {cid: sum(v) for cid, v in vec_map.items()}  # 等权加和仅 front 内序
    classes: dict[str, str] = {c.candidate_id: priority_class_of(c.source_kind) for c in candidates}
    ranked = sorted(front, key=lambda cid: (_PRIORITY_RANK[classes[cid]], -scores[cid], cid))
    picked = ranked[0]
    dropped: list[tuple[str, str]] = []
    for c in candidates:
        if c.candidate_id == picked:
            continue
        if c.candidate_id not in front:
            dropped.append((c.candidate_id, "DOMINATED_OUT_OF_FRONT"))
        else:
            dropped.append((c.candidate_id,
                            f"FRONT_LOST_TIEBREAK(class={classes[c.candidate_id]})"))
    return ArbitrationTrace(
        cycle=cycle, front=front, dropped=tuple(dropped), picked=picked,
        picked_reason=f"PRIORITY_CLASS={classes[picked]}", conflict=len(front) > 1,
    )
