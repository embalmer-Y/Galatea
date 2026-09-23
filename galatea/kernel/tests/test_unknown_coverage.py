"""typed unknown 全覆盖（L00 §6.1/§7；Q-L00-02 冻结清单 10 项）。"""
import pytest

from galatea.kernel.unknown import (
    NotTypedUnknown,
    Unknown,
    UnknownReason,
    UnknownsLog,
    ensure_typed_confidence,
)


def test_frozen_list_has_exactly_ten_reasons() -> None:
    reasons = {r.value for r in UnknownReason}
    assert len(reasons) == 10
    assert "STREAM_MISSING" in reasons
    assert "DECISION_PATH_UNRESOLVED" in reasons


def test_bare_values_rejected() -> None:
    for bad in (None, "", "unknown", "None", ["unknown"]):
        with pytest.raises(NotTypedUnknown):
            ensure_typed_confidence(bad, "f")  # type: ignore[arg-type]


def test_typed_values_accepted() -> None:
    assert ensure_typed_confidence(0.5, "f") == 0.5
    u = Unknown(reason=UnknownReason.OOD, evidence_refs=(), detail=None, detected_by="m", virtual_time=1)
    assert ensure_typed_confidence(u, "f") is u
    for bad in (float("nan"), float("inf"), 1.5, -0.1):
        with pytest.raises(NotTypedUnknown):
            ensure_typed_confidence(bad, "f")


def test_unknowns_log_append_only() -> None:
    log = UnknownsLog()
    u1 = Unknown(reason=UnknownReason.MISSING_SIGNAL, evidence_refs=("e1",), detail=None, detected_by="m", virtual_time=1)
    u2 = Unknown(reason=UnknownReason.STREAM_MISSING, evidence_refs=(), detail="x", detected_by="m", virtual_time=2)
    assert log.add(u1) == 1
    snap = log.snapshot()
    assert log.add(u2) == 2
    assert len(snap) == 1  # 既有快照不受追加影响
    assert len(log.snapshot()) == 2
    assert log.count(UnknownReason.MISSING_SIGNAL) == 1
    assert log.count(UnknownReason.STREAM_MISSING) == 1
    assert log.count(UnknownReason.OOD) == 0
