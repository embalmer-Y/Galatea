"""三控制器提案构造与 ω 评分仲裁（L09 §4.1/§4.2/§10 controllers.py，C3 实现期）。

启用电（Q-L09-02）：Habit / ModelBased / ActivePerception——Reflex 延续禁用
（白名单刺激未定义，Q-L09-06 C0 结论延续）、Language/social C4（D-14）。
偏序（viability 保护 > ACTIVE 目标 > 信息增益 > 习惯低成本 > 语言/社会）仅在
metacontrol 轮内 tie-break（元决策先于控制器选择）。

ω 评分（Q-L09-01）：五项等权 1:1:1:1:1，score = ω_g·goal + ω_c·conf − ω_cost·cost
+ ω_u·info + ω_a·min(1, affect·factor)——**成本项 = 字面负向**（REV-0017 R3 钉死）；
affect_factor ∈ [0.5, 2.0]（消费 C2 调制台账 CONFIRMED 面）。

共同纪律（L09 §4.1）：提案必带 rationale_refs 非空 + predicted_outcome_ref；
提案不具执行力；tie-break (score desc, controller_kind_rank, proposal_id)。
"""
from dataclasses import dataclass

from dataclasses import dataclass
from galatea.kernel.digest import content_digest

__all__ = [
    "ControllerKind",
    "ControlProposal",
    "score_proposal",
    "arbitrate_proposals",
]


class ControllerKind:
    """控制器枚举与优先级秩（Q-L09-02 偏序：小秩优先——viability 保护由 VIABILITY
    源候选承载于 L08 仲裁面；本秩为控制器 tie-break 面）。"""

    HABIT = "Habit"
    MODEL_BASED = "ModelBased"
    ACTIVE_PERCEPTION = "ActivePerception"
    REFLEX = "Reflex"                # C3 禁用（构造面拒绝）
    LANGUAGE = "Language"            # C4 禁用

    #: 控制器 tie-break 秩（Q-L09-02① 偏序映射：ModelBased[ACTIVE 目标] > ActivePerception
    #: [信息增益] > Habit[习惯低成本] > 语言/社会——REV-0018 R2 修正：初版 HABIT:0 系误序）
    RANK: dict[str, int] = {MODEL_BASED: 0, ACTIVE_PERCEPTION: 1, HABIT: 2,
                            REFLEX: 3, LANGUAGE: 4}


# affect_factor 由**装配层**从 C2 调制台账 CONFIRMED 面读出后以 float 传入
#（P03：action 域禁 import affect——affect 不直达执行的结构面）。


@dataclass(frozen=True, slots=True)
class ControlProposal:
    """控制器提案（L09 §4.1：rationale_refs 非空 + predicted_outcome_ref；不具执行力）。"""

    proposal_id: str
    controller: str
    action_class: str                       # L10 五原语语义（move/forage/eat/rest/look）
    goal_align: float                       # ω_g 分量 [0,1]
    confidence: float                       # ω_c 分量 [0,1]
    cost: float                             # ω_cost 分量 [0,1]（负向项）
    expected_info_gain: float               # ω_u 分量 [0,1]
    affect_component: float                 # ω_a 分量基值 [0,1]（×factor 后 clip）
    rationale_refs: tuple[str, ...]
    predicted_outcome_ref: str

    def __post_init__(self) -> None:
        if self.controller not in (ControllerKind.HABIT, ControllerKind.MODEL_BASED,
                                   ControllerKind.ACTIVE_PERCEPTION):
            raise ValueError(
                f"controller {self.controller!r} not enabled at C3（Q-L09-02 启用电）"
            )
        if not self.rationale_refs:
            raise ValueError("ControlProposal requires rationale_refs（禁无理由提案）")
        if not self.predicted_outcome_ref:
            raise ValueError("ControlProposal requires predicted_outcome_ref（L09 §4.1）")
        for name in ("goal_align", "confidence", "cost", "expected_info_gain",
                     "affect_component"):
            v = getattr(self, name)
            if not 0.0 <= v <= 1.0:
                raise ValueError(f"proposal component {name} out of [0,1]: {v!r}")


def score_proposal(p: ControlProposal, affect_factor: float) -> float:
    """ω 评分（Q-L09-01 等权；成本字面负向 REV-0017 R3；affect ×factor 域 clip）。"""
    return (
        p.goal_align + p.confidence - p.cost
        + p.expected_info_gain + min(1.0, p.affect_component * affect_factor)
    ) / 5.0


def arbitrate_proposals(
    proposals: tuple[ControlProposal, ...], affect_factor: float, cycle: int
) -> tuple[ControlProposal | None, tuple[tuple[str, str], ...]]:
    """控制器仲裁（评分 → tie-break (score desc, rank, proposal_id)；落选留痕）。"""
    if not proposals:
        return None, ()
    scored = sorted(
        ((score_proposal(p, affect_factor), p) for p in proposals),
        key=lambda sp: (-sp[0], ControllerKind.RANK[sp[1].controller], sp[1].proposal_id),
    )
    winner = scored[0][1]
    dropped = tuple(
        (p.proposal_id, f"SCORE_LOST({s:.6f})") for s, p in scored[1:]
    )
    return winner, dropped


def arbitration_digest(cycle: int, winner: ControlProposal | None,
                       dropped: tuple[tuple[str, str], ...]) -> str:
    """仲裁 digest（bit-exact 重放载体）。"""
    return content_digest({
        "cycle": cycle,
        "winner": winner.proposal_id if winner else None,
        "dropped": [list(d) for d in dropped],
    })
