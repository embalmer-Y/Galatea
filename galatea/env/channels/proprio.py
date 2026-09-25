"""本体感受通道（L01 §2/§10 proprio.py）：姿态/朝向观测（M0 最小集）。

M0 语义（Q-L01-09⑥ 简化留痕的对应面）：位置不直接下发（主体由观测窗中心性
隐式获得），朝向经本通道 RECEIVED；load ≡ 0 无信号。
"""
import json

from galatea.env.channels.adapter import ChannelBus, ChannelKind
from galatea.env.world.mw0 import MW0World
from galatea.kernel.packet import ArtifactRef


class ProprioceptiveChannel:
    def __init__(self, bus: ChannelBus, world: MW0World) -> None:
        self._bus = bus
        self._world = world

    def render_and_submit(self, cycle: int, truth_ref: ArtifactRef) -> ArtifactRef:
        signal = {
            "kind": "proprioceptive_state",
            "orientation": self._world.orientation(),
        }
        return self._bus.submit(
            ChannelKind.PROPRIOCEPTIVE,
            json.dumps(signal, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            truth_ref,
            cycle,
        )
