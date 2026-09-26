"""目标生命周期状态机（L08 §4.1/§4.5/§10 lifecycle.py）。

状态：ACTIVE | BLOCKED | DEFERRED | MODIFIED(rev+1) | RELEASED | SUPERSEDED |
SETTLED（L08 §4.1）。唯一写者 = Goal Ownership（OwnedGoal owner 申报机械强制）。
解除/取代的 goal_id 入废止集，复活即 GoalRevivalError（L08 §4.5 防伪更新：
解除后不得复活旧 goal_id，新目标须重走清单）。blocked 仅记录（GoalProgressView）
——M1 无 blocked→FAILED 阈值（Q-L08-09⑧：达阈分支随 C3/L09 落地）。
"""
import enum
from dataclasses import dataclass
from typing import Any

from galatea.subject.goals.candidates import GoalCandidate
from galatea.subject.goals.checklist import ChecklistVerdict
from galatea.subject.goals.ports import GoalDecision, GoalDecisionLog, GoalWriter
from galatea.subject.goals.owned import GoalRevivalError, OwnedGoal

__all__ = ["GoalStatus", "GoalProgressView", "GoalLifecycle", "LifecycleError"]


class GoalStatus(enum.StrEnum):
    """目标七态（L08 §4.1 状态机）。"""

    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    DEFERRED = "DEFERRED"
    MODIFIED = "MODIFIED"          # 修订瞬态：rev+1 落账后回 ACTIVE（谱系见 OwnedGoal.rev/prior_rev_ref）
    RELEASED = "RELEASED"
    SUPERSEDED = "SUPERSEDED"
    SETTLED = "SETTLED"


@dataclass(frozen=True, slots=True)
class GoalProgressView:
    """只读进度视图（L08 §2.2 goal.progress_view；L04 SelfModelView / L06 prospective 消费）。

    remaining_est：M1 无估计器，恒 None（schema 占位同 m0 load≡0 先例，Q-L01-09⑥）。
    """

    goal_id: str
    status: GoalStatus
    blocked: bool
    remaining_est: float | None = None


class LifecycleError(ValueError):
    """生命周期违例（未知目标/非法转移/重复结算等）。"""


@dataclass(frozen=True, slots=True)
class _GoalEntry:
    goal: OwnedGoal
    status: GoalStatus
    blocked: bool = False


