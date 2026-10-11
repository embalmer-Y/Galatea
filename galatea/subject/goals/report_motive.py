"""自述动机源（Q-L08-10，P3 单元 E——发声时机成为主体内生决策）。

零新阈值纪律的最强形态：冲动强度 = 语库分箱变化比例（分箱 = Q-L12-09 冻结格，
与 v0 渲染器同箱）；无变化 = 无动机。发声 = 动作（胜出后 L4 播放冻结 WAV）。
"""
from __future__ import annotations

from typing import cast

from galatea.subject.goals.motives import Motive, MotiveSource

__all__ = [
    "bin_vector",
    "nearest_corpus_state",
    "report_urgency",
    "self_report_motive",
]

# 与 v0 渲染器（scripts/p3_first_words.render_template_v0）同箱——单一分箱事实源
ENERGY_BINS: tuple[tuple[float, str], ...] = (
    (0.8, "e_high"), (0.6, "e_mid"), (0.4, "e_low"), (0.0, "e_verylow"))
TREND_BINS: dict[str, str] = {"rising": "t_rising", "steady": "t_steady",
                              "falling": "t_falling"}
GOAL_BINS: dict[str, str] = {"forage": "g_forage", "rest": "g_rest", "none": "g_none"}
VALENCE_BINS: tuple[tuple[float, str], ...] = (
    (0.2, "v_good"), (-0.2, "v_calm"), (-0.5, "v_uneasy"), (-10.0, "v_bad"))
_BIN_FIELDS: tuple[str, ...] = ("energy", "energy_trend", "integrity", "current_goal", "valence")


def bin_energy(energy: float) -> str:
    value = float(energy)
    for threshold, label in ENERGY_BINS:
        if value >= threshold:
            return label
    return ENERGY_BINS[-1][1]


def bin_valence(valence: float) -> str:
    value = float(valence)
    for threshold, label in VALENCE_BINS:
        if value >= threshold:
            return label
    return VALENCE_BINS[-1][1]


def bin_vector(state: dict[str, object]) -> tuple[str, str, str, str, str]:
    """连续内部态 → 语库分箱五元组（canonical；与渲染器同箱——Q-L08-10②）。"""
    return (
        bin_energy(float(cast("float", state["energy"]))),
        TREND_BINS[str(state["energy_trend"])],
        "intact" if float(cast("float", state["integrity"])) >= 1.0 else "damaged",
        GOAL_BINS[str(state["current_goal"])],
        bin_valence(float(cast("float", state["valence"]))),
    )


def report_urgency(current: tuple[str, str, str, str, str],
                   last_reported: tuple[str, str, str, str, str] | None,
                   ) -> tuple[float, tuple[str, ...]]:
    """(urgency, 变化字段)。首次自述（last=None）= 全变化（urgency 1.0——首言冲动）；
    无变化 = (0.0, ())——零冲动不产动机（Q-L08-10②）。"""
    if last_reported is None:
        return 1.0, _BIN_FIELDS
    changed = tuple(f for f, a, b in zip(_BIN_FIELDS, current, last_reported) if a != b)
    return (len(changed) / 5.0, changed)


def nearest_corpus_state(state: dict[str, object],
                         corpus_states: list[dict[str, object]],
                         ) -> dict[str, object]:
    """语库格最近匹配（确定性：先按五箱全等，再按箱距离 + 数值距离字典序）。"""
    target = bin_vector(state)
    energy_now = float(cast("float", state["energy"]))
    valence_now = float(cast("float", state["valence"]))

    def distance(cs: dict[str, object]) -> tuple[int, float]:
        bins = bin_vector(cs)
        bin_dist = sum(1 for a, b in zip(target, bins) if a != b)
        num_dist = (abs(float(cast("float", cs["energy"])) - energy_now)
                    + abs(float(cast("float", cs["valence"])) - valence_now))
        return (bin_dist, round(num_dist, 6))
    ranked = sorted(corpus_states, key=lambda cs: (distance(cs), json_key(cs)))
    return dict(ranked[0])


def json_key(cs: dict[str, object]) -> str:
    import json
    return json.dumps(cs, sort_keys=True, ensure_ascii=False)


def self_report_motive(state: dict[str, object],
                       last_reported: tuple[str, str, str, str, str] | None,
                       cycle: int, evidence_ref: str) -> Motive | None:
    """自述动机生产（Q-L08-10：无变化 = None；变化 = urgency 比例动机）。"""
    urgency, changed = report_urgency(bin_vector(state), last_reported)
    if urgency <= 0.0:
        return None
    return Motive(
        source_kind=MotiveSource.SELF_REPORT,
        urgency=urgency,
        evidence_refs=(evidence_ref, *(f"changed:{f}" for f in changed)),
        ts=cycle,
        detail=",".join(changed) if changed else "first_report",
    )
