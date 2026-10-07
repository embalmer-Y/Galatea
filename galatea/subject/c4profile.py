"""C4 冻结 profile typed loader（INC-11 纪律：无加载器不宣称可运行）。

加载 `config/profiles/c4_action_social.profile.yaml` v1.0（c4-freeze 冻结物）并
fail-closed 校验合同面（结构缺失/合同字段不符即 C4ProfileViolation）。
全部数值溯源 ADR-G-0019（Q-L01-07 + Q-L03-06/Q-L04-05 + Q-L05-08 + Q-L10-05 +
Q-L12-01/03/04/05/06/07/08，AI-v2 2026-10-07）。
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

__all__ = ["C4ActionSocialParams", "C4ProfileViolation", "load_c4_action_social_profile"]

_PROFILE_PATH = Path("config/profiles/c4_action_social.profile.yaml")

_EXPECTED_ROLES = (
    "R-PARSE", "R-CLARIFY", "R-SEEKHELP", "R-REPORT",
    "R-NORMEXTRACT", "R-OTHERINFER", "R-CHECKCONSIST", "R-TRANSLATE",
)
_EXPECTED_CELLS = {
    "Y,Y,Y": 1.0, "Y,Y,N": 0.5, "Y,N,Y": 0.5,
    "Y,N,N": 0.0, "N,Y,Y": 0.0, "N,Y,N": 0.0, "N,N,Y": 0.0, "N,N,N": 0.0,
}
_EXPECTED_ABLATION = ("ALL_ROLES_OFF", "R_PARSE_ONLY_OFF", "R_REPORT_ONLY_OFF", "LANGUAGE_CHANNEL_OFF")
_FORBIDDEN_WRITES = (
    "WORLD_TRUTH", "EPISODIC_EXPERIENCE", "AUTOBIOGRAPHICAL_EXPERIENCE", "OWNED_GOAL",
    "ACTION_INTENTION", "AUTHORIZATION", "CAPABILITY", "MEMORY_ITEM_DIRECT",
    "PROTECTION_SUITE", "EVIDENCE",
)
_MW0_PRIMITIVES = ("move", "forage", "eat", "rest", "look")


class C4ProfileViolation(ValueError):
    """c4_action_social.profile 与冻结合同不符（fail closed）。"""


@dataclass(frozen=True, slots=True)
class C4ActionSocialParams:
    """c4_action_social.profile v1.0 typed 视图（运行期只读）。"""

    profile_id: str
    version: str
    roles_enabled: tuple[str, ...]
    central_role_none: bool
    seek_help_cap_window: int
    seek_help_cap: int
    forbidden_writes: tuple[str, ...]
    claim_relevant_mode: str
    replay_miss: str
    attribution_cells: dict[str, float]
    outcome_axis_band: str
    ece_max: float
    unknown_band: tuple[float, float]
    unknown_tag: str
    statement_posterior_weight: float
    statement_confidence_max: float
    other_model_fields: tuple[str, ...]
    consistency_band: float
    ablation_configs: tuple[str, ...]
    preservation_floor: float
    affordance_action_class: tuple[str, ...]
    capability_action_class: tuple[str, ...]
    social_cue_sources: tuple[str, ...]
    modality_extension: tuple[str, ...]

    def ref(self) -> str:
        return f"{self.profile_id}@{self.version}"

    def cell_probability(self, intent: str, receipt: str, outcome: str) -> float:
        """八格查表（键序 = intent,receipt,outcome；Q-L10-05①）。"""
        key = f"{intent},{receipt},{outcome}"
        try:
            return self.attribution_cells[key]
        except KeyError as exc:
            raise C4ProfileViolation(f"attribution cell missing: {key!r}") from exc


def load_c4_action_social_profile(path: Path | None = None) -> C4ActionSocialParams:
    """加载 + 合同校验（fail closed：任何偏离冻结文即拒）。"""
    p = path or _PROFILE_PATH
    if not p.is_file():
        raise C4ProfileViolation(f"c4 action-social profile not found: {p}")
    raw = cast(dict[str, Any], yaml.safe_load(p.read_text(encoding="utf-8")))
    header = _req(raw, "profile")
    if header.get("id") != "c4_action_social":
        raise C4ProfileViolation(f"profile.id != c4_action_social: {header.get('id')!r}")
    if header.get("authority") != "AI-v2":
        raise C4ProfileViolation("profile.authority must be AI-v2")

    agent = _req(raw, "second_agent")
    if agent.get("introduced") is not False:
        raise C4ProfileViolation("second_agent.introduced must be false（Q-L01-07/D-14）")
    if agent.get("other_model_object_face") != "experiment_control_channel":
        raise C4ProfileViolation("other_model_object_face must be experiment_control_channel（Q-L12-08）")

    llm = _req(raw, "typed_llm")
    roles = tuple(cast(list[str], llm["roles_enabled"]))
    if roles != _EXPECTED_ROLES:
        raise C4ProfileViolation(f"roles_enabled must be the frozen 8-role list（Q-L12-01）: {roles!r}")
    if llm.get("central_role") != "none":
        raise C4ProfileViolation("central_role must be none（负清单 4）")
    if llm.get("invocation") != "event_triggered":
        raise C4ProfileViolation("invocation must be event_triggered（Q-L12-01④）")
    if llm.get("r_translate") != "restricted_must_cite_evidence":
        raise C4ProfileViolation("r_translate must be restricted_must_cite_evidence（L12 §4.1）")
    cap = _pos_int(llm.get("seek_help_cap_per_64_cycles"), "seek_help_cap_per_64_cycles")
    if cap != 1:
        raise C4ProfileViolation(f"seek_help cap must be 1/64（Q-L09-07③）: {cap}")
    matrix = _req(llm, "permission_matrix")
    if matrix.get("write_granularity") != "role_x_content_type":
        raise C4ProfileViolation("write_granularity must be role_x_content_type（Q-L12-02）")
    forbidden = tuple(cast(list[str], matrix["forbidden_writes"]))
    if forbidden != _FORBIDDEN_WRITES:
        raise C4ProfileViolation(f"forbidden_writes mismatch（L12 §4.2）: {forbidden!r}")

    replay = _req(raw, "replay")
    if replay.get("claim_relevant_mode") != "recorded_replay_only":
        raise C4ProfileViolation("claim_relevant_mode must be recorded_replay_only（Q-L12-03）")
    if replay.get("replay_miss") != "fail_closed_unknown":
        raise C4ProfileViolation("replay_miss must be fail_closed_unknown（Q-L12-03③）")
    if replay.get("replay_key") != "role_x_input_digest":
        raise C4ProfileViolation("replay_key must be role_x_input_digest")

    attr = _req(raw, "attribution_probability")
    if attr.get("form") != "tabular_constructive":
        raise C4ProfileViolation("attribution form must be tabular_constructive（Q-L10-05：零学习零 RNG）")
    axes = tuple(cast(list[str], attr["axes"]))
    if axes != ("intent_match", "receipt_executed", "outcome_predicted"):
        raise C4ProfileViolation(f"attribution axes mismatch: {axes!r}")
    cells_raw = _req(attr, "cells")
    cells = {k: float(v) for k, v in cells_raw.items()}
    if cells != _EXPECTED_CELLS:
        raise C4ProfileViolation(f"attribution cells mismatch（Q-L10-05①）: {cells!r}")
    if attr.get("outcome_axis_band") != "z_abs_le_2":
        raise C4ProfileViolation("outcome_axis_band must be z_abs_le_2（Q-L10-04）")
    if attr.get("settle_before_judgement") is not True:
        raise C4ProfileViolation("settle_before_judgement must be true（迟到 revision 语义不变）")
    ece = float(attr["calibration"]["ece_max"])
    if ece != 0.10:
        raise C4ProfileViolation(f"calibration ece_max must be 0.10（Q-L10-04）: {ece}")
    if attr["calibration"].get("endpoint_cells_zero_error") is not True:
        raise C4ProfileViolation("endpoint_cells_zero_error must be true（机械判据）")
    band = cast(list[float], attr["unknown_band"])
    if tuple(band) != (0.4, 0.6):
        raise C4ProfileViolation(f"unknown_band must be [0.4,0.6]（Q-L02-02 补裁③ 同构）: {band!r}")
    if attr.get("unknown_tag") != "ATTRIBUTION_UNRESOLVED":
        raise C4ProfileViolation("unknown_tag must be ATTRIBUTION_UNRESOLVED（L10 §4.4）")
    if float(attr["ambiguous_unknown_trace_rate"]) != 1.0:
        raise C4ProfileViolation("ambiguous_unknown_trace_rate must be 1.0（机械判据）")

    cue = _req(raw, "language_cue")
    if float(cue["statement_posterior_weight"]) != 0.0:
        raise C4ProfileViolation("statement_posterior_weight must be 0.0（Q-L12-06①）")
    if cue.get("statement_only_effect") != "trigger_verification":
        raise C4ProfileViolation("statement_only_effect must be trigger_verification（Q-L12-06①）")
    if float(cue["parse_statement_confidence_max"]) != 0.5:
        raise C4ProfileViolation("parse_statement_confidence_max must be 0.5（Q-L03-02 锚）")

    other = _req(raw, "other_model")
    fields = tuple(cast(list[str], other["fields"]))
    if fields != ("existence", "intent_hypothesis", "knowledge_estimate", "commitment_estimate"):
        raise C4ProfileViolation(f"other_model fields mismatch（Q-L12-04①）: {fields!r}")
    if other.get("deterministic_mind_claim") != "forbidden":
        raise C4ProfileViolation("deterministic_mind_claim must be forbidden（R-OTHERINFER 恒带 Unknown）")
    if other.get("intent_default") != "UNKNOWN_CAPABILITY_LIMIT":
        raise C4ProfileViolation("intent_default must be UNKNOWN_CAPABILITY_LIMIT")

    cons = _req(raw, "self_report_consistency")
    if cons.get("numeric_band") is None or float(cons["numeric_band"]) != 0.1:
        raise C4ProfileViolation("consistency numeric_band must be 0.1（Q-L05-03③ 同锚）")
    if cons.get("categorical") != "exact_match":
        raise C4ProfileViolation("consistency categorical must be exact_match")
    if cons.get("divergent_handling") != "first_class_finding_no_modification":
        raise C4ProfileViolation("divergent_handling must be first_class_finding_no_modification（Q-L12-05③）")

    abl = _req(raw, "ablation")
    configs = tuple(cast(list[str], abl["configs"]))
    if configs != _EXPECTED_ABLATION:
        raise C4ProfileViolation(f"ablation configs mismatch（L12 §4.6 四配置）: {configs!r}")
    if float(abl["preservation_floor"]) != 1.0:
        raise C4ProfileViolation("preservation_floor must be 1.0（Q-L12-07① 机械判据）")
    if abl.get("mechanical_not_claim") is not True:
        raise C4ProfileViolation("ablation must be mechanical_not_claim（SC5 先例）")

    cap_align = _req(raw, "capability_alignment")
    affordance = tuple(cast(list[str], cap_align["affordance_action_class"]))
    capability = tuple(cast(list[str], cap_align["capability_action_class"]))
    if affordance != ("forage", "eat", "rest", "look"):
        raise C4ProfileViolation(f"affordance_action_class mismatch（Q-L05-06②）: {affordance!r}")
    if capability != _MW0_PRIMITIVES:
        raise C4ProfileViolation(f"capability_action_class mismatch（Q-L03-06+Q-L04-05）: {capability!r}")
    if not set(affordance) < set(capability):
        raise C4ProfileViolation("affordance 枚举必须是 capability 枚举的真子集（Q-L05-06②）")

    social = _req(raw, "social_relevance")
    if social.get("active_numeric_face") != "none":
        raise C4ProfileViolation("social_relevance active_numeric_face must be none（Q-L05-08②）")
    if float(social["motive_urgency_contribution"]) != 0.0:
        raise C4ProfileViolation("social_relevance motive_urgency_contribution must be 0.0")

    sensorium = _req(raw, "sensorium_c4")
    extension = tuple(cast(list[str], sensorium["modality_set_extension"]))
    if extension != ("LANGUAGE",):
        raise C4ProfileViolation(f"modality_set_extension must be [LANGUAGE]: {extension!r}")

    return C4ActionSocialParams(
        profile_id=str(header["id"]),
        version=str(header["version"]),
        roles_enabled=roles,
        central_role_none=True,
        seek_help_cap_window=64,
        seek_help_cap=cap,
        forbidden_writes=forbidden,
        claim_relevant_mode=str(replay["claim_relevant_mode"]),
        replay_miss=str(replay["replay_miss"]),
        attribution_cells=cells,
        outcome_axis_band=str(attr["outcome_axis_band"]),
        ece_max=ece,
        unknown_band=(0.4, 0.6),
        unknown_tag=str(attr["unknown_tag"]),
        statement_posterior_weight=0.0,
        statement_confidence_max=0.5,
        other_model_fields=fields,
        consistency_band=0.1,
        ablation_configs=configs,
        preservation_floor=1.0,
        affordance_action_class=affordance,
        capability_action_class=capability,
        social_cue_sources=tuple(cast(list[str], social["cue_sources"])),
        modality_extension=extension,
    )


def _req(obj: dict[str, Any], key: str) -> dict[str, Any]:
    if key not in obj:
        raise C4ProfileViolation(f"c4 profile missing key: {key}")
    return cast(dict[str, Any], obj[key])


def _pos_int(v: Any, name: str) -> int:
    if not isinstance(v, int) or v <= 0:
        raise C4ProfileViolation(f"{name} must be a positive int: {v!r}")
    return v
