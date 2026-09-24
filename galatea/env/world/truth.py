"""WorldTruth 与效果模型（L01 §2/§4.1——真值平面 schema，EVIDENCE_ONLY）。

纪律：本模块对象对主体平面物理不可见（主体 import 即 CI 失败，L01 §3）；
requested ≠ effective 必须显形于 EffectFact（禁合并，L01 §8 不变量 2）。
F0 范围 = schema 合同；dynamics/mw0 行为实现归 M0（L01 §9）。
"""
import enum
from dataclasses import dataclass, field

from galatea.kernel.packet import AccessScope, ArtifactRef
from galatea.kernel.unknown import Unknown

EVIDENCE_ONLY_PLANE: AccessScope = AccessScope.EVIDENCE_ONLY


class EffectDomain(enum.StrEnum):
    """效果域（L10 §4.2：MW0 期恒 SIMULATED；PHYSICAL 仅 P1 且四类授权全齐）。"""

    NONE = "NONE"
    SIMULATED = "SIMULATED"
    DIGITAL = "DIGITAL"
    PHYSICAL = "PHYSICAL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class Patch:
    """16×16 资源 niche 的格位（L01 §4.1；几何/再生行为归 M0）。"""

    kind: str
    resource_level: int
    respawn_timer: int


@dataclass(frozen=True, slots=True)
class BodyTruth:
    """身体真值（L01 §4.1：pos/orientation/energy/integrity/load）。"""

    pos: tuple[int, int]
    orientation: str
    energy: float
    integrity: float
    load: float


@dataclass(frozen=True, slots=True)
class WorldEvent:
    """世界事件（资源涌现/风暴/威胁等）。"""

    kind: str
    pos: tuple[int, int]
    tick: int


@dataclass(frozen=True, slots=True)
class WorldState:
    """MW0 世界状态真值（L01 §4.1）。"""

    grid: tuple[tuple[Patch, ...], ...]
    body: BodyTruth
    events: tuple[WorldEvent, ...]


@dataclass(frozen=True, slots=True)
class WorldTruthEvent:
    """世界真值事件（L01 §2.1：EVIDENCE_ONLY，主体不可见）。"""

    tick: int
    world_state_digest: str
    state_ref: ArtifactRef
    causal_parents: tuple[str, ...]
    access_scope: AccessScope = field(default=EVIDENCE_ONLY_PLANE, init=False)  # 平面恒定（REV-0003 R4）


@dataclass(frozen=True, slots=True)
class EffectFact:
    """效果事实（L01 §4.1：requested 与 effective 分别记录——coercion/blocked 在此显形）。"""

    action_window: tuple[int, int]
    requested_effect: str
    effective_effect: str
    domain: EffectDomain
    effective_unknown: "Unknown | None" = None
    access_scope: AccessScope = field(default=EVIDENCE_ONLY_PLANE, init=False)  # 平面恒定（REV-0003 R4）
