"""五类声明通道合同（L01 §2——通道外无边界）与接收侧 payload schema。

F0 范围 = schema 合同：通道名/content_type 常量 + ReceivedSignalPayload
（Q-T03：payload = Pydantic v2）+ 统一注册入口；render→transport 行为归 M0。
ReceivedSignalPacket 本体 = L00 CognitivePacket（representation_level=RECEIVED），
其 payload schema 在此登记——"接收"与"真值"（galatea.env.world.truth）分属不同类型。
"""
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from galatea.kernel.packet import ArtifactRef
from galatea.kernel.payload import PayloadSchemaRegistry


class ChannelKind(StrEnum):
    """五类声明通道（L01 §2.2：通道外无边界，禁第六类）。"""

    EXTEROCEPTIVE = "exteroceptive"
    INTEROCEPTIVE = "interoceptive"
    PROPRIOCEPTIVE = "proprioceptive"
    OUTCOME = "outcome"
    LANGUAGE = "language"


CHANNEL_CONTENT_TYPES: dict[ChannelKind, str] = {
    kind: f"channel.{kind.value}.received.v1" for kind in ChannelKind
}


class ReceivedSignalPayload(BaseModel):
    """RECEIVED 包的 payload（Q-T03 Pydantic v2；frozen）。

    不含真值坐标/精确量（防 oracle 泄漏，L01 §4.2）；缺失经 missing + signal_ref
    缺省表达，不补零。
    """

    model_config = ConfigDict(frozen=True)

    modality: str
    channel_version: str
    signal_ref: ArtifactRef | None
    missing: bool = False


def register_channel_payload_schemas(registry: PayloadSchemaRegistry) -> None:
    """把五通道 payload schema 登记进内核 schema 注册表（幂等：重复注册拒绝）。"""
    for kind, content_type in CHANNEL_CONTENT_TYPES.items():
        registry.register(
            content_type,
            "v1",
            _validator_for(kind),
        )


def _validator_for(kind: ChannelKind) -> "object":
    """返回该校验 payload 字节的 callable（经 Registered payload schema 校验）。"""

    def validate(payload: bytes) -> None:
        ReceivedSignalPayload.model_validate_json(payload)

    validate.__name__ = f"validate_{kind.value}_received"
    return validate
