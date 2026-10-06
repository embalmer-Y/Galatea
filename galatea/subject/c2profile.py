"""C2 冻结 profile typed loader（INC-11 纪律：无加载器不宣称可运行）。

加载 C2 三份冻结 profile：
- `c2_affect.profile.yaml` v1.0（c2-freeze 冻结物，C2 首单元 loader）；
- `c2_memory.profile.yaml` v1.0（C2 次单元 loader——L06 参数，Q-L06-01/02/03/06 裁决承载）；
- `c2_workspace.profile.yaml` v1.0（C2 次单元 loader——L07 参数，Q-L07-01…06 裁决承载）。
全部 fail-closed 校验合同面（结构缺失/合同字段不符即 C2ProfileViolation）。
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from galatea.subject.affect.ports import DriveKind

__all__ = [
    "C2AffectParams",
    "C2MemoryParams",
    "C2WorkspaceParams",
    "C2ProfileViolation",
    "load_c2_affect_profile",
    "load_c2_memory_profile",
    "load_c2_workspace_profile",
]

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


# --------------------------------------------------------------------- memory
from galatea.subject.memory.ports import MemorySubsystem  # noqa: E402


@dataclass(frozen=True, slots=True)
class C2MemoryParams:
    """c2_memory.profile v1.0 typed 视图（Q-L06-01/02/03/06 裁决承载；运行期只读）。"""

    profile_id: str
    version: str
    capacities: dict[MemorySubsystem, int]
    tau_sub: dict[MemorySubsystem, int]
    retrieval_weights: tuple[float, float, float, float, float]   # cue/strength/recency/affect/reliability
    affective_missing_default: float
    access_boost: float
    access_boost_cap: float
    protected_exempt: bool
    top_k: int
    confusion_upper_bound: float
    overflow_demotion_order: tuple[str, ...]

    def ref(self) -> str:
        return f"{self.profile_id}@{self.version}"


def load_c2_memory_profile(path: Path | None = None) -> C2MemoryParams:
    """加载 c2_memory.profile + 合同校验（fail closed）。"""
    p = path or Path("config/profiles/c2_memory.profile.yaml")
    if not p.is_file():
        raise C2ProfileViolation(f"c2 memory profile not found: {p}")
    raw = cast(dict[str, Any], yaml.safe_load(p.read_text(encoding="utf-8")))
    header = _req(raw, "profile")
    if header.get("id") != "c2_memory":
        raise C2ProfileViolation(f"profile.id != c2_memory: {header.get('id')!r}")
    caps_raw = cast(dict[str, int], _req(raw, "capacities"))
    caps = {MemorySubsystem(k): _pos_int(v, f"capacity.{k}") for k, v in caps_raw.items()}
    if set(caps) != set(MemorySubsystem):
        raise C2ProfileViolation("capacities must cover all eight subsystems（Q-L06-01①）")
    tau_raw = cast(dict[str, int], _req(_req(raw, "decay"), "tau_sub"))
    tau = {MemorySubsystem(k): _pos_int(v, f"tau_sub.{k}") for k, v in tau_raw.items()}
    if set(tau) != set(MemorySubsystem):
        raise C2ProfileViolation("tau_sub must cover all eight subsystems（Q-L06-03①）")
    ret = _req(raw, "retrieval")
    weights = cast(dict[str, float], ret["weights"])
    if tuple(weights.values()) != (1.0, 1.0, 1.0, 1.0, 1.0):
        raise C2ProfileViolation(f"retrieval weights must be equal 1:1:1:1:1（Q-L06-02①）: {weights!r}")
    if ret.get("reliability_mapping") != "strength":
        raise C2ProfileViolation("reliability_mapping must be strength（Q-L06-02② M2 映射维持）")
    if ret.get("affect_modulation_c2") != "none":
        raise C2ProfileViolation("affect_modulation_c2 must be none（Q-L06-02③）")
    decay = _req(raw, "decay")
    boost = float(decay["access_boost"])
    if boost != 0.125:
        raise C2ProfileViolation(f"access_boost must be 0.125（Q-L06-03③）: {boost!r}")
    if decay.get("protected_exempt") is not True:
        raise C2ProfileViolation("protected_exempt must be true（L06 §4.5）")
    meta = _req(raw, "metamemory")
    bound = float(meta["confusion_rate_upper_bound"])
    if bound != 0.05:
        raise C2ProfileViolation(f"confusion upper bound must be 0.05（Q-L06-06②）: {bound!r}")
    overflow = _req(raw, "overflow")
    if overflow.get("policy") != "demote_oldest_labile_to_archived":
        raise C2ProfileViolation("overflow.policy must be demote_oldest_labile_to_archived（Q-L06-01②）")
    order = tuple(cast(list[str], overflow["demotion_order"]))
    if order != ("last_access_asc", "memory_id_asc"):
        raise C2ProfileViolation(f"demotion_order mismatch（Q-L06-01③）: {order!r}")
    top_k = _pos_int(ret["top_k"], "retrieval.top_k")
    return C2MemoryParams(
        profile_id=str(header["id"]), version=str(header["version"]),
        capacities=caps, tau_sub=tau,
        retrieval_weights=(1.0, 1.0, 1.0, 1.0, 1.0),
        affective_missing_default=float(ret["affective_missing_default"]),
        access_boost=boost, access_boost_cap=float(decay["access_boost_cap"]),
        protected_exempt=True, top_k=top_k, confusion_upper_bound=bound,
        overflow_demotion_order=order,
    )


# ------------------------------------------------------------------ workspace
@dataclass(frozen=True, slots=True)
class C2WorkspaceParams:
    """c2_workspace.profile v1.0 typed 视图（Q-L07-01…06 裁决承载；运行期只读）。"""

    profile_id: str
    version: str
    capacity_k: int
    weights: tuple[float, float, float, float, float]   # goal/affect/novelty/uncertainty/info
    affect_modulation_bound: tuple[float, float]
    receipt_timeout_cycles: int
    depth_max: int
    frame_ttl_cycles: int
    dedup_ttl_cycles: int
    watch_modules: tuple[str, ...]
    effective_access_rule: str

    def ref(self) -> str:
        return f"{self.profile_id}@{self.version}"


def load_c2_workspace_profile(path: Path | None = None) -> C2WorkspaceParams:
    """加载 c2_workspace.profile + 合同校验（fail closed）。"""
    p = path or Path("config/profiles/c2_workspace.profile.yaml")
    if not p.is_file():
        raise C2ProfileViolation(f"c2 workspace profile not found: {p}")
    raw = cast(dict[str, Any], yaml.safe_load(p.read_text(encoding="utf-8")))
    header = _req(raw, "profile")
    if header.get("id") != "c2_workspace":
        raise C2ProfileViolation(f"profile.id != c2_workspace: {header.get('id')!r}")
    cap = _req(raw, "capacity")
    k = _pos_int(cap["K"], "capacity.K")
    if cap.get("subquotas") not in (None, "none"):
        raise C2ProfileViolation("subquotas must be none（Q-L07-01②）")
    comp = _req(raw, "competition")
    weights = cast(dict[str, float], comp["weights"])
    if tuple(weights.values()) != (1.0, 1.0, 1.0, 1.0, 1.0):
        raise C2ProfileViolation(f"competition weights must be equal 1:1:1:1:1（Q-L07-02①）: {weights!r}")
    bound = cast(list[float], comp["affect_modulation_bound"])
    if tuple(bound) != (0.5, 2.0):
        raise C2ProfileViolation(f"affect_modulation_bound must be [0.5, 2.0]（Q-L07-02②）: {bound!r}")
    if comp.get("modulation_scope") != "component_weight_only":
        raise C2ProfileViolation("modulation_scope must be component_weight_only（Q-L07-02③）")
    rec = _req(raw, "receipts")
    timeout = _pos_int(rec["timeout_cycles"], "receipts.timeout_cycles")
    if rec.get("retry") != "forbidden" or rec.get("rebroadcast") != "forbidden":
        raise C2ProfileViolation("receipts retry/rebroadcast must be forbidden（Q-L07-03③）")
    recu = _req(raw, "recursion")
    depth = _pos_int(recu["depth_max"], "recursion.depth_max")
    ttl = _pos_int(recu["frame_ttl_cycles"], "recursion.frame_ttl_cycles")
    dedup = _pos_int(recu["dedup_ttl_cycles"], "recursion.dedup_ttl_cycles")
    sep = _req(raw, "separated_modules")
    watch_modules = tuple(cast(list[str], sep["watch_modules_c2"]))
    if set(watch_modules) != {"perception_L03", "models_L04", "affect_L05", "memory_L06"}:
        raise C2ProfileViolation(f"watch_modules_c2 mismatch（Q-L07-05②）: {watch_modules!r}")
    wp = _req(raw, "watch_points")
    if wp.get("addition") != "profile_version_change_only":
        raise C2ProfileViolation("watch_points.addition must be profile_version_change_only（Q-L07-06②）")
    if wp.get("posthoc_registration") != "rejected":
        raise C2ProfileViolation("posthoc_registration must be rejected（Q-L07-06③）")
    eff = _req(raw, "effective_access")
    if eff.get("rule") != "receipts_ge_2_and_separated_watch_changes_ge_2":
        raise C2ProfileViolation("effective_access.rule mismatch（L07 §4.3）")
    return C2WorkspaceParams(
        profile_id=str(header["id"]), version=str(header["version"]),
        capacity_k=k, weights=(1.0, 1.0, 1.0, 1.0, 1.0),
        affect_modulation_bound=(float(bound[0]), float(bound[1])),
        receipt_timeout_cycles=timeout, depth_max=depth,
        frame_ttl_cycles=ttl, dedup_ttl_cycles=dedup,
        watch_modules=watch_modules,
        effective_access_rule=str(eff["rule"]),
    )
