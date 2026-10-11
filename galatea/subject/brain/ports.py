"""P4-α 脑核 typed 合同面（L04 §10 brain/ports.py；Q-L13-20①② / Q-T02①）。

- TrainingSessionRecord：学习会话录制格式 v1 十字段物化（profile
  training.session_record_schema = training_session.v1；字段集与
  p4profile.RECORD_FIELDS_V1 逐项一致，构造期机械强制）。
- GaussianPosterior：对角高斯潜后验（摊销推断输出；采样自由操作化——
  给定权重确定性 Q-G00-14①，计算路径只取均值点估计）。
- 录制重放判据（Q-L13-20①）：同录制种子 + 同数据 digest → 末权重逐位恒等。
"""
from dataclasses import dataclass

from galatea.subject.p4profile import RECORD_FIELDS_V1


class TrainingSessionViolation(ValueError):
    """训练会话录制与 schema v1 合同不符——fail closed。"""


@dataclass(frozen=True, slots=True)
class TrainingSessionRecord:
    """学习会话录制（Q-L13-20①；十缺一即拒）。

    master_seed 驱动世界流（数据身份），init_seed 驱动权重初始化——两 seed
    分立（探针同构）；data_digest = 训练数据身份锚（流/语料 sha256）；
    weights_digest_* = state_dict 规范化聚合 digest（逐键 sha256 的 sha256）。
    """

    master_seed_hex: str
    init_seed: int
    data_digest: str
    weights_digest_before: str
    weights_digest_after: str
    loss_first: float
    loss_last: float
    optimizer: str
    lr: float
    epochs: int

    def __post_init__(self) -> None:
        missing = [
            field for field in ("master_seed_hex", "init_seed", "data_digest",
                                "weights_digest_before", "weights_digest_after",
                                "loss_first", "loss_last", "optimizer", "lr", "epochs")
            if getattr(self, field) is None
        ]
        if missing:
            raise TrainingSessionViolation(
                f"training_session.v1 fields missing: {missing}（Q-L13-20① 十缺一即拒）")
        if not self.master_seed_hex or len(self.master_seed_hex) % 2 != 0 \
                or set(self.master_seed_hex) > set("0123456789abcdef"):
            raise TrainingSessionViolation(
                "master_seed_hex must be a nonzero even-length hex seed"
                "（Q-L13-12 同族：任意短语 hex，先于结果钉死——探针 28 位即合法）")
        for digest_name in ("data_digest", "weights_digest_before", "weights_digest_after"):
            digest = getattr(self, digest_name)
            if len(digest) != 64 or digest == "0" * 64:
                raise TrainingSessionViolation(
                    f"{digest_name} must be sha256 hex（数据/权重身份锚 Q-L13-20①）")
        if self.loss_last > self.loss_first:
            raise TrainingSessionViolation(
                f"loss must not increase across session: {self.loss_first} -> {self.loss_last}"
                "（训练损失必须下降——学习发生，ADR-G-0030 §2 判据）")


@dataclass(frozen=True, slots=True)
class GaussianPosterior:
    """对角高斯潜后验（摊销推断输出）。"""

    mean: tuple[float, ...]
    logvar: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.mean) != len(self.logvar):
            raise TrainingSessionViolation(
                f"posterior mean/logvar dim mismatch: {len(self.mean)} vs {len(self.logvar)}")


def record_field_names() -> tuple[str, ...]:
    """录制格式 v1 字段序（schema 身份；与 profile training.record_fields 同源）。"""
    return RECORD_FIELDS_V1
