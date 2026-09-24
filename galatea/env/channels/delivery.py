"""通道投递事实与缺失信号（L01 §2.1/§4.2——投递 ≠ 接收 的 schema 承载）。

纪律：DeliveryFact 与 Signal 分离——投递事实只入证据侧；主体只拿 RECEIVED 包；
缺失/损坏不静默补零，产生 MissingSignalEvent 随包 provenance 下发（L01 §8）。
"""
from dataclasses import dataclass, field

from galatea.kernel.packet import AccessScope, ArtifactRef
from galatea.kernel.unknown import Unknown, UnknownReason

EVIDENCE_ONLY_PLANE: AccessScope = AccessScope.EVIDENCE_ONLY


@dataclass(frozen=True, slots=True)
class ChannelDeliveryFact:
    """投递事实（L01 §2.1：sent_truth_ref/delivered/delay/corruption/channel_version）。"""

    sent_truth_ref: ArtifactRef
    delivered: bool
    delay_cycles: int
    corrupted: bool
    channel_version: str
    access_scope: AccessScope = field(default=EVIDENCE_ONLY_PLANE, init=False)  # 平面恒定（REV-0003 R4）


@dataclass(frozen=True, slots=True)
class MissingSignalEvent:
    """缺失信号事件（L01 §4.2：typed unknown=MISSING_SIGNAL，由 L02 决定形成策略）。"""

    channel_version: str
    expected_truth_ref: ArtifactRef
    unknown: Unknown  # reason 恒为 MISSING_SIGNAL（构造时校验）

    def __post_init__(self) -> None:
        if self.unknown.reason is not UnknownReason.MISSING_SIGNAL:
            raise ValueError("MissingSignalEvent requires Unknown(MISSING_SIGNAL)")
