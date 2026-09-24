"""ExternalRequest 类型合同（L12 §2.2 request_out.py——语言请求唯一落点）。

纪律：`is_request_only` 标记不可去除（L12 §8 不变量；L08 C-5 硬检依赖）——
构造即冻结为 True，任何"顺带改成可执行指令"的路径在 schema 级被封死；
目的地只有 L08 动机源，禁直写 OwnedGoal（HLD §6.2 LLM→goal 禁写路径的入口闸）。
F0 范围 = schema 合同；R-PARSE 行为归 C4。
"""
from dataclasses import dataclass, field

from galatea.kernel.packet import ArtifactRef


@dataclass(frozen=True, slots=True)
class ExternalRequest:
    """语言侧请求（is_request_only 恒 True 且不可变）。"""

    content_ref: ArtifactRef
    requester: str
    phrasing: str
    typed_fields: tuple[tuple[str, str], ...] = ()
    is_request_only: bool = field(default=True, init=False)  # init=False：构造参数无法关闭

    def __post_init__(self) -> None:
        if self.is_request_only is not True:
            raise ValueError("ExternalRequest.is_request_only is immutable True（L12 §2.2）")
        if not self.requester or not self.phrasing:
            raise ValueError("requester and phrasing are required")
