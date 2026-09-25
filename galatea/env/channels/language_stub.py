"""语言通道 stub（L01 §2/§10 language_stub.py；L12 typed 陈述入口）。

M0 合同：通道 stub 存在（f0_language_contract.profile.yaml），不启用任何 LLM 角色；
typed 陈述仅可由实验控制经本 stub 注入（EXTERNAL_STATEMENT 层级，永不提升）。
"""
import json

from galatea.env.channels.adapter import ChannelBus, ChannelKind
from galatea.kernel.packet import ArtifactRef


class LanguageStubChannel:
    def __init__(self, bus: ChannelBus) -> None:
        self._bus = bus

    def submit_typed_statement(self, cycle: int, truth_ref: ArtifactRef, *, text: str, requester: str) -> ArtifactRef:
        """实验控制注入点（M0 无 LLM 角色；请求只进动机源，L08 C-5 由主体侧执行）。"""
        signal = {
            "kind": "typed_statement",
            "text": text,
            "requester": requester,
            "level": "EXTERNAL_STATEMENT",
        }
        return self._bus.submit(
            ChannelKind.LANGUAGE,
            json.dumps(signal, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            truth_ref,
            cycle,
        )
