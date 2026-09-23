"""payload 引用与 schema 版本注册接口（L00 §2.1/§2.3）。

纪律：内核只见 payload_ref（digest 寻址），不见 payload 语义；payload 本体
存 registry，由目标模块自行取回（调度器 payload 不可见性的另一半）。
Q-T03：payload schema 校验属 Pydantic v2 层——本模块只提供注册表接口，
具体 payload 模型在 L01+ 各平面模块注册，内核不引入第三方依赖。
"""
from collections.abc import Callable
from dataclasses import dataclass

from galatea.kernel.packet import ArtifactRef


@dataclass(frozen=True, slots=True)
class PayloadRef(ArtifactRef):
    """payload 专用引用（语义别名：kind 恒为注册的 content_type）。"""


class SchemaViolation(ValueError):
    """payload schema 违规（L00 §6.2：拒绝投递，reason=SCHEMA）。"""


class PayloadSchemaRegistry:
    """content_type → (schema_version, validator) 注册表。

    validator: (payload_bytes) -> None，校验失败抛 SchemaViolation。
    同名 content_type 重复注册拒绝（版本演进 = 新 content_type 名或显式覆盖登记）。
    """

    def __init__(self) -> None:
        self._schemas: dict[str, tuple[str, Callable[[bytes], None]]] = {}

    def register(
        self, content_type: str, schema_version: str, validator: Callable[[bytes], None]
    ) -> None:
        if not content_type or not schema_version:
            raise SchemaViolation("content_type/schema_version must be non-empty")
        if content_type in self._schemas:
            raise SchemaViolation(f"content_type already registered: {content_type!r}")
        self._schemas[content_type] = (schema_version, validator)

    def resolve(self, content_type: str) -> tuple[str, Callable[[bytes], None]]:
        try:
            return self._schemas[content_type]
        except KeyError:
            raise SchemaViolation(f"unregistered content_type: {content_type!r}") from None

    def validate(self, content_type: str, declared_version: str, payload: bytes) -> None:
        version, validator = self.resolve(content_type)
        if version != declared_version:
            raise SchemaViolation(
                f"schema version mismatch for {content_type!r}: "
                f"declared {declared_version!r}, registered {version!r}"
            )
        validator(payload)

    def registered(self) -> tuple[str, ...]:
        return tuple(sorted(self._schemas))
