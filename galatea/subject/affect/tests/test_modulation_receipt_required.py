"""无回执调制 = 未发生（L05 §6 行 3 / §7 modulation_receipt_required）。"""
from galatea.subject.affect.modulation import (
    MODULATION_TTL_CYCLES,
    ModulationField,
    ModulationLedger,
    ModulationReceiptRecord,
    ModulationStatus,
    ModulationTarget,
)


def _f(mid: str) -> ModulationField:
    return ModulationField(
        modulation_id=mid, target=ModulationTarget.SENSORIUM, dimension="gain",
        requested_value=2.0, bound_ref="c2_affect.profile@v1.0/modulation",
        ttl_cycles=MODULATION_TTL_CYCLES, issued_at=10, reason=("a",),
    )


def test_unreceipted_never_confirmed() -> None:
    """TTL 内无回执 → EXPIRED_UNCONFIRMED，不进 confirmed 集（evaluator 不得采信）。"""
    ledger = ModulationLedger()
    ledger.issue(_f("m.a"))
    for cycle in range(10, 10 + MODULATION_TTL_CYCLES):
        st = ledger.settle(cycle)
        assert st["m.a"] is ModulationStatus.PENDING
        assert ledger.confirmed_fields(cycle) == ()
    st = ledger.settle(10 + MODULATION_TTL_CYCLES)
    assert st["m.a"] is ModulationStatus.EXPIRED_UNCONFIRMED
    assert ledger.confirmed_fields(10 + MODULATION_TTL_CYCLES) == ()


def test_late_receipt_after_expiry_still_uncounted() -> None:
    """过期后补回执不复活"未发生"结算（Q-L07-03③ 禁重试同源；回执仅审计留痕）。"""
    ledger = ModulationLedger()
    ledger.issue(_f("m.b"))
    ledger.record_receipt(ModulationReceiptRecord(
        modulation_id="m.b", accepted=True, applied_value=2.0,
        bound_check="IN_BOUND", received_at=10 + MODULATION_TTL_CYCLES + 5,
    ))
    st = ledger.settle(10 + MODULATION_TTL_CYCLES + 5)
    assert st["m.b"] is ModulationStatus.EXPIRED_UNCONFIRMED
    assert ledger.confirmed_fields(10 + MODULATION_TTL_CYCLES + 5) == ()


def test_duplicate_issue_rejected() -> None:
    """重复 modulation_id 即拒（确定性 id 纪律）。"""
    ledger = ModulationLedger()
    ledger.issue(_f("m.c"))
    try:
        ledger.issue(_f("m.c"))
        raise AssertionError("duplicate issue must raise")
    except ValueError:
        pass
