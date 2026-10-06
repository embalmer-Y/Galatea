"""C2 冻结 profile typed loader（INC-11 纪律：无加载器不宣称可运行）。

加载 `config/profiles/c2_affect.profile.yaml` v1.0（c2-freeze 冻结物）并
fail-closed 校验合同面（结构缺失/合同字段不符即 C2ProfileViolation）。
L06/L07 profile（c2_memory/c2_workspace v1.0）typed loader 随各自实现件交付
（C2 次单元）——本文件只承载 affect 面。
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from galatea.subject.affect.ports import DriveKind

__all__ = ["C2AffectParams", "C2ProfileViolation", "load_c2_affect_profile"]

_PROFILE_PATH = Path("config/profiles/c2_affect.profile.yaml")


class C2ProfileViolation(ValueError):
    """C2 affect profile 与冻结合同不符（fail closed）。"""


@dataclass(frozen=True, slots=True)
class C2AffectParams:
    """c2_affect.profile v1.0 typed 视图（数值 = 冻结值，运行期只读）。"""

    profile_id: str
    version: str
    valence_domain: tuple[float, float]
    other_domain: tuple[float, float]
    drive_weights: dict[DriveKind, float]
    set_points: dict[DriveKind, float]
    tau_int: int
    tau_dec: int
    band: float
    ethics_valence_le: float
    ethics_persistence_ge: float
    ethics_sustained_cycles: int

    def ref(self) -> str:
        return f"{self.profile_id}@{self.version}"


def load_c2_affect_profile(path: Path | None = None) -> C2AffectParams:
    """加载 + 合同校验（fail closed：任何偏离冻结文即拒）。"""
    p = path or _PROFILE_PATH
    if not p.is_file():
        raise C2ProfileViolation(f"c2 affect profile not found: {p}")
    raw = cast(dict[str, Any], yaml.safe_load(p.read_text(encoding="utf-8")))
    header = _req(raw, "profile")
    if header.get("id") != "c2_affect":
        raise C2ProfileViolation(f"profile.id != c2_affect: {header.get('id')!r}")
    version = str(header.get("version"))

    domains = _req(raw, "domains")
    if domains.get("cross_dim_aggregation") != "forbidden":
        raise C2ProfileViolation("cross_dim_aggregation must be forbidden（Q-L05-01③）")
    if domains.get("social_relevance_c2") != "unknown_baseline":
        raise C2ProfileViolation("social_relevance_c2 must be unknown_baseline（D-14）")
    val = cast(dict[str, float], domains["valence"])
    if (val["min"], val["max"]) != (-1.0, 1.0) or not val.get("symmetric"):
        raise C2ProfileViolation("valence domain must be symmetric [−1,1]（Q-L05-01①）")
    other = cast(dict[str, float], domains["other_dims"])
    if (other["min"], other["max"]) != (0.0, 1.0):
        raise C2ProfileViolation("other dims domain must be [0,1]（Q-L05-01②）")

    drives = _req(raw, "drives")
    set_list = cast(list[str], drives["set"])
    if set(set_list) != {"energy", "integrity", "load"}:
        raise C2ProfileViolation(f"drives.set mismatch: {set_list!r}")
    weights = cast(dict[str, float], drives["weights"])
    set_points_raw = cast(dict[str, float], drives["set_points"])
    if drives.get("weight_source") != "profile_frozen":
        raise C2ProfileViolation("weight_source must be profile_frozen（禁在线自改）")
    if float(drives.get("appraisal_adjustment_c2", -1.0)) != 0.0:
        raise C2ProfileViolation("appraisal_adjustment_c2 must be 0.0（Q-L05-02③）")

    dynamics = _req(raw, "dynamics")
    tau_int = _pos_int(dynamics.get("tau_integrator_cycles"), "tau_integrator_cycles")
    tau_dec = _pos_int(dynamics.get("tau_decay_cycles"), "tau_decay_cycles")
    band = float(dynamics["hysteresis_band"])
    if not 0.0 < band < 1.0:
        raise C2ProfileViolation(f"band out of (0,1): {band!r}")
    if dynamics.get("rng_operators") != "none_c2":
        raise C2ProfileViolation("dynamics.rng_operators must be none_c2（Q-G00-10 纪律）")

    valence_sec = _req(raw, "valence")
    if valence_sec.get("input") != "body_belief_only":
        raise C2ProfileViolation("valence.input must be body_belief_only（不变量 2）")
    if valence_sec.get("not_reward") is not True:
        raise C2ProfileViolation("valence.not_reward must be true（HLD §11.1）")

    modulation = _req(raw, "modulation")
    for key in ("bounded", "ttl_required", "receipt_required"):
        if modulation.get(key) is not True:
            raise C2ProfileViolation(f"modulation.{key} must be true（L05 §4.4）")

    ethics = _req(raw, "ethics")
    trigger = cast(dict[str, Any], ethics["trigger"])
    ethics_valence_le = float(trigger["valence_le"])
    ethics_persistence_ge = float(trigger["persistence_ge"])
    ethics_sustained = _pos_int(trigger.get("sustained_cycles_ge"), "ethics.sustained_cycles_ge")
    if not -1.0 <= ethics_valence_le < 0.0:
        raise C2ProfileViolation(f"ethics valence_le out of [−1,0): {ethics_valence_le!r}")
    if not 0.0 < ethics_persistence_ge <= 1.0:
        raise C2ProfileViolation(f"ethics persistence_ge out of (0,1]: {ethics_persistence_ge!r}")
    if ethics.get("conservative_default_preserved") is not True:
        raise C2ProfileViolation("ethics.conservative_default_preserved must be true")

    determinism = _req(raw, "determinism")
    if determinism.get("rng_operators") != "none_c2":
        raise C2ProfileViolation("determinism.rng_operators must be none_c2")

    return C2AffectParams(
        profile_id=str(header["id"]),
        version=version,
        valence_domain=(-1.0, 1.0),
        other_domain=(0.0, 1.0),
        drive_weights={DriveKind(k): float(weights[k]) for k in set_list},
        set_points={DriveKind(k): float(set_points_raw[k]) for k in set_list},
        tau_int=tau_int,
        tau_dec=tau_dec,
        band=band,
        ethics_valence_le=ethics_valence_le,
        ethics_persistence_ge=ethics_persistence_ge,
        ethics_sustained_cycles=ethics_sustained,
    )


def _req(obj: dict[str, Any], key: str) -> dict[str, Any]:
    if key not in obj:
        raise C2ProfileViolation(f"missing section: {key}")
    return cast(dict[str, Any], obj[key])


def _pos_int(v: Any, name: str) -> int:
    if not isinstance(v, int) or isinstance(v, bool) or v < 1:
        raise C2ProfileViolation(f"{name} must be positive int: {v!r}")
    return v
