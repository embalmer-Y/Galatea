"""表示层级篡改检出（L02 §6/§10 test_level_escalation.py；S0 面）。"""
import dataclasses
from pathlib import Path

import pytest

from galatea.kernel.packet import RepresentationLevel
from galatea.subject.sensorium.calibration import bind_calibration
from galatea.subject.sensorium.pipeline import SensoriumPipeline, audit
from galatea.subject.sensorium.ports import (
    ExtLocalObsFeatures,
    QualityMetrics,
    RepresentationEscalation,
    SensoryFrame,
    SensoryModality,
    load_c0_sensorium_profile,
)
from galatea.subject.sensorium.receipt import build_receipt
from galatea.subject.sensorium.gain import apply_gain
from galatea.subject.sensorium.tests.conftest import extero_packet

_ROOT = Path(__file__).resolve().parents[4]
_PROFILE_PATH = _ROOT / "config" / "profiles" / "c0_sensorium.profile.yaml"


def _pipeline() -> SensoriumPipeline:
    from galatea.subject.sensorium.tests.conftest import time_basis

    profile = load_c0_sensorium_profile(_PROFILE_PATH)
    return SensoriumPipeline(
        profile, bind_calibration(_PROFILE_PATH, profile.calibration_version), time_basis()
    )


def test_frame_level_escalation_rejected_at_construction() -> None:
    """构造期层级提升即拒（representation_level 恒 SENSORY_FORMED）。"""
    with pytest.raises(RepresentationEscalation):
        SensoryFrame(
            frame_id="sf.bad", modality=SensoryModality.EXT_LOCAL_OBS,
            source_received_ids=("evt",), effective_time=0, formed_time=0,
            alignment_offset=0, alignment_confidence=1.0, calibration_version="c0-static-v1",
            features=ExtLocalObsFeatures(window=((0.0,) * 5,) * 5),
            quality=QualityMetrics(completeness=1.0, corruption_flags=()),
            gain=apply_gain("sf.bad", None)[0],
            representation_level=RepresentationLevel.PERCEIVED,   # 提升 → S0
        )


def test_frame_frozen_mutation_blocked() -> None:
    from galatea.subject.sensorium.tests.conftest import run_full_stream

    outputs = run_full_stream(_pipeline(), 5)
    frame = next(f for o in outputs for f in o.frames)
    with pytest.raises(dataclasses.FrozenInstanceError):
        frame.representation_level = RepresentationLevel.PERCEIVED   # type: ignore[misc]


def test_frame_rewrite_detected_at_construction() -> None:
    """帧改写检出（S0 面）：dataclasses.replace 复制陈旧 digest → 构造期即拒。

    ports.__post_init__ 强制重算 digest 并核验——"内容与声明 digest 不符"的帧
    不可能存在于类型系统（REV 首轮发现 replace 携带陈旧 digest 的缺陷，本测试钉死修复）。
    """
    from galatea.subject.sensorium.tests.conftest import run_full_stream

    outputs = run_full_stream(_pipeline(), 5)
    frame = next(f for o in outputs for f in o.frames)
    with pytest.raises(RepresentationEscalation, match="content_digest mismatch"):
        dataclasses.replace(
            frame, quality=QualityMetrics(completeness=0.5, corruption_flags=("tampered",))
        )


def test_receipt_forgery_detected_by_audit() -> None:
    """回执伪造检出：receipt.frame_digest 与帧不符 → audit 检出。"""
    from galatea.subject.sensorium.tests.conftest import run_full_stream

    outputs = run_full_stream(_pipeline(), 5)
    frame = next(f for o in outputs for f in o.frames)
    receipt = next(r for o in outputs for r in o.formation_receipts if r.frame_id == frame.frame_id)
    forged = object.__setattr__(receipt, "frame_digest", "f" * 64) or receipt
    with pytest.raises(AssertionError, match="digest mismatch"):
        audit((frame,), (forged,), (next(g for o in outputs for g in o.gain_receipts),))
