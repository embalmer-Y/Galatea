"""自述动机源测试（Q-L08-10：分箱冲动零新阈值 + 仲裁参与 + 最近格匹配）。"""
from galatea.subject.goals.arbitration import pareto_front, vector_of
from galatea.subject.goals.motives import MotiveSource
from galatea.subject.goals.report_motive import (
    bin_vector,
    nearest_corpus_state,
    report_urgency,
    self_report_motive,
)

# 语库 v0/v1 同 schema 的代表格（测试自持，不读文件）
_CORPUS = [
    {"energy": 0.9, "energy_trend": "steady", "integrity": 1.0, "current_goal": "forage", "valence": 0.1},
    {"energy": 0.5, "energy_trend": "falling", "integrity": 1.0, "current_goal": "rest", "valence": -0.4},
    {"energy": 1.0, "energy_trend": "steady", "integrity": 1.0, "current_goal": "none", "valence": 0.0},
]


def test_bin_vector_canonical() -> None:
    assert bin_vector({"energy": 0.9, "energy_trend": "rising", "integrity": 1.0,
                       "current_goal": "forage", "valence": 0.3}) == \
        ("e_high", "t_rising", "intact", "g_forage", "v_good")
    assert bin_vector({"energy": 0.3, "energy_trend": "falling", "integrity": 0.7,
                       "current_goal": "rest", "valence": -0.8}) == \
        ("e_verylow", "t_falling", "damaged", "g_rest", "v_bad")


def test_urgency_zero_when_unchanged_and_first_report_full() -> None:
    bins = ("e_mid", "t_steady", "intact", "g_none", "v_calm")
    assert report_urgency(bins, None) == (1.0, ("energy", "energy_trend", "integrity",
                                                "current_goal", "valence"))
    assert report_urgency(bins, bins) == (0.0, ())          # 零冲动
    urgency, changed = report_urgency(bins, ("e_low", "t_steady", "intact", "g_none", "v_calm"))
    assert urgency == 0.2 and changed == ("energy",)         # 单箱变化 = 1/5


def test_motive_none_when_unchanged() -> None:
    state = {"energy": 0.75, "energy_trend": "steady", "integrity": 1.0,
             "current_goal": "none", "valence": 0.0}
    bins = bin_vector(state)
    assert self_report_motive(state, bins, 5, "ref") is None      # 无变化无动机
    m = self_report_motive(state, None, 5, "ref")                 # 首言冲动
    assert m is not None and m.source_kind is MotiveSource.SELF_REPORT
    assert m.urgency == 1.0 and m.detail  # 首言：全五箱变化（detail = 变化字段表）


def test_self_report_participates_nonexclusively_in_front() -> None:
    """Pareto 非独占：SELF_REPORT（info 高）与觅食（viability 高）双非支配共存。"""
    m = self_report_motive({"energy": 0.75, "energy_trend": "falling", "integrity": 1.0,
                            "current_goal": "none", "valence": -0.2}, None, 1, "ref")
    assert m is not None
    cv = vector_of("self_report", m)
    assert cv.vector == (0.0, 0.0, m.urgency, 0.0, 0.5)           # info_value 载体
    front = pareto_front({"forage": (0.5, 0.0, 0.0, 0.0, 0.5),
                          "self_report": cv.vector})
    assert set(front) == {"forage", "self_report"}                 # 双共存 → 可同时胜出


def test_nearest_corpus_state_deterministic() -> None:
    state = {"energy": 0.72, "energy_trend": "steady", "integrity": 1.0,
             "current_goal": "none", "valence": 0.05}
    a = nearest_corpus_state(state, _CORPUS)
    b = nearest_corpus_state(state, _CORPUS)
    assert a == b and a["current_goal"] == "none"                   # 确定性 + 格匹配
    # 完全出格态（很低能量 + 很差效价）仍最近匹配（不崩不编造）
    far = nearest_corpus_state({"energy": 0.1, "energy_trend": "falling",
                                "integrity": 0.5, "current_goal": "rest", "valence": -0.9},
                               _CORPUS)
    assert far["current_goal"] == "rest"
