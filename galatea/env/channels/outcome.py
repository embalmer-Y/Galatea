"""结果通道（L01 §2/§10 outcome.py）：动作的世界后果回传（形成后结果的前身）。

纪律：
- 渲染素材 = EffectFact 的 effective 描述（requested≠effective 已在世界侧显形）；
- **egocentric 化（ADR-G-0005 R3 处置）**：位移坐标不出主体边界——effect 描述中的
  绝对格坐标（`_to_X_Y`）替换为 `_arrived`，与 proprio"位置不直接下发"（Q-L01-09⑥
  简化的对应面）一致；世界侧 EffectFact 保留全量坐标（EVIDENCE_ONLY）；
- 投递经通道延迟——主体拿到的是 RECEIVED 结果，非 ExecutionFact 真值。
"""
import json
import re

from galatea.env.channels.adapter import ChannelBus, ChannelKind
from galatea.kernel.packet import ArtifactRef

_COORDINATE = re.compile(r"_to_\d+_\d+")


def egocentric_effect(effect: str) -> str:
    """清洗绝对坐标（outcome 主体侧口径；SC1 探针同模式）。"""
    return _COORDINATE.sub("_arrived", effect)


class OutcomeChannel:
    def __init__(self, bus: ChannelBus) -> None:
        self._bus = bus

    def render_and_submit(self, cycle: int, truth_ref: ArtifactRef, command_id: str, effect: str) -> ArtifactRef:
        signal = {
            "kind": "action_outcome",
            "command_id": command_id,
            "effect": egocentric_effect(effect),
        }
        return self._bus.submit(
            ChannelKind.OUTCOME,
            json.dumps(signal, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            truth_ref,
            cycle,
        )
