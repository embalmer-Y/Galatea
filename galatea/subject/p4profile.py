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

    torch_version = _need_str(det, "torch_version", torch.__version__)
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
