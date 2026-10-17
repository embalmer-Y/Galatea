"""思维迭代循环（L07 P4-β 扩展——Q-L07-10；profile p4_beta_mind thought_iteration 节）。

合同（Q-L07-10）：
- **循环四拍** = generate（草稿板 open 草稿/后继）→ evaluate（注入式评估器——生产面
  = P4-α 世界模型 imagine rollout 评分，Q-L04-12 复用；本模块只定合同不绑实现）
  → contradict（与既有草稿两两冲突**检出**——typed ContradictionEvent，不改状态）
  → revise（修正后继：被后继覆盖者 superseded 留痕；事件引用中未被修正者
  = 未驳倒矛盾 → contradicted）；
- **逐拍 receipt**：DraftThoughtReceipt（拍号/供体/评分/矛盾引用/动作 + prev digest
  链——审计 fail-closed 同族）；
- **终止** = 预算上界（think_steps_budget，profile 冻结）或收敛——确定性系统下
  "评分改进 < 阈值"的机械操作化 = **无改进后继**（revise 拍零后继且零状态变化；
  离散生成器无改进产出即收敛，零新自由常量——profile convergence_mode 冻结）；
- **因果判据** = GCTB think_first_advantage（Q-L13-21④）：开/关慢环决策质量差——
  本循环为 TFA 的"开循环"臂载体；
- **层级**（⑤）：评估用世界模型 ≠ 信念内模拟隐藏真值（Q-L04-09 转移语义继承）；
  本模块零 import action/goals 平面（结构守卫既有面消费）。
"""
from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Callable

from galatea.kernel.digest import content_digest
from galatea.subject.workspace.draft import (
    DraftDonor,
    DraftEvaluation,
    DraftHypothesis,
    DraftStatus,
    Scratchpad,
)

__all__ = [
    "ThoughtBeat",
    "ThoughtAction",
    "ContradictionEvent",
    "DraftThoughtReceipt",
    "ThoughtIterationParams",
    "ThoughtLoopResult",
    "ThoughtLoop",
    "ThoughtEvaluator",
    "ConflictFn",
    "ReviseFn",
]


class ThoughtBeat(enum.StrEnum):
    """循环四拍（Q-L07-10①；profile thought_iteration.loop 顺序冻结校验点）。"""

    GENERATE = "generate"
    EVALUATE = "evaluate"
    CONTRADICT = "contradict"
    REVISE = "revise"


class ThoughtAction(enum.StrEnum):
    """逐拍动作词表（receipt.action——typed，禁自由串）。"""

    SEEDS_OPEN = "seeds_open"                    # generate：种子草稿就绪
    SUCCESSORS_OPEN = "successors_open"          # generate：revise 后继就绪
    SCORED = "scored"                            # evaluate：评分落账
    NO_OPEN_DRAFTS = "no_open_drafts"            # evaluate：无 open 草稿
    CONTRADICTIONS_FIRED = "contradictions_fired"
    NO_CONTRADICTION = "no_contradiction"
    SUPERSEDED = "superseded"                    # revise：被替代留痕
    NO_SUCCESSOR = "no_successor"                # revise：零后继（收敛判据输入）


ThoughtEvaluator = Callable[[DraftHypothesis], float]
"""评估器合同：生产面 = RSSM imagine rollout 评分（Q-L07-10①/⑤）；注入式解耦。"""

ConflictFn = Callable[[DraftHypothesis, DraftHypothesis], bool]
"""冲突判据：两草稿是否互斥（域逻辑注入——如目标格不同/预算互斥）。"""


class ConvergenceModeViolation(ValueError):
    """收敛模式词表外（profile convergence_mode 冻结校验）。"""


@dataclass(frozen=True, slots=True)
class ContradictionEvent:
    """typed 矛盾事件（Q-L07-10①；探针实证可开火——INC-08 可失败性在 TFA 判据承载）。"""

    event_id: str
    cycle: int
    iteration: int
    refs: tuple[str, ...]          # 冲突草稿 hypothesis_id（≥2）
    kind: str                      # 域判据引用串（如 "target_exclusive"/"budget_infeasible"）
    detail: str = ""

    def __post_init__(self) -> None:
        if len(self.refs) < 2:
            raise ValueError("contradiction requires ≥2 refs")
        if not self.kind:
            raise ValueError("contradiction kind required（判据引用禁空）")


ReviseFn = Callable[[tuple[ContradictionEvent, ...], tuple[DraftHypothesis, ...], dict[str, float]],
                    tuple[DraftHypothesis, ...]]
"""修正生成：给定矛盾事件 + 存活草稿 + 当前评分，产出后继草稿集合（payload.parent 引用被替代者）。"""


