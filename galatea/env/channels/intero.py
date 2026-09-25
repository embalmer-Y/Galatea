"""内感受通道（L01 §2/§10 intero.py）：能量/完整度水平 + 离散原始事件。

L01 §4.4：内感受原始事件（energy 变化率、integrity 损伤事件、load、恢复）经本通道
形成 InteroceptiveSensation——不是 telemetry 直填；M0 渲染 = 水平 + 事件种类清单。
"""
import json

from galatea.env.channels.adapter import ChannelBus, ChannelKind
from galatea.env.world.mw0 import MW0World
from galatea.env.world.truth import WorldEvent
from galatea.kernel.packet import ArtifactRef


class InteroceptiveChannel:
    def __init__(self, bus: ChannelBus, world: MW0World) -> None:
        self._bus = bus
        self._world = world

    def render_and_submit(self, cycle: int, truth_ref: ArtifactRef, events: tuple[WorldEvent, ...]) -> ArtifactRef:
        signal = {
            "kind": "interoceptive_state",
            "energy": round(self._world.energy_fraction(), 6),
            "integrity": round(self._world.integrity_fraction(), 6),
            "events": sorted(e.kind for e in events),
        }
        return self._bus.submit(
            ChannelKind.INTEROCEPTIVE,
            json.dumps(signal, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            truth_ref,
            cycle,
        )
