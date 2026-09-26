"""GoalCandidate、TTL 台账、过期/容量日志（L08 §2.2 goal.candidates / §10 candidates.py）。

纪律：候选有 TTL（C-6；Q-L08-02：256 cycles = 一 regime 驻留窗），过期入日志禁静默
丢弃（RejectionLog(EXPIRED)）；每 T4 批次候选上界 = source_kind 枚举基数 8，超限按
移除序（urgency 最低先移除，tie 按 candidate_id 升序先移除——Q-L08-02 REV-0006 R4
补裁）逐个记 RejectionLog(CAPACITY)。候选是 GoalCandidate 类型，与 ExternalRequest/
OwnedGoal 无隐式转换（四型分离，ports.assert_four_type_separation）。
"""
import math
from dataclasses import dataclass, replace

from galatea.subject.goals.ports import (
    GoalDecision,
    GoalDecisionLog,
    RejectionCode,
    SettlePredicate,
)
from galatea.subject.goals.motives import Motive, MotiveSource

__all__ = ["SettleCriterion", "GoalCandidate", "CandidateLedger", "CandidateBatchOverflow"]


@dataclass(frozen=True, slots=True)
class SettleCriterion:
    """结算判据（C-7 输入；词表 = ports.SettlePredicate，Q-L08-09③）。

    primitive_completion 无参数；stored_food_at_least/energy_at_least 的阈值
    n/x 冻结于 M1 统计计划（SC3 运行前），构造时必须显式给出。
    """

    predicate: SettlePredicate
    threshold: float | None = None

    def __post_init__(self) -> None:
        if self.predicate is SettlePredicate.PRIMITIVE_COMPLETION:
            if self.threshold is not None:
                raise ValueError("primitive_completion takes no threshold")
            return
        if self.threshold is None or math.isnan(self.threshold) or self.threshold < 0.0:
            raise ValueError(f"{self.predicate.value} requires threshold >= 0（统计计划冻结值）")


@dataclass(frozen=True, slots=True)
class GoalCandidate:
    """候选（L08 §2.2：source_kind/motive_refs/content_ref/ttl/checklist_status）。"""

    candidate_id: str
    source_kind: MotiveSource
    motive_refs: tuple[str, ...]
    content_ref: str
    settle: SettleCriterion
    required_primitives: tuple[str, ...]   # C-2 预算核算与 C-1 白名单检查的输入
    ttl_cycles: int                        # C-6：声明 TTL（profile 初值 256，Q-L08-02）
    created_cycle: int
    urgency: float
    checklist_status: str | None = None    # PortOut 视图：清单判定后经 with_checklist_status 回填

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.content_ref:
            raise ValueError("GoalCandidate requires candidate_id and content_ref")
        if not self.motive_refs:
            raise ValueError("GoalCandidate requires motive_refs")
        if not self.required_primitives:
            raise ValueError("GoalCandidate requires required_primitives（C-1/C-2 输入）")
        if self.ttl_cycles <= 0:
            raise ValueError("GoalCandidate.ttl_cycles must be positive（C-6：无 TTL = UNBOUNDED）")
        if math.isnan(self.urgency) or not 0.0 <= self.urgency <= 1.0:
            raise ValueError("GoalCandidate.urgency out of [0,1]")

    def with_checklist_status(self, status: str) -> "GoalCandidate":
        """清单判定后回填状态（不可变更新；原候选不改写——L00 envelope 精神）。"""
        return replace(self, checklist_status=status)


class CandidateBatchOverflow(ValueError):
    """批次构造违例（内部防护；容量截断本身走 CAPACITY 日志而非异常）。"""


