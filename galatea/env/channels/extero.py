"""外感受通道（L01 §2/§10 extero.py）：MW0 观测窗渲染（资源强度 5×5，含噪声）。

纪律：不含真值坐标/资源精确量（防 oracle 泄漏，L01 §4.2）；噪声来自
(env,mw0,render) 流（Q-L01-01）；损坏由总线在传输层字节级扰动（渲染器不感知）。
"""
import json

from galatea.env.channels.adapter import ChannelBus, ChannelKind
from galatea.env.world.mw0 import MW0World
from galatea.kernel.packet import ArtifactRef


class ExteroceptiveChannel:
    def __init__(self, bus: ChannelBus, world: MW0World) -> None:
        self._bus = bus
        self._world = world

    def render_and_submit(self, cycle: int, truth_ref: ArtifactRef) -> ArtifactRef:
        """渲染 5×5 观测窗（行优先，(dx,dy) ∈ [-2,2]）并投递。"""
        window = self._world.render_window(self._bus.render_stream)
        signal = {
            "kind": "observation_window",
            "window": [[window[(dx, dy)] for dx in range(-2, 3)] for dy in range(-2, 3)],
        }
        return self._bus.submit(
            ChannelKind.EXTEROCEPTIVE,
            json.dumps(signal, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            truth_ref,
            cycle,
        )
