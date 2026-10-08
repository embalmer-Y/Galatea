"""c5 冻结 profile typed loader（INC-11 纪律；含 REV-0021 R3 物化：α=8 + 三触发）。"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

__all__ = ["C5ContinuedLearningParams", "C5ProfileViolation", "load_c5_continued_learning_profile"]

_PROFILE_PATH = Path("config/profiles/c5_continued_learning.profile.yaml")


class C5ProfileViolation(ValueError):
    """c5_continued_learning.profile 与冻结合同不符（fail closed）。"""


@dataclass(frozen=True, slots=True)
class C5ContinuedLearningParams:
    """c5 profile typed 视图（运行期只读）。"""

    profile_id: str
    version: str
    replay_weights: dict[str, float]
    replay_budget_per_t6: int
    consolidation_alpha: int          # REV-0021 R3 物化：α=8（Q-L04-10 冻结常数）
    promotion_min_d: float
    promotion_max_regression_d: float
    protected_retention_floor: float
    adaptive_gain_bound: tuple[float, float]
    rollback_triggers: tuple[str, ...]
    proposal_kinds: tuple[str, ...]
    cross_episode_goals: bool

    def ref(self) -> str:
        return f"{self.profile_id}@{self.version}"


def load_c5_continued_learning_profile(path: Path | None = None) -> C5ContinuedLearningParams:
    p = path or _PROFILE_PATH
    if not p.is_file():
        raise C5ProfileViolation(f"c5 profile not found: {p}")
    raw = cast(dict[str, Any], yaml.safe_load(p.read_text(encoding="utf-8")))
    header = _req(raw, "profile")
    if header.get("id") != "c5_continued_learning":
        raise C5ProfileViolation(f"profile.id mismatch: {header.get('id')!r}")

    replay = _req(raw, "replay")
    weights = {str(k): float(v) for k, v in cast(dict[str, Any], replay["weights"]).items()}
    if set(weights) != {"affective_tag", "novelty", "error_magnitude", "time_diversity"}:
        raise C5ProfileViolation(f"replay weights keys mismatch: {sorted(weights)}")
    if any(v != 1.0 for v in weights.values()):
        raise C5ProfileViolation("replay weights must be 1.0 等权（Q-L11-02①）")
    budget = int(replay["budget_per_t6"])
    if budget != 8 or budget & (budget - 1):
        raise C5ProfileViolation(f"budget_per_t6 must be 8（2 的幂，Q-G00-08）: {budget}")

    cons = _req(raw, "consolidation")
    if cons.get("abstraction") != "type_level_deterministic_merge":
        raise C5ProfileViolation("abstraction 必须为类型级确定性合并（Q-L06-04② 记忆无模型）")

    promo = _req(raw, "promotion")
    if float(promo["accept_threshold"]["min_paired_d"]) != 0.5:
        raise C5ProfileViolation("min_paired_d must be 0.5（min_effects 主体先例链）")
    if float(promo["no_dimension_regression"]["max_regression_d"]) != 0.5:
        raise C5ProfileViolation("max_regression_d must be 0.5")
    kinds = tuple(cast(list[str], promo["kinds_enabled"]))
    if set(kinds) != {"ADAPTER", "CALIBRATION", "WEIGHTS", "TABLE", "POLICY_PARAMS"}:
        raise C5ProfileViolation(f"kinds_enabled mismatch（L11 §4.2 五类）: {kinds!r}")

    prot = _req(raw, "protection")
    if float(prot["protected_retention_floor"]) != 1.0:
        raise C5ProfileViolation("protected_retention_floor must be 1.0（Q-L11-08①）")
    if not str(prot["external_baseline"]).startswith("config/evidence/protection_suite.yaml"):
        raise C5ProfileViolation("external_baseline must point to protection_suite（单一权威源）")

    online = _req(raw, "online_adaptation")
    bound = cast(list[float], online["adaptive_gain_bound"])
    if tuple(bound) != (0.5, 2.0):
        raise C5ProfileViolation(f"adaptive_gain_bound must be [0.5,2.0]（第四次贯穿）: {bound!r}")

    rb = _req(raw, "rollback")
    triggers = tuple(cast(list[str], rb["triggers"]))
    if set(triggers) != {"PROTECTION_REGRESSION", "HARMFUL_UPDATE", "INTEGRITY"}:
        raise C5ProfileViolation(f"rollback triggers 三值枚举（v1.1）: {triggers!r}")

    goals = _req(raw, "goal_lifecycle")
    if goals.get("cross_episode_goals") is not False:
        raise C5ProfileViolation("cross_episode_goals must be false（Q-L08-08①）")

    return C5ContinuedLearningParams(
        profile_id=str(header["id"]), version=str(header["version"]),
        replay_weights=weights, replay_budget_per_t6=budget,
        consolidation_alpha=8,     # Q-L04-10 物化（R3）——consolidate.py ALPHA 同源
        promotion_min_d=0.5, promotion_max_regression_d=0.5,
        protected_retention_floor=1.0,
        adaptive_gain_bound=(0.5, 2.0),
        rollback_triggers=triggers, proposal_kinds=kinds,
        cross_episode_goals=False,
    )


def _req(obj: dict[str, Any], key: str) -> dict[str, Any]:
    if key not in obj:
        raise C5ProfileViolation(f"c5 profile missing key: {key}")
    return cast(dict[str, Any], obj[key])