class CandidateLedger:
    """候选台账（唯一写者 = Motivation，L08 §3）：TTL 过期 + 批次容量截断 + 决策日志。

    每源每批次 ≤1 候选由构造侧保证（Q-L08-02：上界 = source_kind 枚举基数 8）；
    本台账机械执行上界与移除序，并对每个被截断/过期候选出 GoalDecisionLog
    （禁静默丢弃，L08 §6）。
    """

    def __init__(self, ttl_cycles: int, max_per_batch: int) -> None:
        if ttl_cycles <= 0 or max_per_batch <= 0:
            raise ValueError("ledger requires positive ttl and batch cap")
        self._ttl = ttl_cycles
        self._cap = max_per_batch
        self._active: dict[str, GoalCandidate] = {}
        self._logs: list[GoalDecisionLog] = []

    @property
    def active(self) -> tuple[GoalCandidate, ...]:
        """现役候选（按 created_cycle、candidate_id 稳定排序——禁容器序依赖）。"""
        return tuple(
            sorted(self._active.values(), key=lambda c: (c.created_cycle, c.candidate_id))
        )

    @property
    def logs(self) -> tuple[GoalDecisionLog, ...]:
        return tuple(self._logs)

    def submit_batch(self, candidates: tuple[GoalCandidate, ...], batch_cycle: int) -> tuple[GoalCandidate, ...]:
        """提交一个 T4 批次：容量截断 + 每源 ≤1 检查，返回存活候选。

        移除序（Q-L08-02 REV-0006 R4 补裁）：urgency 最低者先移除；tie 按
        candidate_id 升序**先移除**（即同 urgency 保留较大 id）。被移除者逐个记
        CAPACITY（按移除序落账）。REV-0007 R3 补测钉死本序（test_candidate_ledger_ttl.py）。
        """
        seen_sources: dict[MotiveSource, str] = {}
        for cand in candidates:
            if cand.created_cycle != batch_cycle:
                raise CandidateBatchOverflow(
                    f"candidate {cand.candidate_id} created_cycle {cand.created_cycle}"
                    f" != batch_cycle {batch_cycle}"
                )
            if cand.candidate_id in self._active:
                raise CandidateBatchOverflow(f"duplicate candidate_id {cand.candidate_id}")
            prior = seen_sources.get(cand.source_kind)
            if prior is not None:
                raise CandidateBatchOverflow(
                    f"source_kind {cand.source_kind.value} already submitted in batch"
                    f"（每源每批次 ≤1，Q-L08-02）: {prior} vs {cand.candidate_id}"
                )
            seen_sources[cand.source_kind] = cand.candidate_id

        removal_order = sorted(candidates, key=lambda c: (c.urgency, c.candidate_id))
        n_drop = max(0, len(candidates) - self._cap)
        dropped = removal_order[:n_drop]
        kept = removal_order[n_drop:]
        for cand in dropped:
            self._logs.append(
                GoalDecisionLog(
                    candidate_id=cand.candidate_id,
                    decision=GoalDecision.REJECT,
                    reason_refs=cand.motive_refs,
                    counterfactual_sensitive=False,
                    rejection_code=RejectionCode.CAPACITY,
                    ts=batch_cycle,
                )
            )
        for cand in kept:
            self._active[cand.candidate_id] = cand
        return tuple(kept)

    def expire(self, now_cycle: int) -> tuple[str, ...]:
        """TTL 过期清账：created_cycle + ttl ≤ now 的候选移出并记 EXPIRED（禁静默丢弃）。

        返回过期 candidate_id 元组（稳定序）。
        """
        expired: list[str] = []
        for cand in self.active:
            if cand.created_cycle + cand.ttl_cycles <= now_cycle:
                expired.append(cand.candidate_id)
        for cid in expired:
            cand = self._active.pop(cid)
            self._logs.append(
                GoalDecisionLog(
                    candidate_id=cid,
                    decision=GoalDecision.REJECT,
                    reason_refs=cand.motive_refs,
                    counterfactual_sensitive=False,
                    rejection_code=RejectionCode.EXPIRED,
                    ts=now_cycle,
                )
            )
        return tuple(expired)

    def consume(self, candidate_id: str) -> GoalCandidate:
        """清单 ACCEPT 后取走候选（进入 owned 侧；台账移除，防二次采纳）。"""
        cand = self._active.pop(candidate_id, None)
        if cand is None:
            raise KeyError(f"candidate {candidate_id} not active（不存在/已过期/已采纳）")
        return cand

    def reject(self, candidate: Motive | GoalCandidate, code: RejectionCode, ts: int) -> None:
        """清单 REJECT 落账（候选移出台账；reason_refs 取其动机引用）。"""
        cand = _as_candidate(candidate)
        self._active.pop(cand.candidate_id, None)
        self._logs.append(
            GoalDecisionLog(
                candidate_id=cand.candidate_id,
                decision=GoalDecision.REJECT,
                reason_refs=cand.motive_refs,
                counterfactual_sensitive=True,
                rejection_code=code,
                ts=ts,
            )
        )


def _as_candidate(obj: Motive | GoalCandidate) -> GoalCandidate:
    if isinstance(obj, GoalCandidate):
        return obj
    raise TypeError(f"reject() expects GoalCandidate, got {type(obj).__name__}（四型分离）")
