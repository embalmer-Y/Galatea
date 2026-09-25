"""MW0 profile 加载与 digest 校验（L01 §10 profile.py）。

纪律：运行期禁改（L01 §3：profile 由 registry 只读加载）；缺键 fail closed
（WorldProfileViolation）；digest 入 checkpoint 谱系引用（profile_ref）。
数值全部来自冻结的 config/profiles/m0_mw0.profile.yaml（Q-G00-08/Q-L01-09）。
"""
import enum
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from galatea.kernel.digest import content_digest


class WorldProfileViolation(ValueError):
    """冻结 profile 与合同不符（缺键/类型错）——fail closed。"""


class RegimeName(enum.StrEnum):
    """三 regime（Q-L01-03 CONFIRMED）。"""

    ABUNDANCE = "abundance"
    SCARCITY = "scarcity"
    VOLATILE = "volatile"


@dataclass(frozen=True, slots=True)
class RegimeParams:
    """单 regime 参数（Q-L01-03 框架 + Q-G00-08 初值 + Q-L01-09 语义）。"""

    respawn_multiplier: float
    resource_density: float          # 目标覆盖率（Q-L01-09③）
    storm_rate_per_cycle: float      # 全局语义：每 grid 每 cycle 期望命中（Q-L01-09①）
    drift_period_cycles: int         # volatile 风暴带漂移周期（Q-L01-09②）
    cells_per_drift: int


@dataclass(frozen=True, slots=True)
class MW0Params:
    """MW0 世界参数的 typed 视图（全部溯源冻结 profile）。"""

    grid_size: int
    patch_types: tuple[str, ...]
    resource_max_level: int
    respawn_base_cycles: int
    energy_max: float
    integrity_max: float
    action_energy_delta: dict[str, float]
    forage_yield: int
    food_storage_max: int
    storm_damage_per_hit: float
    damage_event_min_delta: float
    observation_gain: dict[str, float]
    render_noise_sigma: float
    regimes: dict[str, RegimeParams]
    min_dwell_cycles: int
    initial_regime: str
    channel_delay_cycles: dict[str, int]
    channel_corruption_rate: float
    channel_loss_rate: float

    def regime(self, name: str) -> RegimeParams:
        try:
            return self.regimes[name]
        except KeyError:
            raise WorldProfileViolation(f"unknown regime: {name!r}") from None


@dataclass(frozen=True, slots=True)
class MW0Profile:
    """加载结果：typed 参数 + 内容 digest（谱系引用用）。"""

    params: MW0Params
    digest: str
    source: str

    def ref(self) -> str:
        return f"m0_mw0@{self.digest[:16]}"


def _need(mapping: dict[str, Any], key: str) -> Any:
    value = mapping.get(key)
    if value is None:
        raise WorldProfileViolation(f"profile key missing: {key}")
    return value


def load_profile(path: Path) -> MW0Profile:
    """加载并校验冻结 profile；不符即 WorldProfileViolation。"""
    raw_bytes = path.read_text(encoding="utf-8")
    doc = cast("dict[str, Any]", yaml.safe_load(raw_bytes))
    profile_doc = cast("dict[str, Any]", _need(doc, "profile"))
    world = cast("dict[str, Any]", _need(doc, "world"))
    observation = cast("dict[str, Any]", _need(doc, "observation"))
    regimes_doc = cast("dict[str, Any]", _need(doc, "regimes"))
    channels = cast("dict[str, Any]", _need(doc, "channels"))
    body = cast("dict[str, Any]", _need(world, "body"))
    resource = cast("dict[str, Any]", _need(world, "resource"))
    storm = cast("dict[str, Any]", _need(world, "storm"))
    forage = cast("dict[str, Any]", _need(world, "forage_chain"))
    floor_doc = cast("dict[str, Any]", _need(world, "floor_semantics"))
    action_delta_doc = cast("dict[str, Any]", _need(world, "action_energy_delta"))
    gain_doc = cast("dict[str, Any]", _need(observation, "gain_by_distance"))
    delay_doc = cast("dict[str, Any]", _need(channels, "delay_cycles"))
    if floor_doc.get("clamp_at_zero") != ["energy", "integrity"] or floor_doc.get("death_rebirth") != "none":
        raise WorldProfileViolation("floor_semantics deviate from frozen M0 contract（Q-L01-09⑤）")
    if float(_need(channels, "loss_rate")) != 0.0:
        raise WorldProfileViolation("loss_rate must be 0.0 in M0（Q-L01-09⑦）")
    regimes: dict[str, RegimeParams] = {}
    for name in ("abundance", "scarcity", "volatile"):
        entry = cast("dict[str, Any]", _need(regimes_doc, name))
        drift = cast("dict[str, Any] | None", entry.get("storm_band_drift"))
        drift_period, drift_cells = (64, 1) if name == RegimeName.VOLATILE.value else (0, 0)
        if isinstance(drift, dict):
            drift_period = int(drift.get("period_cycles", drift_period))
            drift_cells = int(drift.get("cells_per_drift", drift_cells))
        regimes[name] = RegimeParams(
            respawn_multiplier=float(_need(entry, "respawn_multiplier")),
            resource_density=float(_need(entry, "resource_density")),
            storm_rate_per_cycle=float(_need(entry, "storm_rate_per_cycle")),
            drift_period_cycles=drift_period,
            cells_per_drift=drift_cells,
        )
    params = MW0Params(
        grid_size=int(_need(cast("dict[str, Any]", _need(world, "grid")), "size")),
        patch_types=tuple(str(t) for t in _need(world, "patch_types")),
        resource_max_level=int(_need(resource, "max_level")),
        respawn_base_cycles=int(_need(resource, "respawn_base_cycles")),
        energy_max=float(_need(body, "energy_max")),
        integrity_max=float(_need(body, "integrity_max")),
        action_energy_delta={k: float(v) for k, v in action_delta_doc.items()},
        forage_yield=int(_need(forage, "yield_per_success")),
        food_storage_max=int(_need(forage, "food_storage_max")),
        storm_damage_per_hit=float(_need(storm, "integrity_damage_per_hit")),
        damage_event_min_delta=float(_need(storm, "damage_event_min_delta")),
        observation_gain={k: float(v) for k, v in gain_doc.items()},
        render_noise_sigma=float(_need(observation, "render_noise_sigma")),
        regimes=regimes,
        min_dwell_cycles=int(_need(regimes_doc, "min_dwell_cycles")),
        initial_regime=str(_need(regimes_doc, "initial_regime")),
        channel_delay_cycles={k: int(v) for k, v in delay_doc.items()},
        channel_corruption_rate=float(_need(channels, "corruption_rate")),
        channel_loss_rate=float(_need(channels, "loss_rate")),
    )
    return MW0Profile(params=params, digest=content_digest(doc), source=str(profile_doc.get("id", "m0_mw0")))