class GoalLifecycle:
    """目标所有权台账（Goal Ownership 独占写者；adopt/revise/supersede/release/进度）。"""

    def __init__(self, policy_version: str) -> None:
        if not policy_version:
            raise ValueError("GoalLifecycle requires policy_version（回执 policy 锚）")
        self._policy_version = policy_version
        self._entries: dict[str, _GoalEntry] = {}
        self._retired: set[str] = set()
        self._progress: list[GoalProgressView] = []
        self._decisions: list[GoalDecisionLog] = []

    # ---- 读取面 ----

    @property
    def policy_version(self) -> str:
        return self._policy_version

    def status_of(self, goal_id: str) -> GoalStatus:
        entry = self._entries.get(goal_id)
        if entry is None:
            raise LifecycleError(f"unknown goal_id {goal_id}")
        return entry.status

    def goal(self, goal_id: str) -> OwnedGoal:
        entry = self._entries.get(goal_id)
        if entry is None:
            raise LifecycleError(f"unknown goal_id {goal_id}")
        return entry.goal

    def snapshot(self) -> tuple[tuple[str, GoalStatus], ...]:
        """全目标状态快照（稳定序；禁容器序依赖）。"""
        return tuple((gid, e.status) for gid, e in sorted(self._entries.items()))

    @property
    def progress_log(self) -> tuple[GoalProgressView, ...]:
        return tuple(self._progress)

    @property
    def decisions(self) -> tuple[GoalDecisionLog, ...]:
        return tuple(self._decisions)

    @property
    def retired_ids(self) -> frozenset[str]:
        return frozenset(self._retired)

    # ---- 写入面（Goal Ownership 独占）----

    def adopt(
        self,
        verdict: ChecklistVerdict,
        candidate: GoalCandidate,
        goal_id: str,
        now_cycle: int,
        *,
        rejected_alternatives: tuple[str, ...] = (),
    ) -> OwnedGoal:
        """清单 ACCEPT → OwnedGoal（C-5 主体侧理由并入 adopted_reasons；禁复活）。"""
        if verdict.decision is not GoalDecision.ACCEPT:
            raise LifecycleError(
                f"candidate {candidate.candidate_id} verdict {verdict.decision.value} != ACCEPT"
            )
        if verdict.candidate_id != candidate.candidate_id:
            raise LifecycleError("verdict/candidate mismatch")
        if goal_id in self._retired:
            raise GoalRevivalError(
                f"goal_id {goal_id} is retired（解除后不得复活，L08 §4.5；新目标须重走清单）"
            )
        if goal_id in self._entries:
            raise LifecycleError(f"goal_id {goal_id} already exists")
        adopted_reasons = (*candidate.motive_refs, *verdict.subject_side_reason_refs)
        goal = OwnedGoal(
            owner=GoalWriter.GOAL_OWNERSHIP,
            goal_id=goal_id,
            content_ref=candidate.content_ref,
            source_kind=candidate.source_kind,
            adopted_reasons=adopted_reasons,
            subject_side_reason_refs=verdict.subject_side_reason_refs,
            commitment_receipt=verdict.to_receipt(goal_id, self._policy_version).digest,
            settle=candidate.settle,
            adopted_cycle=now_cycle,
            expires_at_cycle=now_cycle + candidate.ttl_cycles,
            rejected_alternatives=rejected_alternatives,
        )
        self._entries[goal_id] = _GoalEntry(goal=goal, status=GoalStatus.ACTIVE)
        self._decisions.append(
            GoalDecisionLog(
                candidate_id=candidate.candidate_id,
                decision=GoalDecision.ACCEPT,
                reason_refs=adopted_reasons,
                counterfactual_sensitive=True,
                ts=now_cycle,
            )
        )
        return goal

    def revise(self, goal_id: str, now_cycle: int, /, **changes: Any) -> OwnedGoal:
        """修订 = OwnedGoal.revise(rev+1) 落账 + MODIFY 决策日志（禁原地改写）。

        goal_id/now_cycle 为 positional-only：受管字段（goal_id/rev 等）只能经
        **changes 传入并在 OwnedGoal.revise 的受管字段守卫处被拒。
        """
        entry = self._entries.get(goal_id)
        if entry is None:
            raise LifecycleError(f"unknown goal_id {goal_id}")
        if entry.status in (GoalStatus.RELEASED, GoalStatus.SUPERSEDED, GoalStatus.SETTLED):
            raise LifecycleError(f"goal {goal_id} terminal at {entry.status.value}")
        revised = entry.goal.revise(**changes)
        self._entries[goal_id] = _GoalEntry(goal=revised, status=GoalStatus.ACTIVE, blocked=entry.blocked)
        self._decisions.append(
            GoalDecisionLog(
                candidate_id=goal_id,
                decision=GoalDecision.MODIFY,
                reason_refs=(revised.prior_rev_ref or f"{goal_id}#rev{entry.goal.rev}",),
                counterfactual_sensitive=True,
                ts=now_cycle,
            )
        )
        return revised

    def record_progress(
        self, goal_id: str, blocked: bool, evidence_refs: tuple[str, ...]
    ) -> GoalProgressView:
        """进度记录（L08 §4.5：ACTIVE 目标每 T4 复核；M1 blocked 仅记录不判 FAILED）。"""
        entry = self._entries.get(goal_id)
        if entry is None:
            raise LifecycleError(f"unknown goal_id {goal_id}")
        if entry.status not in (GoalStatus.ACTIVE, GoalStatus.BLOCKED, GoalStatus.DEFERRED):
            raise LifecycleError(f"goal {goal_id} in {entry.status.value} cannot take progress")
        if not evidence_refs:
            raise ValueError("progress requires evidence_refs")
        status = GoalStatus.BLOCKED if blocked else (
            GoalStatus.DEFERRED if entry.status is GoalStatus.DEFERRED else GoalStatus.ACTIVE
        )
        self._entries[goal_id] = _GoalEntry(goal=entry.goal, status=status, blocked=blocked)
        view = GoalProgressView(goal_id=goal_id, status=status, blocked=blocked)
        self._progress.append(view)
        return view

    def defer(self, goal_id: str) -> None:
        """暂停（DEFERRED：临时挂起，可 resume）。"""
        self._transition(goal_id, GoalStatus.ACTIVE, GoalStatus.DEFERRED)

    def resume(self, goal_id: str) -> None:
        self._transition(goal_id, GoalStatus.DEFERRED, GoalStatus.ACTIVE)

    def release(self, goal_id: str, reason_refs: tuple[str, ...]) -> None:
        """解除（RELEASED：须留理由与日志——L08 §4.5；id 入废止集）。"""
        if not reason_refs:
            raise ValueError("release requires reason_refs（禁静默解除，L08 §4.5）")
        self._transition(goal_id, None, GoalStatus.RELEASED)
        self._decisions.append(
            GoalDecisionLog(
                candidate_id=goal_id,
                decision=GoalDecision.RELEASE,
                reason_refs=reason_refs,
                counterfactual_sensitive=True,
                ts=self._entries[goal_id].goal.adopted_cycle,
            )
        )

    def supersede(
        self,
        old_goal_id: str,
        verdict: ChecklistVerdict,
        candidate: GoalCandidate,
        new_goal_id: str,
        now_cycle: int,
    ) -> OwnedGoal:
        """被后续目标取代（旧目标 SUPERSEDED 入废止集；新目标重走清单——C-6/SUPERSEDE 语义）。"""
        self._transition(old_goal_id, None, GoalStatus.SUPERSEDED)
        return self.adopt(verdict, candidate, new_goal_id, now_cycle)

    def close(self, goal_id: str, terminal: GoalStatus) -> None:
        """终态落账（限 RELEASED/SUPERSEDED/SETTLED；供 settlement 模块消费 L10 结算与 TTL 判定）。"""
        if terminal not in (GoalStatus.RELEASED, GoalStatus.SUPERSEDED, GoalStatus.SETTLED):
            raise LifecycleError(f"close() requires a terminal status, got {terminal.value}")
        self._transition(goal_id, None, terminal)

    def _transition(self, goal_id: str, expected: GoalStatus | None, target: GoalStatus) -> None:
        entry = self._entries.get(goal_id)
        if entry is None:
            raise LifecycleError(f"unknown goal_id {goal_id}")
        if expected is not None and entry.status is not expected:
            raise LifecycleError(
                f"goal {goal_id}: {entry.status.value} → {target.value} requires {expected.value}"
            )
        if entry.status in (GoalStatus.RELEASED, GoalStatus.SUPERSEDED, GoalStatus.SETTLED):
            raise LifecycleError(f"goal {goal_id} terminal at {entry.status.value}")
        self._entries[goal_id] = _GoalEntry(goal=entry.goal, status=target, blocked=entry.blocked)
        if target in (GoalStatus.RELEASED, GoalStatus.SUPERSEDED):
            self._retired.add(goal_id)
