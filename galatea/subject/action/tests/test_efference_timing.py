"""EfferenceCopy 时序纪律（L10 §10 test_efference_timing.py；L10 §4.3 原文）。

判据（L10 §7 efference timing C4 行）：副本同步产生；必早于或同 cycle 于效果到达；
预测必须是先行 PREDICTED 层（禁事后拟合）；移除 efference → forward 预测退化
（消融检出面随统计评价 runner 交付，本文件钉构造面时序）。
"""


import pytest

from galatea.subject.action.efference import (
    EfferenceCopy, EfferenceTimingViolation, issue_efference_copy,
)
from galatea.subject.action.gateway import ActionSpec
from galatea.subject.control.intention import ActionIntention
from galatea.subject.models.ports import ModelPrediction


def _command() -> object:
    from galatea.subject.action.signature import derive_signing_key
    from galatea.subject.action.gateway import CapabilityGateway, load_gateway_config
    from pathlib import Path

    root = Path(__file__).resolve().parents[4]
    gateway = CapabilityGateway(
        load_gateway_config(
            root / "config" / "profiles" / "m0_gateway.profile.yaml",
            root / "config" / "profiles" / "f0_action_contract.profile.yaml",
        ),
        derive_signing_key(b"efference-test"), run_id="R", branch_id="B",
        subject_candidate_id="S",
    )
    intention = ActionIntention(
        intention_id="i-eff", selected_proposal_id="t", arbitration_trace="t",
        deadline=32, budget_hint=None, idempotency_key="eff-1",
    )
    decision, command = gateway.authorize(
        intention, ActionSpec("move", "N"),
        subject_candidate_id="S", run_id="R", branch_id="B", virtual_time=4,
    )
    assert command is not None
    return command


def _prediction(valid_time: int = 6) -> ModelPrediction:
    return ModelPrediction(
        prediction_id="mp.EXT.6", target_modality="EXT_LOCAL_OBS",
        expected_window=((0.1,) * 5,) * 5, valid_time=valid_time,
    )


def test_efference_sync_issuance_and_timing_ok() -> None:
    command = _command()
    copy = issue_efference_copy(command, _prediction(valid_time=6), issued_cycle=4)
    assert isinstance(copy, EfferenceCopy)
    assert copy.motor_command_copy == command.command_id
    assert copy.requested_action == "move:N"
    assert copy.issued_cycle <= copy.valid_time          # 先行（同 cycle 或更早）


def test_efference_late_issuance_rejected() -> None:
    """副本晚于预测目标窗 = 事后拟合 → EfferenceTimingViolation。"""
    command = _command()
    with pytest.raises(EfferenceTimingViolation, match="先行"):
        issue_efference_copy(command, _prediction(valid_time=6), issued_cycle=8)


def test_efference_requires_predicted_level() -> None:
    """非 PREDICTED 层预测不可作 efference 载体（T1 先行语义）。"""
    command = _command()
    stale = _prediction()
    object.__setattr__(stale, "representation_level", "SENSORY_FORMED")   # 越过 init=False 面
    with pytest.raises(EfferenceTimingViolation, match="PREDICTED"):
        issue_efference_copy(command, stale, issued_cycle=4)


def test_efference_requires_prediction_ref() -> None:
    """禁无预测的副本（L10 §4.3 prediction_ref 合同）。"""
    with pytest.raises(ValueError, match="prediction_ref"):
        EfferenceCopy(
            motor_command_copy="c-1", requested_action="move:N",
            issued_cycle=4, prediction_ref="", valid_time=6,
        )
