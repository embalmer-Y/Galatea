"""训练会话录制器（Q-L13-20①②；ADR-G-0030 §5 P4-α 实现期范围）。

- record/replay：学习会话录制（training_session.v1 十字段）+ 重放判据
  （同录制种子 + 同数据 → 末权重逐位恒等 + 损失曲线末位恒等——给定权重
  确定性 Q-G00-14① 的训练面机械判据）。
- 探针报告生成器在**证据面 runner**（galatea/evidence/control/probe_report.py）
  ——REV-0027 R5"并入 P4-α 实现 runner"的落位：生成器需 env 真实流（W/O
  隔离守卫禁主体平面 import env，tests/env/test_leakage_env.py 机械强制），
  故流采集 + 报告产出归证据面；本模块提供其消费的 record/replay 面。

录制的部署面（Q-L13-20②）：权重 = registry 工件（weights.py）；录制记录本身
入 EvidenceResult data_refs / manifest 锚（评价侧承载——本模块不 import
证据平面，P04 平面分离保持）。
"""
from __future__ import annotations

from collections.abc import Callable

from galatea.subject.brain.module import NeuralModule, configure_deterministic_torch
from galatea.subject.brain.ports import TrainingSessionRecord
from galatea.subject.p4profile import P4AlphaBrainParams


def record_training_session(master_seed: bytes, init_seed: int, data_digest: str,
                            module: NeuralModule, weights_digest_before: str,
                            losses: list[float], params: P4AlphaBrainParams,
                            epochs: int | None = None) -> TrainingSessionRecord:
    """训练后录制（字段 = schema v1 十项；损失必须下降——学习发生判据）。

    epochs = 实际训练轮数（缺省 = profile 冻结值；录制反映真实会话）。
    """
    if len(losses) < 2:
        raise ValueError("session requires >= 2 loss points")
    return TrainingSessionRecord(
        master_seed_hex=master_seed.hex(),
        init_seed=init_seed,
        data_digest=data_digest,
        weights_digest_before=weights_digest_before,
        weights_digest_after=module.digest(),
        loss_first=losses[0],
        loss_last=losses[-1],
        optimizer=params.optimizer,
        lr=params.lr,
        epochs=params.epochs if epochs is None else epochs,
    )


def replay_training_session(record: TrainingSessionRecord,
                            rebuild: Callable[[], NeuralModule],
                            retrain: Callable[[NeuralModule], list[float]]) -> bool:
    """重放判据（Q-L13-20①）：同种子重建初始化 → 同数据重训 → 末权重逐位恒等。

    rebuild = 从录制 init_seed 重建初始化模块（调用方闭包承载同数据 digest 的
    训练集）；retrain = 全批量重训并返回损失。逐位恒等含损失曲线末位。
    """
    configure_deterministic_torch()
    replayed = rebuild()
    if replayed.digest() != record.weights_digest_before:
        return False
    replay_losses = retrain(replayed)
    return (replayed.digest() == record.weights_digest_after
            and replay_losses[-1] == record.loss_last)
