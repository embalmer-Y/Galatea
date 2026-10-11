"""Galatea P4-α 预测脑脑核（HLD §15 预测脑 v2；Q-L04-12/Q-L13-20/Q-G00-15）。

范围 = 脑核三面（ADR-G-0030 §5）：
- NeuralModule 谱系（Q-T02①）+ RSSM 式潜状态世界模型（Q-L04-12①）；
- 摊销推断入口（观测史→潜后验单次前向）+ 统一误差流（Q-L02-06 特征空间唯一复用）；
- 权重工件面（Q-L13-20② registry 内容寻址）+ 训练会话录制器（Q-L13-20①，
  探针报告生成器并入——REV-0027 R5）。

确定性宪法（ADR-G-0029 §2）：给定权重的确定性——训练可复算（录制重放逐位
恒等），部署推理双跑 bit-exact；种子经 Generator 显式注入，禁全局 RNG。
"""
from galatea.subject.brain.error_stream import INPUT_DIM, build_stream_vector
from galatea.subject.brain.module import (
    NeuralModule,
    aggregate_digest,
    configure_deterministic_torch,
    per_key_digests,
)
from galatea.subject.brain.ports import GaussianPosterior, TrainingSessionRecord
from galatea.subject.brain.world_model import RSSMWorldModel

__all__ = [
    "INPUT_DIM",
    "GaussianPosterior",
    "NeuralModule",
    "RSSMWorldModel",
    "TrainingSessionRecord",
    "aggregate_digest",
    "build_stream_vector",
    "configure_deterministic_torch",
    "per_key_digests",
]
