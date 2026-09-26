"""ExternalRequest 接收（L08 §2.1 goal.motive_request / §10 request.py）。

纪律：is_request_only 恒 True 且构造不可指定（init=False，同 L12 request_out.py
先例）——外部请求**只能成为候选**（C-5 检查的输入侧前提，HLD §6.2 禁直写 OwnedGoal）；
措辞/请求者字段留证（Q-L08-06：4 措辞 × 2 请求者，语义恒定由 M1 统计计划冻结文本承载）。
"""
import enum
from dataclasses import dataclass, field

__all__ = ["RequesterIdentity", "RequestPhrasing", "ExternalRequest"]


class RequesterIdentity(enum.StrEnum):
    """请求者身份二型（Q-L08-06 CONFIRMED 2026-09-26：人类研究者/实验控制代理）。"""

    HUMAN_RESEARCHER = "HUMAN_RESEARCHER"
    EXPERIMENT_CONTROL_PROXY = "EXPERIMENT_CONTROL_PROXY"


class RequestPhrasing(enum.StrEnum):
    """措辞四型（Q-L08-06：中性/礼貌/命令/恳求；语义恒定，仅 phrasing 变）。"""

    NEUTRAL = "NEUTRAL"
    POLITE = "POLITE"
    COMMAND = "COMMAND"
    PLEADING = "PLEADING"


@dataclass(frozen=True, slots=True)
class ExternalRequest:
    """外部请求（EXTERNAL_STATEMENT 层级，经 L01 language 通道 typed 注入）。"""

    content_ref: str
    requester: RequesterIdentity
    phrasing: RequestPhrasing
    phrasing_text: str                 # 措辞文本留证（统计计划冻结文本的运行时实例）
    received_refs: tuple[str, ...]     # RECEIVED 事件 id（language 通道投递留痕）
    is_request_only: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        if self.is_request_only is not True:
            raise ValueError("ExternalRequest.is_request_only is immutable True（L08 §2.1）")
        if not self.content_ref or not self.phrasing_text:
            raise ValueError("ExternalRequest requires content_ref and phrasing_text")
        if not self.received_refs:
            raise ValueError("ExternalRequest requires received_refs（语言通道投递留证）")
