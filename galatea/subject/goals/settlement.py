"""GoalSettlement 消费、SettlementPending、revision（L08 §2.1 goal.settlement_in / §6 / §10 settlement.py）。

纪律：只接受 L10 结算系统产出的 `GoalSettlement`（L10 §4.5 独占写者；本档消费）；
UNKNOWN 是合法结算（目标保持 ACTIVE 待复核，禁把 unresolved 归为 FAILED——L10 §4.5/
L08 §6）；FAILED 判据 M1 = TTL-only（Q-L08-09⑧：TTL 到期未达成由本模块自动落账）；
禁伪造 ACHIEVED（ACHIEVED/FAILED 结算必须携带证据引用）；迟到结算以 revision 表达
（新记录引用旧记录，禁改写历史）。
"""
from dataclasses import dataclass, replace
from enum import StrEnum

from galatea.subject.action.ports import GoalSettlement, SettlementKind
from galatea.subject.goals.lifecycle import GoalLifecycle, GoalStatus, LifecycleError

__all__ = ["SettlementSource", "SettlementRecord", "SettlementRegistry", "settle", "expire_unsettled", "pending"]


class SettlementSource(StrEnum):
    """结算来源（L10 结算系统 vs 本档 TTL-only 自动判定，Q-L08-09⑧）。"""

    L10_SETTLEMENT = "L10_SETTLEMENT"
    TTL_EXPIRY = "TTL_EXPIRY"


@dataclass(frozen=True, slots=True)
class SettlementRecord:
    """结算记录（append-only；UNKNOWN → applied=None 目标保持 ACTIVE）。"""

    goal_ref: str
    outcome_kind: SettlementKind
    source: SettlementSource
    evidence_refs: tuple[str, ...]
    ts: int
    applied_status: GoalStatus | None
    record_id: int = 0                   # 台账分配（单调，append-only）
    revision_of: int | None = None       # 迟到结算：引用被修订的旧 record_id


class SettlementRegistry:
    """结算台账（append-only；本档唯一写者；record_id 单调分配）。"""

    def __init__(self) -> None:
        self._records: list[SettlementRecord] = []
        self._next_id = 1

    @property
    def records(self) -> tuple[SettlementRecord, ...]:
        return tuple(self._records)

    def append(self, record: SettlementRecord) -> SettlementRecord:
        stored = replace(record, record_id=self._next_id)
        self._next_id += 1
        self._records.append(stored)
        return stored

    def latest_for(self, goal_ref: str) -> SettlementRecord | None:
        found = [r for r in self._records if r.goal_ref == goal_ref]
        return found[-1] if found else None


def settle(
    settlement: object,
    lifecycle: GoalLifecycle,
    registry: SettlementRegistry,
    now_cycle: int,
) -> SettlementRecord:
    """消费 L10 结算（L08 §2.1 goal.settlement_in）。

    映射：ACHIEVED/FAILED → SETTLED；ABANDONED → RELEASED；SUPERSEDED → SUPERSEDED
    （均入废止集）；UNKNOWN → 目标保持 ACTIVE（合法结算，禁负偏置自欺）。
    已终态目标的迟到结算 → revision 记录（不改状态、不改历史）。
    """
    if not isinstance(settlement, GoalSettlement):
        raise TypeError(
            f"settle() consumes L10 GoalSettlement, got {type(settlement).__name__}（禁伪造结算）"
        )
    if not settlement.evidence_refs:
        raise ValueError(
            f"settlement {settlement.outcome_kind.value} requires evidence_refs（禁伪造 ACHIEVED/FAILED）"
        )
    applied: GoalStatus | None
    match settlement.outcome_kind:
        case SettlementKind.ACHIEVED | SettlementKind.FAILED:
            applied = GoalStatus.SETTLED
        case SettlementKind.ABANDONED:
            applied = GoalStatus.RELEASED
        case SettlementKind.SUPERSEDED:
            applied = GoalStatus.SUPERSEDED
        case SettlementKind.UNKNOWN:
            applied = None
        case _:
            raise LifecycleError(f"unhandled settlement kind {settlement.outcome_kind}")

    prior = registry.latest_for(settlement.goal_ref)
    if prior is not None:
        if applied is None:
            raise LifecycleError("late UNKNOWN settlement is not a revision（保持 ACTIVE 即可）")
        record = registry.append(
            SettlementRecord(
                goal_ref=settlement.goal_ref,
                outcome_kind=settlement.outcome_kind,
                source=SettlementSource.L10_SETTLEMENT,
                evidence_refs=settlement.evidence_refs,
                ts=now_cycle,
                applied_status=None,      # 修订不改状态、不改历史（append-only 留痕）
                revision_of=prior.record_id,
            )
        )
        return record

    if applied is not None:
        try:
            lifecycle.close(settlement.goal_ref, applied)
        except LifecycleError as exc:
            raise LifecycleError(f"settlement for {settlement.goal_ref}: {exc}") from exc
    record = registry.append(
        SettlementRecord(
            goal_ref=settlement.goal_ref,
            outcome_kind=settlement.outcome_kind,
            source=SettlementSource.L10_SETTLEMENT,
            evidence_refs=settlement.evidence_refs,
            ts=now_cycle,
            applied_status=applied,
        )
    )
    return record


def expire_unsettled(
    lifecycle: GoalLifecycle,
    registry: SettlementRegistry,
    now_cycle: int,
) -> tuple[str, ...]:
    """TTL-only 自动结算（Q-L08-09⑧）：expires_at_cycle ≤ now 的未结算目标 → FAILED/SETTLED。

    返回被自动结算的 goal_id 元组（稳定序）。禁伪造 ACHIEVED 的镜像面：TTL 到期
    不得保持 ACTIVE 悬置（不可结算的僵尸目标，Q-L08-01 C-6 立法动机）。
    """
    expired: list[str] = []
    for gid, status in lifecycle.snapshot():
        if status not in (GoalStatus.ACTIVE, GoalStatus.BLOCKED, GoalStatus.DEFERRED):
            continue
        if lifecycle.goal(gid).expires_at_cycle <= now_cycle:
            expired.append(gid)
    for gid in expired:
        lifecycle.close(gid, GoalStatus.SETTLED)
        registry.append(
            SettlementRecord(
                goal_ref=gid,
                outcome_kind=SettlementKind.FAILED,
                source=SettlementSource.TTL_EXPIRY,
                evidence_refs=(f"ttl_expiry@{now_cycle}",),
                ts=now_cycle,
                applied_status=GoalStatus.SETTLED,
            )
        )
    return tuple(expired)


def pending(lifecycle: GoalLifecycle, registry: SettlementRegistry) -> tuple[str, ...]:
    """SettlementPending 视图：存活目标中尚无终局结算者（最新记录缺失或为
    UNKNOWN——UNKNOWN 合法结算后目标仍待终局；L08 §6 禁伪造 ACHIEVED 的观测面）。"""

    def _unresolved(gid: str) -> bool:
        latest = registry.latest_for(gid)
        return latest is None or latest.applied_status is None

    return tuple(
        gid
        for gid, status in lifecycle.snapshot()
        if status in (GoalStatus.ACTIVE, GoalStatus.BLOCKED, GoalStatus.DEFERRED)
        and _unresolved(gid)
    )
