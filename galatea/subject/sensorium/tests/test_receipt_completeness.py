"""FormationReceipt 完整性（L02 §7 contract/§10 test_receipt_completeness.py）。"""
from pathlib import Path

import pytest

from galatea.subject.sensorium.calibration import bind_calibration
from galatea.subject.sensorium.pipeline import SensoriumPipeline
from galatea.subject.sensorium.ports import load_c0_sensorium_profile
from galatea.subject.sensorium.receipt import ReceiptIncomplete, build_receipt
from galatea.subject.sensorium.tests.conftest import extero_packet, intero_packet, proprio_packet

_ROOT = Path(__file__).resolve().parents[4]
_PROFILE_PATH = _ROOT / "config" / "profiles" / "c0_sensorium.profile.yaml"


def _pipeline() -> SensoriumPipeline:
    profile = load_c0_sensorium_profile(_PROFILE_PATH)
    return SensoriumPipeline(profile, bind_calibration(_PROFILE_PATH, profile.calibration_version))


def test_every_frame_has_complete_receipt() -> None:
    """逐帧回执：字段全量（frame/source/calibration/offset/quality/gain/unknowns）。"""
    from galatea.subject.sensorium.tests.conftest import run_full_stream

    pipeline = _pipeline()
    total = 0
    for out in run_full_stream(pipeline, 5):
        assert len(out.formation_receipts) == len(out.frames)
        total += len(out.frames)
        for receipt in out.formation_receipts:
            assert receipt.frame_id and receipt.frame_digest
            assert receipt.source_received_ids
            assert receipt.calibration_version == "c0-static-v1"
            assert receipt.quality is not None
            assert receipt.gain_applied == 1.0
            assert receipt.gain_receipt.frame_id == receipt.frame_id
    assert total > 0                                                # 非空断言（防空转）


def test_receipt_incomplete_rejected() -> None:
    from galatea.subject.sensorium.tests.conftest import run_full_stream

    outputs = run_full_stream(_pipeline(), 5)
    frame = next(f for o in outputs for f in o.frames)
    receipt = next(r for o in outputs for r in o.formation_receipts if r.frame_id == frame.frame_id)
    with pytest.raises(ReceiptIncomplete):
        object.__setattr__(receipt, "frame_id", "")    # 空字段 → 完整性拒
        receipt.__post_init__()


def test_receipt_binding_mismatch_rejected() -> None:
    from galatea.subject.sensorium.tests.conftest import run_full_stream

    outputs = run_full_stream(_pipeline(), 5)
    frame = next(f for o in outputs for f in o.frames)
    other_frame = [f for o in outputs for f in o.frames][-1]
    receipt = next(r for o in outputs for r in o.formation_receipts if r.frame_id == frame.frame_id)
    with pytest.raises(ReceiptIncomplete):
        object.__setattr__(receipt, "gain_receipt", receipt.gain_receipt.__class__(
            frame_id=other_frame.frame_id, requested_gain=1.0, applied_gain=1.0, bound_check="IDENTITY_C0",
        ))
        receipt.__post_init__()
