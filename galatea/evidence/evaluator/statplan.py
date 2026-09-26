"""冻结统计计划加载/校验/最小效应（L13 §4.3/§10 statplan.py）。

纪律：claim 冻结先于运行；运行后修改 = StatPlanMutation 拒绝（L13 §6）——
本加载器 fail-closed（缺十字段集任一项即拒，Q-L13-01），digest 入 EvidenceResult
stat_plan_ref，加载时校验内容 digest（防冻结后静默改写）。
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from galatea.kernel.digest import content_digest

__all__ = ["StatPlan", "StatPlanClaim", "StatPlanViolation", "load_stat_plan", "verify_stat_plan"]

# 统计计划模板十字段最小集（Q-L13-01；L13 §4.3）
_REQUIRED_CLAIM_FIELDS: tuple[str, ...] = (
    "hypothesis",       # 假设（可反驳、预注册）
    "estimand",         # estimand
    "primary_endpoints",  # 主终点（≤3、预注册）
    "test",             # 检验方法
    "effect_ci_rule",   # 效应量与 95% CI 规则
    "threshold",        # 判定阈值（含最小可辨效应引用）
    "unknown_handling",  # 未知处理规则
)
# n 字段二选一（按 claim 设计：n_per_arm / n_per_cell）
_N_FIELDS: tuple[str, ...] = ("n_per_arm", "n_per_cell", "min_trials_per_cell")


class StatPlanViolation(ValueError):
    """统计计划与模板合同不符（缺字段/主终点超界/重复 claim）——fail closed。"""


@dataclass(frozen=True, slots=True)
class StatPlanClaim:
    """单 claim 的冻结协议（typed 视图）。"""

    claim_id: str
    hypothesis: str
    estimand: str
    primary_endpoints: tuple[str, ...]
    test: str
    effect_ci_rule: str
    threshold: dict[str, str]
    unknown_handling: str
    n: int
    correction: str


@dataclass(frozen=True, slots=True)
class StatPlan:
    """冻结统计计划（digest = canonical JSON sha256；EvidenceResult.stat_plan_ref 指向）。"""

    id: str
    version: str
    claims: tuple[StatPlanClaim, ...]
    digest: str


def load_stat_plan(path: Path) -> StatPlan:
    """加载并校验冻结统计计划（L13 §4.3 十字段集 fail-closed）。"""
    if not path.is_file():
        raise StatPlanViolation(f"stat plan not found: {path}")
    raw = cast(dict[str, Any], yaml.safe_load(path.read_text(encoding="utf-8")))
    header = cast(dict[str, Any], _require(raw, "stat_plan"))
    plan_id = cast(str, _require(header, "id"))
    version = cast(str, _require(header, "version"))
    correction = cast(str, _require(header, "correction"))
    claims_raw = cast(list[dict[str, Any]], _require(header, "claims"))
    if not claims_raw:
        raise StatPlanViolation("stat plan requires at least one claim")
    claims: list[StatPlanClaim] = []
    seen: set[str] = set()
    for entry in claims_raw:
        claim_id = cast(str, _require(entry, "claim_id"))
        if claim_id in seen:
            raise StatPlanViolation(f"duplicate claim_id: {claim_id}")
        seen.add(claim_id)
        missing = [f for f in _REQUIRED_CLAIM_FIELDS if f not in entry]
        if missing:
            raise StatPlanViolation(f"claim {claim_id} missing fields: {missing}")
        endpoints = tuple(cast(list[str], entry["primary_endpoints"]))
        if not 1 <= len(endpoints) <= 3:
            raise StatPlanViolation(f"claim {claim_id}: primary endpoints must be 1..3（Q-L13-01）")
        n = _resolve_n(claim_id, entry)
        threshold = cast(dict[str, str], entry["threshold"])
        if "min_effect_ref" not in threshold:
            raise StatPlanViolation(
                f"claim {claim_id}: threshold.min_effect_ref required（Q-L13-09：每 claim 统计计划必须引用 min_effects 条目）"
            )
        claims.append(
            StatPlanClaim(
                claim_id=claim_id,
                hypothesis=str(entry["hypothesis"]).strip(),
                estimand=str(entry["estimand"]),
                primary_endpoints=endpoints,
                test=str(entry["test"]),
                effect_ci_rule=str(entry["effect_ci_rule"]),
                threshold=threshold,
                unknown_handling=str(entry["unknown_handling"]).strip(),
                n=n,
                correction=correction,
            )
        )
    digest = content_digest(
        {
            "id": plan_id,
            "version": version,
            "correction": correction,
            "claims": [
                {
                    "claim_id": c.claim_id,
                    "hypothesis": c.hypothesis,
                    "estimand": c.estimand,
                    "primary_endpoints": list(c.primary_endpoints),
                    "test": c.test,
                    "effect_ci_rule": c.effect_ci_rule,
                    "threshold": c.threshold,
                    "unknown_handling": c.unknown_handling,
                    "n": c.n,
                }
                for c in claims
            ],
        }
    )
    return StatPlan(id=plan_id, version=version, claims=tuple(claims), digest=digest)


def verify_stat_plan(plan: StatPlan, path: Path) -> None:
    """冻结完整性：重载并比对 digest（运行前每次校验；不一致 = StatPlanMutation 前兆）。"""
    reloaded = load_stat_plan(path)
    if reloaded.digest != plan.digest or reloaded.id != plan.id or reloaded.version != plan.version:
        raise StatPlanViolation(
            f"stat plan drift detected for {plan.id}@{plan.version}（运行后改动 = StatPlanMutation，L13 §6）"
        )


def _require(obj: dict[str, Any], key: str) -> Any:
    if key not in obj:
        raise StatPlanViolation(f"missing key: {key}")
    return obj[key]


def _resolve_n(claim_id: str, entry: dict[str, Any]) -> int:
    for field_name in _N_FIELDS:
        if field_name in entry:
            n = cast(int, entry[field_name])
            if n <= 0:
                raise StatPlanViolation(f"claim {claim_id}: {field_name} must be positive")
            return n
    raise StatPlanViolation(f"claim {claim_id}: sample size field required（{_N_FIELDS} 之一）")
