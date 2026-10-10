"""PhysIO typed profile 加载（INC-11：fail-closed；p1_physio.profile.yaml v1.0 冻结合同）。

零无源默认值：缺键/错型/越域即 ProfileViolation——禁运行时发明。
hwmon 锚定（REV-0025 R6）：source 以 hwmon **name**（coretemp/nvme/acpitz）为锚，
索引字段仅作快照参考——loader 不消费索引做解析。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

_PROFILE_PATH = Path("config/profiles/p1_physio.profile.yaml")


class ProfileViolation(ValueError):
    """p1 profile 合同违反（fail-closed——缺键/错型/越域）。"""


@dataclass(frozen=True, slots=True)
class TelemetrySource:
    """单个物理源（hwmon name 锚定，R6）。"""

    key: str
    kind: str                    # hwmon | proc_stat | loadavg | meminfo | netdev | rapl
    path: str                    # hwmon: name 锚（coretemp）；其余：绝对路径
    quantity: str
    readable: bool


@dataclass(frozen=True, slots=True)
class P1PhysioProfile:
    """p1_physio.profile.yaml 的 typed 视图（只暴露实现消费的冻结字段）。"""

    profile_id: str
    version: str
    period_ms: int
    energy_round_dp: int
    schema_name: str                     # physio.host_telemetry.v1
    carrier: str                         # interoceptive
    delay_cycles: int
    min_dwell_cycles: int
    estop_upper_bound_cycles: int
    capability_actions: tuple[str, ...]
    contract_keys: tuple[str, ...]       # 合同 payload 三键（Q-L01-10 R5 勘误）
    sources: tuple[TelemetrySource, ...]
    backup_target_host: str


def _require(mapping: dict[str, Any], key: str) -> Any:
    if key not in mapping:
        raise ProfileViolation(f"p1 profile missing required key: {key}")
    return mapping[key]


def _require_int(mapping: dict[str, Any], key: str) -> int:
    value = _require(mapping, key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ProfileViolation(f"p1 profile key {key} must be int, got {type(value).__name__}")
    return value


def _require_str(mapping: dict[str, Any], key: str) -> str:
    value = _require(mapping, key)
    if not isinstance(value, str) or not value:
        raise ProfileViolation(f"p1 profile key {key} must be non-empty str")
    return value


def load_p1_physio_profile(path: Path | None = None) -> P1PhysioProfile:
    """加载并结构校验 p1 profile（fail-closed；调用方禁二次修改——frozen）。"""
    raw: dict[str, Any] = yaml.safe_load((path or _PROFILE_PATH).read_text(encoding="utf-8"))
    profile = _require(raw, "profile")
    sampling = _require(raw, "sampling")
    channel = _require(raw, "channel")
    quant = _require(channel, "quantization")
    grades = _require(raw, "l_grades")
    capability = _require(raw, "capability_set")
    sources_raw = _require(raw, "sources")
    backup = _require(raw, "backup")

    if _require_str(profile, "id") != "p1_physio":
        raise ProfileViolation("p1 profile id mismatch")
    version = _require_str(profile, "version")

    contract_keys_raw = channel.get("contract_keys")
    contract_keys: tuple[str, ...]
    if contract_keys_raw is None:
        # 冻结合同三键（Q-L01-10 REV-0025 R5 勘误注记的 profile 侧承载）
        field_semantics = _require(channel, "field_semantics")
        contract_keys = tuple(field_semantics.keys())
    else:
        contract_keys = tuple(str(k) for k in contract_keys_raw)
    if tuple(sorted(contract_keys)) != ("energy", "events", "integrity"):
        raise ProfileViolation(f"contract payload keys must be MW0-aligned trio, got {contract_keys}")

    sources: list[TelemetrySource] = []
    for key, value in sources_raw.items():
        if not isinstance(value, dict):
            raise ProfileViolation(f"source {key} must be mapping")
        source_map = cast(dict[str, Any], value)
        kind = str(source_map.get("quantity", "")).split("_")[0]
        if "hwmon" in source_map:
            sources.append(TelemetrySource(key=key, kind="hwmon", path=str(source_map["hwmon"]),
                                           quantity=str(source_map.get("quantity", "")), readable=True))
        elif "path" in source_map:
            readable = bool(source_map.get("readable", True))
            sources.append(TelemetrySource(key=key, kind=kind or "proc", path=str(source_map["path"]),
                                           quantity=str(source_map.get("quantity", "")), readable=readable))
        else:
            sources.append(TelemetrySource(key=key, kind=kind or "virtual", path="",
                                           quantity=str(source_map.get("quantity", "")),
                                           readable=bool(source_map.get("readable", False))))

    actions_raw = cast(list[Any], _require(capability, "actions"))
    if not actions_raw:
        raise ProfileViolation("capability_set.actions must be non-empty list")

    return P1PhysioProfile(
        profile_id="p1_physio",
        version=version,
        period_ms=_require_int(sampling, "period_ms"),
        energy_round_dp=_require_int(quant, "busy_rate_round_dp"),
        schema_name=_require_str(channel, "payload_schema"),
        carrier=_require_str(channel, "carrier"),
        delay_cycles=_require_int(channel, "delay_cycles"),
        min_dwell_cycles=_require_int(grades, "min_dwell_cycles"),
        estop_upper_bound_cycles=_require_int(grades, "estop_software_upper_bound_cycles"),
        capability_actions=tuple(str(a) for a in actions_raw),
        contract_keys=contract_keys,
        sources=tuple(sources),
        backup_target_host=_require_str(backup, "target_host"),
    )
