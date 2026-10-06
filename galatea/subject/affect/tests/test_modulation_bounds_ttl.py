"""调制有界性、TTL 与裁剪（L05 §7 modulation bounds/TTL；Q-L02-02）。"""
import pytest

from galatea.subject.affect.modulation import (
    BELIEVE_THRESHOLD_BOUND,
    FACTOR_BOUND,
    MODULATION_TTL_CYCLES,
    ModulationField,
    ModulationLedger,
    ModulationStatus,
    ModulationTarget,
)
from galatea.subject.sensorium.gain import GAIN_BOUND, apply_gain_c2, scale_intensity
from galatea.subject.perception.modulation import apply_modulation


def _field(**kw: object) -> ModulationField:
    base = dict(
        modulation_id="m.1", target=ModulationTarget.SENSORIUM, dimension="gain",
        requested_value=1.5, bound_ref="c2_affect.profile@v1.0/modulation",
        ttl_cycles=4, issued_at=0, reason=("a",),
    )
    base.update(kw)
    return ModulationField(**base)  # type: ignore[arg-type]


def test_factor_bound_enforced_at_construction() -> None:
    """越界 requested 构造即拒（发放面自约束——目标模块裁剪是第二道防线）。"""
    with pytest.raises(ValueError):
        _field(requested_value=2.5)
    with pytest.raises(ValueError):
        _field(requested_value=0.1)
    _field(requested_value=2.0)
    _field(requested_value=0.5)


def test_ttl_positive_and_receipt_expected() -> None:
    """TTL ≥ 1（禁永久调制）；receipt_expected 恒 True。"""
    with pytest.raises(ValueError):
        _field(ttl_cycles=0)
    with pytest.raises(ValueError):
        _field(receipt_expected=False)


def test_ledger_settle_semantics() -> None:
    """台账结算：CONFIRMED（有回执）/ PENDING / EXPIRED_UNCONFIRMED（= 未发生）。"""
    from galatea.subject.affect.modulation import ModulationReceiptRecord

    ledger = ModulationLedger()
    f1 = ledger.issue(_field(modulation_id="m.1"))
    f2 = ledger.issue(_field(modulation_id="m.2", target=ModulationTarget.PERCEPTION,
                             dimension="believe_threshold", requested_value=0.6))
    ledger.record_receipt(ModulationReceiptRecord(
        modulation_id="m.1", accepted=True, applied_value=1.5, bound_check="IN_BOUND",
        received_at=1,
    ))
    st = ledger.settle(cycle=MODULATION_TTL_CYCLES)
    assert st["m.1"] is ModulationStatus.CONFIRMED
    assert st["m.2"] is ModulationStatus.EXPIRED_UNCONFIRMED
    confirmed = ledger.confirmed_fields(cycle=MODULATION_TTL_CYCLES)
    assert [f.modulation_id for f in confirmed] == [f1.modulation_id]   # m.2 未发生
    with pytest.raises(ValueError):
        ledger.record_receipt(ModulationReceiptRecord(   # 未发放调制回执 = 违约
            modulation_id="m.3", accepted=True, applied_value=1.0, bound_check="IN_BOUND",
            received_at=2,
        ))
    del f2


def test_sensorium_gain_face_bounded_clip() -> None:
    """L02 接收面：requested 越界 clip [0.5,2.0] + bound_check=CLIPPED（Q-L02-02②）。"""
    state, receipt = apply_gain_c2("sf.X.0", 5.0)
    assert state.applied_factor == 2.0 and state.source == "MODULATION"
    assert receipt.bound_check == "CLIPPED"
    assert (receipt.requested_gain, receipt.applied_gain) == (5.0, 2.0)   # 成对呈现
    _, receipt_ok = apply_gain_c2("sf.X.0", 1.25)
    assert receipt_ok.bound_check == "IN_BOUND" and receipt_ok.applied_gain == 1.25
    assert GAIN_BOUND == FACTOR_BOUND                                     # 单一界源


def test_gain_feature_scaling_saturates() -> None:
    """特征缩放：×factor 后域 clip（0.9×2 → 1.0 饱和；0.4×0.5 → 0.2）。"""
    assert scale_intensity(0.9, 2.0) == 1.0
    assert scale_intensity(0.4, 0.5) == 0.2
    assert scale_intensity(0.3, 1.0) == 0.3


def test_perception_threshold_face_bounded() -> None:
    """L03 接收面：believe_threshold ∈ [0.4,0.6]；越界 clip + CLIPPED 标注。"""
    r = apply_modulation("believe_threshold", 0.6)
    assert r.accepted and r.applied_value == 0.6 and r.bound_check == "IN_BOUND"
    r_clip = apply_modulation("believe_threshold", 0.9)
    assert r_clip.accepted and r_clip.applied_value == BELIEVE_THRESHOLD_BOUND[1]
    assert r_clip.bound_check == "CLIPPED"
    r_bad = apply_modulation("believe_threshold", "high")
    assert r_bad.accepted is False
