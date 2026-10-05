"""C1 冻结 profile 的 typed 加载器（c1_perception_models.profile.yaml v1.0；L03/L04/L11/L02-C1 共档）。

INC-11 纪律：冻结 profile 必须有 typed loader 才可被运行时消费——缺键/越界/合同不符
一律 fail closed（C1ProfileViolation）。数值全部溯源：
- perception/models/learning/sensorium_c1 各值 → 15 项成批裁决（Q-L02-01/04/06、
  Q-L03-01/02/03/05/07、Q-L04-01/02/04/07/08、Q-L09-08、Q-L11-01/06）+ 转移语义批
  （Q-L04-09/-10/-11，2026-10-05）；
- 先验 π / 似然表原料（g(d)、σ）→ 冻结 m0_mw0.profile（初始条件合同，Q-L04-11/
  Q-L03-03 派生链）——本 loader 直接读冻结 YAML（合同文件），不 import env 实现。

formed_features_flat 维度域（Q-L02-06，特征空间由形成层唯一决定）与事件/朝向枚举
（Q-L01-08 M0 事件集；proprio 载荷域）在此集中声明，禁评价侧自造。
"""
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from galatea.kernel.digest import content_digest


class C1ProfileViolation(ValueError):
    """冻结 profile 与合同不符（缺键/类型错/禁用项出现）——fail closed。"""


#: EXT_EVENT one-hot 域 = Q-L01-08 M0 事件集（integrity_damage_event + energy_depleted）
EVENT_KINDS: tuple[str, ...] = ("energy_depleted", "integrity_damage_event")

#: PROPRIO one-hot 域 = L01 §4 proprio 载荷 orientation 域（MW0 DIRECTIONS 键集，冻结）
ORIENTATION_TOKENS: tuple[str, ...] = ("N", "E", "S", "W")

#: INTERO 特征 = 四 sensation 标量序（Q-L02-05 集合 + Q-L02-06 展平序）
INTERO_SCALARS: tuple[str, ...] = ("energy_level", "integrity_level", "damage_event", "energy_depleted")


def _need(mapping: dict[str, Any], key: str) -> Any:
    value = mapping.get(key)
    if value is None:
        raise C1ProfileViolation(f"profile key missing: {key}")
    return value


@dataclass(frozen=True, slots=True)
class C1PerceptionParams:
    """知觉 C1 参数（c1 profile perception 节 + m0 冻结参数派生）。"""

    believe_threshold: float              # Q-L03-02
    hypothesis_cap: int                   # Q-L03-05
    collapse_confidence: float            # Q-L03-05
    collapse_margin: float                # Q-L03-05
    collapse_tie: str                     # Q-L03-05
    belief_reopenable: bool               # Q-L03-05
    bin_edges: tuple[float, ...]          # Q-L03-03（5 档确定性量化）
    prior_resource_density: float         # Q-L04-11：initial_regime 覆盖率恒定
    gain_by_distance: dict[str, float]    # Q-L03-03：m0 冻结 g(d)
    render_noise_sigma: float             # Q-L03-03：m0 冻结 σ
    ood_rule: str                         # Q-L03-02：event_level_domain_exit
    abstain_form: str                     # Q-L03-02：binary
    learning_from_data: str               # 必须为 forbidden（Q-L03-03）
    distance_metric: str                  # chebyshev_egocentric


@dataclass(frozen=True, slots=True)
class C1ModelsParams:
    """三模型 C1 参数（c1 profile models 节）。"""

    world_model_scope: str                # Q-L04-08：egocentric_plus_dead_reckoning
    update_period_cycles: int             # Q-L04-02：T3 窗批
    multi_hypothesis_cap: int             # Q-L04-02（与 Q-L03-05 单值共用）
    rollout_depth_max: int                # Q-L04-01
    rollout_width_max: int                # Q-L04-01
    rollout_over_budget_prune: str        # Q-L04-01：width_desc_by_posterior
    rollout_budget_in_checkpoint: bool    # Q-L04-01：digest 引用制
    self_error_dimensions: str            # Q-L04-04：body_state_vector
    tau_fast_cycles: int                  # Q-L04-04
    tau_slow_cycles: int                  # Q-L04-04
    error_layer_weights: tuple[float, ...]  # Q-L09-08：1:1:1
    cross_layer_normalization: str        # 必须为 forbidden（Q-L09-08）


