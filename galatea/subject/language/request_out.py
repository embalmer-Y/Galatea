"""ExternalRequest 类型合同（L12 §2.2 request_out.py——语言请求唯一落点）。

纪律：`is_request_only` 标记不可去除（L12 §8 不变量；L08 C-5 硬检依赖）——
构造即冻结为 True，任何"顺带改成可执行指令"的路径在 schema 级被封死；
目的地只有 L08 动机源，禁直写 OwnedGoal（HLD §6.2 LLM→goal 禁写路径的入口闸）。
F0 范围 = schema 合同；C4 范围 = R-PARSE 分型 → 本类型的构造面（from_typed_fields）
+ instruction 五原语子集校验（Q-L03-06+Q-L04-05 成组⑤：外部请求不扩展能力）。
"""
from dataclasses import dataclass, field

from galatea.kernel.packet import ArtifactRef
from galatea.subject.c4profile import C4ActionSocialParams
from galatea.subject.language.ports import TypedFields


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


def from_typed_fields(
    parsed: TypedFields, requester: str, phrasing: str, content_digest: str
) -> ExternalRequest:
    """R-PARSE 分型（request/instruction）→ 语言侧请求（statement/question 不走此面）。

    typed_fields 携带 (kind, confidence) 对留证；目的地只有 L08 动机源（C-5 检查
    在 goals.checklist 承载——本类型不携带任何执行面字段）。
    """
    if parsed.kind not in ("request", "instruction"):
        raise ValueError(
            f"from_typed_fields requires request|instruction, got {parsed.kind!r}"
            "（statement/question 各走既有路由，Q-L12-06③）"
        )
    return ExternalRequest(
        content_ref=ArtifactRef(digest=content_digest, kind="parsed_request"),
        requester=requester,
        phrasing=phrasing,
        typed_fields=((parsed.kind, f"{parsed.confidence:.6f}"),),
    )


def validate_instruction_primitives(
    requested_primitives: tuple[str, ...], profile: C4ActionSocialParams
) -> None:
    """语言 instruction 的动作面映射 = 五原语子集校验（越界即拒——外部请求不扩展能力）。"""
    legal = set(profile.capability_action_class)
    illegal = [p for p in requested_primitives if p not in legal]
    if illegal:
        raise ValueError(
            f"instruction requests out-of-capability primitives {illegal}"
            "（外部请求不扩展能力，Q-L03-06+Q-L04-05 成组⑤）"
        )