@dataclass(frozen=True, slots=True)
class DraftThoughtReceipt:
    """逐拍回执（Q-L07-10②：拍号/供体/评分/矛盾引用/动作 + prev digest 链）。"""

    beat_index: int                # 全局拍号（跨迭代递增）
    iteration: int
    beat: ThoughtBeat
    action: ThoughtAction
    hypothesis_refs: tuple[str, ...]
    donor: str | None
    scores: tuple[tuple[str, float], ...]
    contradiction_refs: tuple[str, ...]
    prev_digest: str | None

    def digest(self) -> str:
        return content_digest({
            "beat_index": self.beat_index, "iteration": self.iteration, "beat": self.beat.value,
            "action": self.action.value, "hypothesis_refs": list(self.hypothesis_refs),
            "donor": self.donor, "scores": [[h, s] for h, s in self.scores],
            "contradiction_refs": list(self.contradiction_refs), "prev_digest": self.prev_digest,
        })


@dataclass(frozen=True, slots=True)
class ThoughtIterationParams:
    """循环冻结参数（p4_beta_mind.profile thought_iteration 节 typed 视图）。"""

    beats: tuple[ThoughtBeat, ...]         # (generate, evaluate, contradict, revise) 顺序冻结
    think_steps_budget: int                # 迭代预算上界（③）
    evaluate_source: str                   # "rssm_imagine_rollout"
    convergence_mode: str                  # "no_new_successor"（v1.1 冻结）

    def __post_init__(self) -> None:
        if self.beats != (ThoughtBeat.GENERATE, ThoughtBeat.EVALUATE,
                          ThoughtBeat.CONTRADICT, ThoughtBeat.REVISE):
            raise ValueError("thought loop beat order frozen（Q-L07-10①）")
        if self.think_steps_budget < 1:
            raise ValueError("think_steps_budget must be ≥1")
        if self.convergence_mode != "no_new_successor":
            raise ConvergenceModeViolation(
                f"convergence_mode {self.convergence_mode!r} not frozen vocabulary")


@dataclass(frozen=True, slots=True)
class ThoughtLoopResult:
    """循环产物（证据侧消费：receipts 链 + 矛盾事件 + 选择 + 终止形态）。"""

    receipts: tuple[DraftThoughtReceipt, ...]
    contradictions: tuple[ContradictionEvent, ...]
    selected_id: str | None
    selected_score: float | None
    iterations: int
    terminated_by: str             # "budget" | "converged"