@dataclass(frozen=True, slots=True)
class C1LearningParams:
    """学习 C1 件参数（c1 profile learning 节）。"""

    online_step_cap: float                # Q-L11-01：0.125
    persistence: str                      # Q-L11-06：checkpoint_incremental
    proposal_only: bool                   # L11 §9 C1 行（必须 True）
    neural_components: str                # Q-L11-01：deferred_to_c5


@dataclass(frozen=True, slots=True)
class C1SensoriumParams:
    """sensorium C1 件参数（c1 profile sensorium_c1 节）。"""

    calibration_version: str              # Q-L02-01：c1-static-v1
    runtime_drift: str                    # 必须为 forbidden（Q-L02-01）
    quality_scale: tuple[float, float]    # Q-L02-04
    snr_est: str                          # Q-L02-04：placeholder_to_c2
    pred_error_feature_space: str         # Q-L02-06：formed_features_flat
    precision_weighting: str              # Q-L02-06：deferred_to_c2


@dataclass(frozen=True, slots=True)
class C1Profile:
    """C1 冻结合同 typed 视图（digest 入 checkpoint 谱系引用）。"""

    perception: C1PerceptionParams
    models: C1ModelsParams
    learning: C1LearningParams
    sensorium_c1: C1SensoriumParams
    digest: str

    def ref(self) -> str:
        return f"c1_perception_models@{self.digest[:16]}"


