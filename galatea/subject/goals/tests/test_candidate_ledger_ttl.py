"""CandidateLedger TTL 过期与容量截断（L08 §10 test_candidate_ledger_ttl.py；Q-L08-02；REV-0007 R3 补测）。

断言（L08 §7 unit 行"TTL 必测"）：过期 = RejectionLog(EXPIRED) + 台账移除（禁静默
丢弃）；容量截断移除序 = urgency 最低先移除、tie 按 candidate_id 升序**先移除**
（REV-0006 R4 补裁；REV-0007 R3 发现实现与裁决相反，随本测试钉死修正）。
"""
import pytest

from galatea.subject.goals.candidates import (
    CandidateBatchOverflow,
    CandidateLedger,
    GoalCandidate,
    SettleCriterion,
)
from galatea.subject.goals.motives import MotiveSource
from galatea.subject.goals.ports import GoalDecision, RejectionCode, SettlePredicate


def _candidate(cid: str, urgency: float, source: MotiveSource = MotiveSource.OPPORTUNITY) -> GoalCandidate:
    return GoalCandidate(
        candidate_id=cid,
        source_kind=source,
        motive_refs=(f"m.{cid}",),
        content_ref=f"goal.{cid}",
        settle=SettleCriterion(SettlePredicate.PRIMITIVE_COMPLETION),
        required_primitives=("look",),
        ttl_cycles=256,
        created_cycle=0,
        urgency=urgency,
    )


def test_ttl_expiry_logs_expired_and_removes() -> None:
    """TTL=256（Q-L08-02）：created+ttl ≤ now 即过期，EXPIRED 落账（禁静默丢弃）。"""
    ledger = CandidateLedger(ttl_cycles=256, max_per_batch=8)
    kept = ledger.submit_batch((_candidate("a", 0.5),), 0)
    assert len(kept) == 1
    assert ledger.expire(255) == ()           # 驻留窗内存活
    assert ledger.expire(256) == ("a",)       # created 0 + ttl 256 ≤ 256 → 过期
    assert ledger.active == ()
    log = ledger.logs[-1]
    assert log.rejection_code is RejectionCode.EXPIRED and log.decision is GoalDecision.REJECT
    with pytest.raises(KeyError):
        ledger.consume("a")                    # 过期候选不可再采纳


def test_capacity_truncation_removes_lowest_urgency_first() -> None:
    """cap=2：urgency 0.9/0.5/0.1 → 0.1 被移除（CAPACITY 落账），保留高 urgency。"""
    ledger = CandidateLedger(ttl_cycles=256, max_per_batch=2)
    kept = ledger.submit_batch(
        (_candidate("hi", 0.9), _candidate("mid", 0.5, MotiveSource.VIABILITY), _candidate("lo", 0.1, MotiveSource.REQUEST)),
        0,
    )
    assert [c.candidate_id for c in kept] == ["mid", "hi"]     # 移除序尾部 = 存活（urgency 升序）
    dropped_log = ledger.logs[-1]
    assert dropped_log.candidate_id == "lo"
    assert dropped_log.rejection_code is RejectionCode.CAPACITY
    assert ledger.consume("hi").candidate_id == "hi"


def test_capacity_tie_removes_smaller_candidate_id_first() -> None:
    """tie（同 urgency）：candidate_id 升序先移除——cap=1、同 urgency 0.5 的 a/b → 保留 b。"""
    ledger = CandidateLedger(ttl_cycles=256, max_per_batch=1)
    kept = ledger.submit_batch((_candidate("a", 0.5), _candidate("b", 0.5, MotiveSource.VIABILITY)), 0)
    assert [c.candidate_id for c in kept] == ["b"]             # 升序先移除 = 小 id 先出
    assert ledger.logs[-1].candidate_id == "a"


def test_per_source_single_candidate_per_batch() -> None:
    """每 source_kind 每批次 ≤1（Q-L08-02 上界 = 枚举基数的构造侧保证）。"""
    ledger = CandidateLedger(ttl_cycles=256, max_per_batch=8)
    with pytest.raises(CandidateBatchOverflow, match="每源每批次"):
        ledger.submit_batch((_candidate("a", 0.5), _candidate("b", 0.4)), 0)


def test_batch_cycle_mismatch_rejected() -> None:
    ledger = CandidateLedger(ttl_cycles=256, max_per_batch=8)
    with pytest.raises(CandidateBatchOverflow, match="batch_cycle"):
        ledger.submit_batch((_candidate("a", 0.5),), 7)   # 候选 created_cycle=0 ≠ 7