class ThoughtLoop:
    """思维循环骨架（Q-L07-10——拍序/receipt/终止/选择机械面；域逻辑全部注入）。"""

    def __init__(self, scratchpad: Scratchpad, evaluator: ThoughtEvaluator,
                 conflict_fn: ConflictFn, revise_fn: ReviseFn,
                 params: ThoughtIterationParams) -> None:
        self._pad = scratchpad
        self._evaluator = evaluator
        self._conflict_fn = conflict_fn
        self._revise_fn = revise_fn
        self._params = params

    def run(self, cycle: int, seed_ids: tuple[str, ...] = ()) -> ThoughtLoopResult:
        receipts: list[DraftThoughtReceipt] = []
        contradictions: list[ContradictionEvent] = []
        prev_digest: str | None = None
        beat_index = 0
        terminated_by = "budget"
        iteration = 0

        for iteration in range(1, self._params.think_steps_budget + 1):
            status_before = {d.hypothesis_id: d.status for d in self._pad.all_drafts()}
            # —— generate ——
            open_ids = tuple(d.hypothesis_id for d in self._pad.by_status(DraftStatus.OPEN))
            if iteration == 1 and seed_ids:
                missing = [h for h in seed_ids if h not in set(open_ids)]
                if missing:
                    raise ValueError(f"seed drafts not open in scratchpad: {missing}")
            gen_action = (ThoughtAction.SUCCESSORS_OPEN if iteration > 1
                          else (ThoughtAction.SEEDS_OPEN if open_ids else ThoughtAction.NO_OPEN_DRAFTS))
            donors = sorted({self._pad.get(h).donor.value for h in open_ids})
            receipts.append(self._emit(receipts, prev_digest, beat_index, iteration,
                                       ThoughtBeat.GENERATE, gen_action, open_ids,
                                       donors[0] if len(donors) == 1 else (",".join(donors) or None),
                                       (), ()))
            prev_digest = receipts[-1].digest()
            beat_index += 1
            # —— evaluate ——
            open_ids = tuple(d.hypothesis_id for d in self._pad.by_status(DraftStatus.OPEN))
            scores: list[tuple[str, float]] = []
            if open_ids:
                for hid in open_ids:
                    score = float(self._evaluator(self._pad.get(hid)))
                    self._pad.evaluate(hid, _evaluation(hid, cycle, score, self._params, iteration))
                    scores.append((hid, score))
                eval_action = ThoughtAction.SCORED
            else:
                eval_action = ThoughtAction.NO_OPEN_DRAFTS
            receipts.append(self._emit(receipts, prev_digest, beat_index, iteration,
                                       ThoughtBeat.EVALUATE, eval_action, open_ids, None,
                                       tuple(scores), ()))
            prev_digest = receipts[-1].digest()
            beat_index += 1
            # —— contradict（只检出：typed 事件；状态处置归 revise 拍）——
            evaluated = self._pad.by_status(DraftStatus.EVALUATED)
            events: list[ContradictionEvent] = []
            for i in range(len(evaluated)):
                for j in range(i + 1, len(evaluated)):
                    a, b = evaluated[i], evaluated[j]
                    if self._conflict_fn(a, b):
                        events.append(ContradictionEvent(
                            event_id=f"cx-{cycle}-{iteration}-{i}-{j}", cycle=cycle,
                            iteration=iteration, refs=(a.hypothesis_id, b.hypothesis_id),
                            kind="domain_conflict_fn"))
            contradictions.extend(events)
            cx_action = ThoughtAction.CONTRADICTIONS_FIRED if events else ThoughtAction.NO_CONTRADICTION
            receipts.append(self._emit(receipts, prev_digest, beat_index, iteration,
                                       ThoughtBeat.CONTRADICT, cx_action,
                                       tuple(h for e in events for h in e.refs), None, (),
                                       tuple(e.event_id for e in events)))
            prev_digest = receipts[-1].digest()
            beat_index += 1
            # —— revise（修正 + 矛盾处置：被后继覆盖 → superseded；未被修正的矛盾引用
            #      → contradicted——"未被修正的矛盾 = 驳倒"，零静默残留）——
            surviving = self._pad.by_status(DraftStatus.EVALUATED)
            current_scores = {h: s for h, s in scores}
            successors = tuple(self._revise_fn(tuple(contradictions), surviving, current_scores)) \
                if (surviving or events) else ()
            superseded: list[str] = []
            for succ in successors:
                parent = succ.payload.get("parent")
                self._pad.submit(succ)
                if isinstance(parent, str) and parent in {d.hypothesis_id for d in surviving}:
                    self._pad.supersede(parent, succ.hypothesis_id)
                    superseded.append(parent)
            event_refs = {h for e in events for h in e.refs}
            for hid in sorted(event_refs):
                if self._pad.get(hid).status is DraftStatus.EVALUATED:
                    self._pad.contradict(hid)
            rev_action = ThoughtAction.SUPERSEDED if superseded else (
                ThoughtAction.SUCCESSORS_OPEN if successors else ThoughtAction.NO_SUCCESSOR)
            receipts.append(self._emit(receipts, prev_digest, beat_index, iteration,
                                       ThoughtBeat.REVISE, rev_action,
                                       tuple(s.hypothesis_id for s in successors),
                                       DraftDonor.WORKSPACE_LOOP.value, (), ()))
            prev_digest = receipts[-1].digest()
            beat_index += 1
            # —— 终止判据（③）：收敛 = 零后继且零状态变化（确定性机械操作化）——
            status_after = {d.hypothesis_id: d.status for d in self._pad.all_drafts()}
            if not successors and status_after == status_before:
                terminated_by = "converged"
                break

        # —— 选择（确定性：最高分 → hypothesis_id 字典序；非信念面——结果仅为循环产物）——
        candidates = [(d, s) for d in self._pad.by_status(DraftStatus.EVALUATED)
                      for s in [self._pad.latest_score(d.hypothesis_id)] if s is not None]
        if candidates:
            best = min(candidates, key=lambda t: (-t[1], t[0].hypothesis_id))
            selected_id, selected_score = best[0].hypothesis_id, best[1]
        else:
            selected_id, selected_score = None, None
        return ThoughtLoopResult(
            receipts=tuple(receipts), contradictions=tuple(contradictions),
            selected_id=selected_id, selected_score=selected_score,
            iterations=iteration, terminated_by=terminated_by)

    @staticmethod
    def _emit(receipts: list[DraftThoughtReceipt], prev_digest: str | None, beat_index: int,
              iteration: int, beat: ThoughtBeat, action: ThoughtAction,
              refs: tuple[str, ...], donor: str | None,
              scores: tuple[tuple[str, float], ...],
              contradiction_refs: tuple[str, ...]) -> DraftThoughtReceipt:
        return DraftThoughtReceipt(
            beat_index=beat_index, iteration=iteration, beat=beat, action=action,
            hypothesis_refs=refs, donor=donor, scores=scores,
            contradiction_refs=contradiction_refs, prev_digest=prev_digest)


def _evaluation(hid: str, cycle: int, score: float, params: ThoughtIterationParams,
                iteration: int) -> DraftEvaluation:
    return DraftEvaluation(hypothesis_id=hid, cycle=cycle, score=score,
                           evaluator_ref=params.evaluate_source, beat=iteration)
