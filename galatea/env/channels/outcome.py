"""结果通道（L01 §2/§10 outcome.py）：动作的世界后果回传（形成后结果的前身）。

纪律：渲染素材 = EffectFact 的 effective 描述（requested≠effective 已在世界侧
显形）；投递经通道延迟——主体拿到的是 RECEIVED 结果，非 ExecutionFact 真值。
"""
import json

from galatea.env.channels.adapter import ChannelBus, ChannelKind
from galatea.kernel.packet import ArtifactRef


class OutcomeChannel:
    def __init__(self, bus: ChannelBus) -> None:
        self._bus = bus

    def render_and_submit(self, cycle: int, truth_ref: ArtifactRef, command_id: str, effect: str) -> ArtifactRef:
        signal = {
            "kind": "action_outcome",
            "command_id": command_id,
            "effect": effect,
        }
        return self._bus.submit(
            ChannelKind.OUTCOME,
            json.dumps(signal, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            truth_ref,
            cycle,
        )