def load_c1_profile(
    c1_path: Path | None = None, m0_path: Path | None = None
) -> C1Profile:
    """加载并校验 C1 冻结 profile；先验/似然原料从 m0 冻结初始条件派生（Q-L04-11）。"""
    root = Path(__file__).resolve().parents[2] / "config" / "profiles"
    c1_path = c1_path or root / "c1_perception_models.profile.yaml"
    m0_path = m0_path or root / "m0_mw0.profile.yaml"
    doc = cast(dict[str, Any], yaml.safe_load(c1_path.read_text(encoding="utf-8")))
    header = cast(dict[str, Any], _need(doc, "profile"))
    if header["id"] != "c1_perception_models":
        raise C1ProfileViolation(f"not a c1_perception_models profile: {header['id']}")
    if str(header["version"]) != "v1.0":
        raise C1ProfileViolation(f"unexpected c1 profile version: {header['version']}")

    perception_doc = cast(dict[str, Any], _need(doc, "perception"))
    tabular = cast(dict[str, Any], _need(perception_doc, "tabular_fusion"))
    if str(_need(tabular, "learning_from_data")) != "forbidden":
        raise C1ProfileViolation("learning_from_data must be forbidden（Q-L03-03：C1 无学习）")

    models_doc = cast(dict[str, Any], _need(doc, "models"))
    world_doc = cast(dict[str, Any], _need(models_doc, "world_model"))
    rollout_doc = cast(dict[str, Any], _need(models_doc, "rollout"))
    self_doc = cast(dict[str, Any], _need(models_doc, "self_model"))
    if str(_need(models_doc, "cross_layer_normalization")) != "forbidden":
        raise C1ProfileViolation("cross_layer_normalization must be forbidden（Q-L09-08）")
    weights_raw = _need(models_doc, "error_layer_weights")
    weights = tuple(float(w) for w in cast(list[Any], weights_raw))
    if weights != (1.0, 1.0, 1.0):
        raise C1ProfileViolation("error_layer_weights must be 1:1:1（Q-L09-08 等权零参数）")

    learning_doc = cast(dict[str, Any], _need(doc, "learning"))
    if _need(learning_doc, "proposal_only") is not True:
        raise C1ProfileViolation("C1 learning must be proposal_only（L11 §9 C1 行：提案不生效只记录）")

    sensorium_doc = cast(dict[str, Any], _need(doc, "sensorium_c1"))
    calibration_doc = cast(dict[str, Any], _need(sensorium_doc, "calibration"))
    if str(_need(calibration_doc, "runtime_drift")) != "forbidden":
        raise C1ProfileViolation("calibration runtime_drift must be forbidden（Q-L02-01）")

    determinism_doc = cast(dict[str, Any], _need(doc, "determinism"))
    if str(_need(determinism_doc, "rng_operators")) != "none_c1":
        raise C1ProfileViolation("C1 operators must be RNG-free（rng_operators none_c1）")

    # 先验/似然原料：m0 冻结初始条件合同（Q-L04-11 / Q-L03-03 派生链）
    m0 = cast(dict[str, Any], yaml.safe_load(m0_path.read_text(encoding="utf-8")))
    m0_regimes = cast(dict[str, Any], _need(m0, "regimes"))
    initial_regime = str(_need(m0_regimes, "initial_regime"))
    initial_params = cast(dict[str, Any], _need(m0_regimes, initial_regime))
    prior_density = float(_need(initial_params, "resource_density"))
    observation = cast(dict[str, Any], _need(m0, "observation"))
    gain_raw = _need(observation, "gain_by_distance")
    gain = {str(k): float(v) for k, v in cast(dict[str, Any], gain_raw).items()}
    sigma = float(_need(observation, "render_noise_sigma"))

    edges = tuple(float(e) for e in cast(list[Any], _need(tabular, "bin_edges")))
    perception = C1PerceptionParams(
        believe_threshold=float(_need(perception_doc, "believe_threshold")),
        hypothesis_cap=int(_need(perception_doc, "hypothesis_cap")),
        collapse_confidence=float(_need(perception_doc, "collapse_confidence")),
        collapse_margin=float(_need(perception_doc, "collapse_margin")),
        collapse_tie=str(_need(perception_doc, "collapse_tie")),
        belief_reopenable=bool(_need(perception_doc, "belief_reopenable")),
        bin_edges=edges,
        prior_resource_density=prior_density,
        gain_by_distance=gain,
        render_noise_sigma=sigma,
        ood_rule=str(_need(perception_doc, "ood_rule")),
        abstain_form=str(_need(perception_doc, "abstain")),
        learning_from_data=str(tabular["learning_from_data"]),
        distance_metric=str(_need(perception_doc, "distance_metric")),
    )
    if not 0.0 < perception.believe_threshold < 1.0:
        raise C1ProfileViolation("believe_threshold must be in (0,1)")
    if perception.hypothesis_cap != int(world_doc["multi_hypothesis_cap"]):
        raise C1ProfileViolation("hypothesis_cap 与 world multi_hypothesis_cap 必须单值共用（Q-L03-05/Q-L04-02）")
    if len(edges) < 3 or any(b <= a for a, b in zip(edges, edges[1:])):
        raise C1ProfileViolation("bin_edges must be strictly increasing（≥3 边界）")

    models = C1ModelsParams(
        world_model_scope=str(_need(world_doc, "scope")),
        update_period_cycles=int(_need(world_doc, "update_period_cycles")),
        multi_hypothesis_cap=int(_need(world_doc, "multi_hypothesis_cap")),
        rollout_depth_max=int(_need(rollout_doc, "depth_max")),
        rollout_width_max=int(_need(rollout_doc, "width_max")),
        rollout_over_budget_prune=str(_need(rollout_doc, "over_budget_prune")),
        rollout_budget_in_checkpoint=bool(_need(rollout_doc, "budget_in_checkpoint")),
        self_error_dimensions=str(_need(self_doc, "error_dimensions")),
        tau_fast_cycles=int(_need(self_doc, "tau_fast_cycles")),
        tau_slow_cycles=int(_need(self_doc, "tau_slow_cycles")),
        error_layer_weights=weights,
        cross_layer_normalization="forbidden",
    )
    learning = C1LearningParams(
        online_step_cap=float(_need(learning_doc, "online_step_cap")),
        persistence=str(_need(learning_doc, "persistence")),
        proposal_only=True,
        neural_components=str(_need(learning_doc, "neural_components")),
    )
    if learning.online_step_cap <= 0.0 or learning.online_step_cap >= 1.0:
        raise C1ProfileViolation("online_step_cap must be in (0,1)（Q-L11-01：0.125）")
    sensorium_c1 = C1SensoriumParams(
        calibration_version=str(_need(calibration_doc, "version_id")),
        runtime_drift="forbidden",
        quality_scale=tuple(float(x) for x in cast(list[Any], _need(cast(dict[str, Any], _need(sensorium_doc, "quality")), "scale"))),  # type: ignore[arg-type]
        snr_est=str(_need(cast(dict[str, Any], _need(sensorium_doc, "quality")), "snr_est")),
        pred_error_feature_space=str(_need(sensorium_doc, "pred_error_feature_space")),
        precision_weighting=str(_need(sensorium_doc, "precision_weighting")),
    )
    return C1Profile(
        perception=perception,
        models=models,
        learning=learning,
        sensorium_c1=sensorium_c1,
        digest=content_digest(doc),
    )


def normal_cdf(x: float) -> float:
    """标准正态分布 Φ(x)（math.erf；Q-L03-03 似然表派生的唯一积分原语）。"""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
