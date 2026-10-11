"""训练会话录制器测试（Q-L13-20①：schema v1 十字段 + 重放逐位恒等）。"""
import pytest
import torch

from galatea.subject.brain.error_stream import INPUT_DIM
from galatea.subject.brain.module import configure_deterministic_torch
from galatea.subject.brain.ports import TrainingSessionViolation, record_field_names
from galatea.subject.brain.recorder import (
    record_training_session,
    replay_training_session,
)
from galatea.subject.brain.world_model import RSSMWorldModel
from galatea.subject.p4profile import load_p4_alpha_profile

_PARAMS = load_p4_alpha_profile()
_MASTER = b"test-brain-session"


def _sequence(n: int) -> list[torch.Tensor]:
    generator = torch.Generator().manual_seed(7)
    return [torch.randn(INPUT_DIM, generator=generator) * 0.1 for _ in range(n)]


def _build(init_seed: int) -> RSSMWorldModel:
    return RSSMWorldModel(_PARAMS, parent_digest="root", init_seed=init_seed)


def test_record_field_names_match_profile_schema() -> None:
    """录制字段序 = profile training.record_fields（schema v1 身份一致）。"""
    assert record_field_names() == _PARAMS.record_fields


def test_record_and_replay_bit_exact() -> None:
    """录制 → 重放：同种子同数据 → 末权重逐位恒等（宪法语义核心判据）。"""
    xs = _sequence(20)
    data_digest = "a" * 64
    module = _build(11)
    before = module.digest()
    losses = module.train_on_sequence(xs, lr=_PARAMS.lr, epochs=20)
    record = record_training_session(_MASTER, 11, data_digest, module, before, losses,
                                     _PARAMS, epochs=20)
    assert record.master_seed_hex == _MASTER.hex()
    assert record.weights_digest_before == before
    assert record.weights_digest_after == module.digest()
    assert record.optimizer == "adam" and record.epochs == 20
    assert record.loss_last < record.loss_first
    assert replay_training_session(
        record,
        rebuild=lambda: _build(11),
        retrain=lambda m: m.train_on_sequence(xs, lr=_PARAMS.lr, epochs=20),
    ) is True


def test_replay_detects_data_drift() -> None:
    """重放数据漂移 → 末权重失配 → False（录制判据可失败——反空转）。"""
    xs = _sequence(20)
    module = _build(11)
    before = module.digest()
    losses = module.train_on_sequence(xs, lr=_PARAMS.lr, epochs=20)
    record = record_training_session(_MASTER, 11, "a" * 64, module, before, losses, _PARAMS)
    drifted = [x * 2.0 for x in _sequence(20)]
    assert replay_training_session(
        record,
        rebuild=lambda: _build(11),
        retrain=lambda m: m.train_on_sequence(drifted, lr=_PARAMS.lr, epochs=20),
    ) is False


def test_record_violations_fail_closed() -> None:
    """损失上升/种子格式非法 = 拒（schema 合同）。"""
    module = _build(11)
    with pytest.raises(TrainingSessionViolation, match="loss must not increase"):
        record_training_session(_MASTER, 11, "a" * 64, module, module.digest(),
                                [0.5, 0.6], _PARAMS)
    configure_deterministic_torch()
    with pytest.raises(TrainingSessionViolation):
        from galatea.subject.brain.ports import TrainingSessionRecord

        TrainingSessionRecord(
            master_seed_hex="short", init_seed=1, data_digest="a" * 64,
            weights_digest_before="b" * 64, weights_digest_after="c" * 64,
            loss_first=0.5, loss_last=0.4, optimizer="adam", lr=0.01, epochs=1)
