"""P4-α 冻结 profile 的 typed 加载器（p4_alpha_brain.profile.yaml v1.0）。

INC-11 纪律：冻结 profile 必须有 typed loader 才可被运行时消费——缺键/类型错/
合同不符一律 fail closed（P4AlphaProfileViolation）。数值全部溯源：
- determinism 节 → Q-L13-20③（探针层A 配置即生产配置）+ Q-T02③ + Q-T10/Q-T11；
- probe_anchors 节 → Q-G00-15②（探针实测，ADR-G-0030 §2 规格）；
- world_model 节 → Q-L04-12①②③④（RSSM 式小尺度/双域训练/表格并存/主体平面输入）；
- training 节 → Q-L13-20①②④（录制格式 v1/权重工件/全批量）；
- evaluation 节 → 判据锚（held-out 比阈 0.1 = 探针实测 0.0083 的 12× 余量）+
  Q-L13-19④ prediction_scales。

torch 版本一致性校验：profile 钉死 torch_version（uv.lock 哈希锁定，Q-L13-20③），
运行时版本不符 = 环境漂移，fail closed——给定权重确定性合同的前提是机器面身份一致。
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import os

import torch
import yaml


class P4AlphaProfileViolation(ValueError):
    """冻结 profile 与合同不符（缺键/类型错/合同禁用项/环境漂移）——fail closed。"""


_PROFILE_DEFAULT = Path(__file__).resolve().parents[2] / "config" / "profiles" / "p4_alpha_brain.profile.yaml"

#: 训练会话录制格式 v1 十字段（Q-L13-20①；profile training.record_fields 原文）
RECORD_FIELDS_V1: tuple[str, ...] = (
    "master_seed", "init_seed", "data_digest", "weights_digest_before",
    "weights_digest_after", "loss_first", "loss_last", "optimizer", "lr", "epochs",
)


def _need(mapping: dict[str, Any], key: str) -> Any:
    value = mapping.get(key)
    if value is None:
        raise P4AlphaProfileViolation(f"profile key missing: {key}")
    return value


def _need_str(mapping: dict[str, Any], key: str, expected: str) -> str:
    value = _need(mapping, key)
    if value != expected:
        raise P4AlphaProfileViolation(f"profile key {key} = {value!r}, contract requires {expected!r}")
    return str(value)


def _resolve_torch_version(det: dict[str, Any]) -> str:
    """torch 版本设备维门（Q-T02 补裁③；P4-α/P4-β loader 共用）。

    两条放行路径，其余一律 fail closed：
    - CPU 路径：运行时 == 冻结 torch_version（锚历史延续）；
    - CUDA 路径：运行时 == device_certification.torch_version_cuda 且 status ==
      certified_cuda 且 CUBLAS_WORKSPACE_CONFIG == 冻结值（认证程序三项合同逐字校验）。
    """
    frozen = str(_need(det, "torch_version"))
    runtime = torch.__version__
    if runtime == frozen:
        return frozen
    cert_row = det.get("device_certification")
    if not isinstance(cert_row, dict):
        raise P4AlphaProfileViolation(
            f"torch runtime {runtime} != frozen {frozen}（无 device_certification 块——设备维未开放）")
    cert = cast(dict[str, Any], cert_row)
    cuda_version = str(_need(cert, "torch_version_cuda"))
    status = str(_need(cert, "status"))
    env_row = cert.get("cuda_env")
    env = cast(dict[str, Any], env_row) if isinstance(env_row, dict) else cast(dict[str, Any], {})
    cublas_frozen = str(env.get("CUBLAS_WORKSPACE_CONFIG")) if env else None
    if (runtime == cuda_version and status == "certified_cuda"
            and os.environ.get("CUBLAS_WORKSPACE_CONFIG") == cublas_frozen):
        return runtime
    raise P4AlphaProfileViolation(
        f"torch runtime {runtime} != frozen {frozen}"
        f"（cert={status}；认证路径需 certified_cuda + CUBLAS_WORKSPACE_CONFIG 冻结值）")


@dataclass(frozen=True, slots=True)
class P4AlphaBrainParams:
    """P4-α 脑核冻结参数（p4_alpha_brain.profile.yaml typed 视图）。"""

    # determinism（Q-L13-20③）
    torch_version: str
    num_threads: int
    use_deterministic_algorithms: bool
    default_dtype: str
    inference_double_run: str
    # probe_anchors（Q-G00-15②）
    probe_master_seed_hex: str
    init_seed: int
    probe_stream_digest: str
    probe_report_path: str
    probe_regression_test: str
    # world_model（Q-L04-12）
    architecture_family: str
    param_budget_min: int
    param_budget_max: int
    latent_dim: int
    deterministic_state_dim: int
    training_domains: tuple[str, ...]
    transfer_semantics: str
    input_plane: str
    table_baseline: str
    # training（Q-L13-20①②④）
    session_record_schema: str
    record_fields: tuple[str, ...]
    replay_criterion: str
    optimizer: str
    lr: float
    epochs: int
    full_batch_preferred: bool
    weights_as_artifacts: bool
    # evaluation（判据锚）
    heldout_margin_vs_persistence: float
    protocol: str
    ablation_selectivity: str


def load_p4_alpha_profile(path: Path | None = None) -> P4AlphaBrainParams:
    """fail-closed 加载 + 合同校验 + torch 运行时版本一致性核验。"""
    raw = cast(dict[str, Any],
               yaml.safe_load((path or _PROFILE_DEFAULT).read_text(encoding="utf-8")))
    if "profile" not in raw:
        raise P4AlphaProfileViolation("profile root missing")
    det = cast(dict[str, Any], _need(raw, "determinism"))
    anchors = cast(dict[str, Any], _need(raw, "probe_anchors"))
    wm = cast(dict[str, Any], _need(raw, "world_model"))
    tr = cast(dict[str, Any], _need(raw, "training"))
    ev = cast(dict[str, Any], _need(raw, "evaluation"))

    torch_version = _resolve_torch_version(det)
    num_threads = int(_need(det, "num_threads"))
    if num_threads != 1:
        raise P4AlphaProfileViolation(f"num_threads must be 1（Q-L13-20③ 位等价前提）, got {num_threads}")
    if _need(det, "use_deterministic_algorithms") is not True:
        raise P4AlphaProfileViolation("use_deterministic_algorithms must be true（Q-T02③）")
    default_dtype = _need_str(det, "default_dtype", "float32")
    inference_double_run = _need_str(det, "inference_double_run", "bit-exact")

    domains = tuple(str(d["id"]) for d in _need(wm, "training_domains"))
    if len(domains) != 2:
        raise P4AlphaProfileViolation(f"training_domains must be dual（Q-L04-12②）, got {domains}")
    record_fields = tuple(str(f) for f in _need(tr, "record_fields"))
    if record_fields != RECORD_FIELDS_V1:
        raise P4AlphaProfileViolation(
            f"record_fields must equal schema v1 ten fields（Q-L13-20①）, got {record_fields}")

    budget_min = int(_need(wm, "param_budget")[0])
    budget_max = int(_need(wm, "param_budget")[1])
    lr = float(_need(tr, "lr"))
    epochs = int(_need(tr, "epochs"))
    margin = float(_need(ev, "heldout_margin_vs_persistence"))
    if not 0.0 < margin < 1.0:
        raise P4AlphaProfileViolation(f"heldout margin must be in (0,1), got {margin}")

    return P4AlphaBrainParams(
        torch_version=torch_version,
        num_threads=num_threads,
        use_deterministic_algorithms=True,
        default_dtype=default_dtype,
        inference_double_run=inference_double_run,
        probe_master_seed_hex=str(_need(anchors, "master_seed_hex")),
        init_seed=int(_need(anchors, "init_seed")),
        probe_stream_digest=str(_need(anchors, "probe_stream_digest")),
        probe_report_path=str(_need(anchors, "probe_report")),
        probe_regression_test=str(_need(anchors, "probe_regression_test")),
        architecture_family=_need_str(wm, "architecture_family", "rssm_style"),
        param_budget_min=budget_min,
        param_budget_max=budget_max,
        latent_dim=int(_need(wm, "latent_dim")),
        deterministic_state_dim=int(_need(wm, "deterministic_state_dim")),
        training_domains=domains,
        transfer_semantics=str(_need(wm, "transfer_semantics")),
        input_plane=_need_str(wm, "input_plane", "subject_formed_frames_only"),
        table_baseline=_need_str(wm, "table_baseline", "coexist"),
        session_record_schema=_need_str(tr, "session_record_schema", "training_session.v1"),
        record_fields=record_fields,
        replay_criterion=str(_need(tr, "replay_criterion")),
        optimizer=_need_str(tr, "optimizer", "adam"),
        lr=lr,
        epochs=epochs,
        full_batch_preferred=bool(_need(tr, "full_batch_preferred")),
        weights_as_artifacts=bool(_need(tr, "weights_as_artifacts")),
        heldout_margin_vs_persistence=margin,
        protocol=str(_need(ev, "protocol")),
        ablation_selectivity=str(_need(ev, "ablation_selectivity")),
    )


# ---------------------------------------------------------------------------
# P4-β（p4_beta_mind.profile.yaml v1.1——草稿板/思维迭代/慢环 + GCTB 判据数值）
# ---------------------------------------------------------------------------

#: 草稿状态词表（Q-L07-09①；DraftStatus 对应面）
BETA_STATUS_VOCABULARY: tuple[str, ...] = ("open", "evaluated", "superseded", "contradicted")
#: 思维循环拍序（Q-L07-10①；ThoughtBeat 对应面）
BETA_LOOP_BEATS: tuple[str, ...] = ("generate", "evaluate", "contradict", "revise")


@dataclass(frozen=True, slots=True)
class P4BetaMindParams:
    """P4-β 心智扩展冻结参数（p4_beta_mind.profile.yaml typed 视图）。"""

    # determinism（Q-T02 补裁③）
    torch_version: str
    device_cert_status: str
    cublas_workspace_config: str
    num_threads: int
    use_deterministic_algorithms: bool
    inference_double_run: str
    # scratchpad（Q-L07-09）
    hypothesis_schema: str
    status_vocabulary: tuple[str, ...]
    non_belief_principle: bool
    # thought_iteration（Q-L07-10）
    loop_beats: tuple[str, ...]
    evaluate_source: str
    receipt: str
    think_steps_budget: int
    convergence_mode: str
    # slow_clock（Q-L09-11，v1.1 数值）
    triggers: tuple[str, ...]
    arousal_low: float
    urgency_idle: float
    check_interval_cycles: int
    # gctb 判据数值（Q-L13-21；stat plan v1.0 冻结同源）
    two_step_trials: int
    two_step_drift_prob: float
    two_step_reversal: int
    two_step_transition_common: float
    two_step_mb_alpha: float
    two_step_habit_alpha: float
    criterion_separation: float
    criterion_dominance: float
    optout_arms: int
    optout_true_p: tuple[float, float]
    optout_safe_harbor: float
    optout_trials: int
    think_first_budget_steps: int
    probe_report_path: str


def load_p4_beta_profile(path: Path | None = None) -> P4BetaMindParams:
    """P4-β profile fail-closed 加载（缺键/类型错/合同禁用项 = P4AlphaProfileViolation）。"""
    default = Path(__file__).resolve().parents[2] / "config" / "profiles" / "p4_beta_mind.profile.yaml"
    raw = cast(dict[str, Any], yaml.safe_load((path or default).read_text(encoding="utf-8")))
    if "profile" not in raw:
        raise P4AlphaProfileViolation("profile root missing")
    if str(_need(raw["profile"], "id")) != "p4_beta_mind":
        raise P4AlphaProfileViolation("profile id must be p4_beta_mind")

    det = cast(dict[str, Any], _need(raw, "determinism"))
    device_cert = cast(dict[str, Any], _need(det, "device_certification"))
    torch_version = _resolve_torch_version(det)
    num_threads = int(_need(det, "num_threads"))
    if num_threads != 1:
        raise P4AlphaProfileViolation(f"num_threads must be 1, got {num_threads}")
    if _need(det, "use_deterministic_algorithms") is not True:
        raise P4AlphaProfileViolation("use_deterministic_algorithms must be true（Q-T02③）")

    sp = cast(dict[str, Any], _need(raw, "scratchpad"))
    status_vocab = tuple(str(s) for s in _need(sp, "status_vocabulary"))
    if status_vocab != BETA_STATUS_VOCABULARY:
        raise P4AlphaProfileViolation(f"scratchpad status_vocabulary frozen, got {status_vocab}")
    if _need(sp, "non_belief_principle") is not True:
        raise P4AlphaProfileViolation("non_belief_principle must be true（Q-L07-09②）")

    ti = cast(dict[str, Any], _need(raw, "thought_iteration"))
    loop_beats = tuple(str(b) for b in _need(ti, "loop"))
    if loop_beats != BETA_LOOP_BEATS:
        raise P4AlphaProfileViolation(f"thought loop beat order frozen（Q-L07-10①）, got {loop_beats}")
    convergence_mode = _need_str(ti, "convergence_mode", "no_new_successor")
    budget = int(_need(ti, "think_steps_budget"))
    if budget < 1:
        raise P4AlphaProfileViolation("think_steps_budget must be ≥1")

    sc = cast(dict[str, Any], _need(raw, "slow_clock"))
    triggers = tuple(str(t) for t in _need(sc, "trigger"))
    if triggers != ("idle_cycle", "low_arousal"):
        raise P4AlphaProfileViolation(f"slow clock trigger set frozen（Q-L09-11①）, got {triggers}")
    arousal_low = float(_need(sc, "arousal_low"))
    if not 0.0 <= arousal_low <= 1.0:
        raise P4AlphaProfileViolation(f"arousal_low out of [0,1]: {arousal_low!r}")

    g = cast(dict[str, Any], _need(raw, "gctb"))
    ts = cast(dict[str, Any], _need(g, "two_step_task"))
    oo = cast(dict[str, Any], _need(g, "opt_out_metacognition"))
    tf = cast(dict[str, Any], _need(g, "think_first_advantage"))
    true_p = tuple(float(v) for v in _need(oo, "true_p_range"))
    if len(true_p) != 2:
        raise P4AlphaProfileViolation("optout true_p_range must be 2 arms")

    return P4BetaMindParams(
        torch_version=torch_version,
        device_cert_status=str(_need(device_cert, "status")),
        cublas_workspace_config=str(_need(device_cert, "cuda_env")["CUBLAS_WORKSPACE_CONFIG"]),
        num_threads=num_threads,
        use_deterministic_algorithms=True,
        inference_double_run=_need_str(det, "inference_double_run", "bit-exact"),
        hypothesis_schema=_need_str(sp, "hypothesis_schema", "DraftHypothesis"),
        status_vocabulary=status_vocab,
        non_belief_principle=True,
        loop_beats=loop_beats,
        evaluate_source=_need_str(ti, "evaluate_source", "rssm_imagine_rollout"),
        receipt=_need_str(ti, "receipt", "DraftThoughtReceipt"),
        think_steps_budget=budget,
        convergence_mode=convergence_mode,
        triggers=triggers,
        arousal_low=arousal_low,
        urgency_idle=float(_need(sc, "urgency_idle")),
        check_interval_cycles=int(_need(sc, "check_interval_cycles")),
    two_step_trials=int(_need(ts, "trials")),
    two_step_drift_prob=float(_need(ts, "drift_prob")),
    two_step_reversal=int(_need(ts, "reversal_at")),
        two_step_transition_common=float(_need(ts, "transition_common")),
        two_step_mb_alpha=float(_need(ts, "mb_alpha")),
        two_step_habit_alpha=float(_need(ts, "habit_alpha")),
        criterion_separation=float(str(_need(ts, "criterion_separation")).lstrip(">")),
        criterion_dominance=float(str(_need(ts, "criterion_dominance")).lstrip(">")),
        optout_arms=int(_need(oo, "arms")),
        optout_true_p=true_p,
        optout_safe_harbor=float(_need(oo, "safe_harbor")),
        optout_trials=int(_need(oo, "trials")),
        think_first_budget_steps=int(_need(tf, "budget_steps")),
        probe_report_path=str(_need(g, "probe_anchors")["probe_report"]),
    )
