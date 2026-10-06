"""C3 冻结 profile typed loader（INC-11 纪律：无加载器不宣称可运行）。

加载 `config/profiles/c3_motivation.profile.yaml` v1.0（c3-freeze 冻结物）并
fail-closed 校验合同面（结构缺失/合同字段不符即 C3ProfileViolation）。
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

__all__ = ["C3MotivationParams", "C3ProfileViolation", "load_c3_motivation_profile"]

_PROFILE_PATH = Path("config/profiles/c3_motivation.profile.yaml")


class C3ProfileViolation(ValueError):
    """c3_motivation.profile 与冻结合同不符（fail closed）。"""


@dataclass(frozen=True, slots=True)
class C3MotivationParams:
    """c3_motivation.profile v1.0 typed 视图（运行期只读）。"""

    profile_id: str
    version: str
    pareto_weights: tuple[float, float, float, float, float]
    priority_classes: tuple[str, ...]
    arb_weights: tuple[float, float, float, float, float]
    affect_factor_bound: tuple[float, float]
    enabled_controllers: tuple[str, ...]
    min_dwell_cycles: int
    switch_confirm_windows: int
    loss_of_control_window: int
    blocked_abandon_threshold: int
    critical_error: float
    help_frequency_cap_window: int
    help_frequency_cap: int
    wired_sources: tuple[str, ...]

    def ref(self) -> str:
        return f"{self.profile_id}@{self.version}"


def load_c3_motivation_profile(path: Path | None = None) -> C3MotivationParams:
    """加载 + 合同校验（fail closed：任何偏离冻结文即拒）。"""
    p = path or _PROFILE_PATH
    if not p.is_file():
        raise C3ProfileViolation(f"c3 motivation profile not found: {p}")
    raw = cast(dict[str, Any], yaml.safe_load(p.read_text(encoding="utf-8")))
    header = _req(raw, "profile")
    if header.get("id") != "c3_motivation":
        raise C3ProfileViolation(f"profile.id != c3_motivation: {header.get('id')!r}")

    pareto = _req(raw, "pareto")
    if pareto.get("front_rule") != "dominance_not_weighted_sum":
        raise C3ProfileViolation("front_rule must be dominance_not_weighted_sum（Q-L08-03③）")
    w = _weights5(cast(dict[str, float], pareto["weights"]), "pareto.weights")

    arb = _req(raw, "arbitration")
    aw = _weights5(cast(dict[str, float], arb["weights"]), "arbitration.weights")
    bound = cast(list[float], arb["affect_factor_bound"])
    if tuple(bound) != (0.5, 2.0):
        raise C3ProfileViolation(f"affect_factor_bound must be [0.5,2.0]（Q-L09-01②）: {bound!r}")
    if arb.get("affect_bound_ref") != "c2_affect.profile@v1.0/modulation":
        raise C3ProfileViolation("affect_bound_ref must point to c2_affect modulation（必回执面）")

    prio = _req(raw, "priority_order")
    classes = tuple(cast(list[str], prio["classes"]))
    if classes != ("VIABILITY", "NORM", "COMMITMENT", "OTHER"):
        raise C3ProfileViolation(f"priority classes mismatch（Q-L08-04）: {classes!r}")
    if prio.get("rng_stream") != "none_c3":
        raise C3ProfileViolation("priority rng_stream must be none_c3（Q-L08-04③）")

    ctrl = _req(raw, "controllers")
    enabled = tuple(cast(list[str], ctrl["enabled_c3"]))
    if set(enabled) != {"Habit", "ModelBased", "ActivePerception"}:
        raise C3ProfileViolation(f"enabled_c3 mismatch（Q-L09-02②）: {enabled!r}")

    meta = _req(raw, "metacontrol")
    dwell = _pos_int(meta.get("min_dwell_cycles"), "min_dwell_cycles")
    if dwell != 4:
        raise C3ProfileViolation(f"min_dwell_cycles must be 4（Q-L09-04，T3 同锚）: {dwell!r}")
    confirm = _pos_int(meta.get("switch_confirm_windows"), "switch_confirm_windows")
    if confirm != 2:
        raise C3ProfileViolation(f"switch_confirm_windows must be 2（Q-L09-04）")
    triggers = cast(dict[str, Any], meta["triggers"])
    loc = str(triggers.get("SEEK_HELP", ""))
    if "Lc16" not in loc:
        raise C3ProfileViolation("SEEK_HELP trigger must carry Lc16（Q-L09-03④）")
    aband = str(triggers.get("ABANDON", ""))
    if "128" not in aband:
        raise C3ProfileViolation("ABANDON trigger must carry TTL/2=128（Q-L09-03⑤）")

    help_sec = _req(raw, "seek_help")
    cap_window = _pos_int(help_sec.get("frequency_cap_per_64_cycles"), "help cap")
    if cap_window != 1:
        raise C3ProfileViolation(f"help cap must be 1/64（Q-L09-07③）")

    wired = tuple(cast(list[str], _req(_req(raw, "wired_sources_c3"), "sources")))
    if len(set(wired)) != 8:
        raise C3ProfileViolation(f"wired_sources must cover 8 kinds: {wired!r}")

    det = _req(raw, "determinism")
    if det.get("rng_streams") != "none_c3":
        raise C3ProfileViolation("determinism.rng_streams must be none_c3（Q-G00-10）")

    return C3MotivationParams(
        profile_id=str(header["id"]), version=str(header["version"]),
        pareto_weights=w, priority_classes=classes, arb_weights=aw,
        affect_factor_bound=(float(bound[0]), float(bound[1])),
        enabled_controllers=enabled,
        min_dwell_cycles=dwell, switch_confirm_windows=confirm,
        loss_of_control_window=16, blocked_abandon_threshold=128,
        critical_error=0.8, help_frequency_cap_window=64, help_frequency_cap=1,
        wired_sources=wired,
    )


def _req(obj: dict[str, Any], key: str) -> dict[str, Any]:
    if key not in obj:
        raise C3ProfileViolation(f"missing section: {key}")
    return cast(dict[str, Any], obj[key])


def _weights5(w: dict[str, float], name: str) -> tuple[float, float, float, float, float]:
    if len(w) != 5 or tuple(w.values()) != (1.0, 1.0, 1.0, 1.0, 1.0):
        raise C3ProfileViolation(f"{name} must be equal 1:1:1:1:1（等权先例链）: {w!r}")
    return (1.0, 1.0, 1.0, 1.0, 1.0)


def _pos_int(v: Any, name: str) -> int:
    if not isinstance(v, int) or isinstance(v, bool) or v < 1:
        raise C3ProfileViolation(f"{name} must be positive int: {v!r}")
    return v
