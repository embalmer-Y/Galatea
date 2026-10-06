"""三控制器仲裁 + metacontrol 五元决策（Q-L09-01/02/03/04/07；L09 §4.1–4.4）。"""
from pathlib import Path

import pytest

from galatea.subject.action.controllers import (
    ControlProposal,
    ControllerKind,
    arbitrate_proposals,
    score_proposal,
)
from galatea.subject.action.metacontrol import (
    MetaControlState,
    MetaDecision,
    MetaTriggers,
    decide,
)
from galatea.subject.c3profile import load_c3_motivation_profile

ROOT = Path(__file__).resolve().parents[4]
PARAMS = load_c3_motivation_profile(ROOT / "config/profiles/c3_motivation.profile.yaml")


def _prop(pid: str, controller: str = ControllerKind.HABIT, goal: float = 0.5,
          cost: float = 0.3, affect: float = 0.4) -> ControlProposal:
    return ControlProposal(
        proposal_id=pid, controller=controller, action_class="move",
        goal_align=goal, confidence=0.7, cost=cost, expected_info_gain=0.2,
        affect_component=affect,
        rationale_refs=(f"r.{pid}",), predicted_outcome_ref=f"po.{pid}",
    )


# ------------------------------------------------------------ 评分与仲裁
def test_score_word_literal_negative_cost() -> None:
    """ω 评分：成本项字面负向（REV-0017 R3 钉死）——手算锚。

    _prop 分量 = (goal 0.5, conf 0.7, cost 0.5, info 0.2, affect 0.5)：
    factor=1.0 → (0.5+0.7−0.5+0.2+0.5)/5 = 0.28；factor=2.0 → (0.5+0.7−0.5+0.2+1.0)/5 = 0.38。
    """
    p = _prop("p", goal=0.5, cost=0.5, affect=0.5)
    assert abs(score_proposal(p, 1.0) - 0.28) < 1e-12
    assert abs(score_proposal(p, 2.0) - 0.38) < 1e-12


def test_affect_factor_passed_as_value_not_import() -> None:
    """affect_factor 由装配层以 float 传入（P03：action 域零 affect import——结构面）。

    台账消费函数（CONFIRMED 判定）属证据编排层（evidence/control）——此处钉死
    controllers.py 模块源零 affect 引用（test_no_execution_path 同型第二防线）。
    """
    import galatea.subject.action.controllers as ctrl_mod

    assert "affect" not in ctrl_mod.__dict__, "controllers 命名空间泄漏 affect 引用"
    # 因子值域由 C2 发放面构造强制；评分函数对越界值 clip（防御性收口）
    p = _prop("p", goal=0.5, cost=0.5, affect=0.5)
    assert abs(score_proposal(p, 1.0) - 0.28) < 1e-12
    assert abs(score_proposal(p, 99.0) - (0.5 + 0.7 - 0.5 + 0.2 + 1.0) / 5) < 1e-12


def test_arbitrate_tiebreak_rank_and_score() -> None:
    """tie-break (score desc, controller_rank, proposal_id)；落选留痕。"""
    a = _prop("a", controller=ControllerKind.MODEL_BASED, goal=0.9, cost=0.1)
    b = _prop("b", controller=ControllerKind.HABIT, goal=0.9, cost=0.1)
    winner, dropped = arbitrate_proposals((a, b), 1.0, 0)
    assert winner.proposal_id == "b"       # 同分 → HABIT 秩小优先（Q-L09-01④）
    assert ("a",) == tuple(d[0] for d in dropped) or dropped[0][0] == "a"


def test_disabled_controllers_rejected_at_construction() -> None:
    """启用电构造面强制：Reflex/Language 提案即拒（Q-L09-02②）。"""
    with pytest.raises(ValueError, match="not enabled at C3"):
        _prop("r", controller=ControllerKind.REFLEX)
    with pytest.raises(ValueError, match="not enabled at C3"):
        _prop("l", controller=ControllerKind.LANGUAGE)


def test_proposal_requires_rationale_and_outcome() -> None:
    """L09 §4.1 共同纪律：rationale_refs 非空 + predicted_outcome_ref。"""
    with pytest.raises(ValueError, match="rationale_refs"):
        ControlProposal(
            proposal_id="x", controller=ControllerKind.HABIT, action_class="look",
            goal_align=0.5, confidence=0.5, cost=0.5, expected_info_gain=0.5,
            affect_component=0.5, rationale_refs=(), predicted_outcome_ref="po")
    with pytest.raises(ValueError, match="predicted_outcome_ref"):
        ControlProposal(
            proposal_id="x", controller=ControllerKind.HABIT, action_class="look",
            goal_align=0.5, confidence=0.5, cost=0.5, expected_info_gain=0.5,
            affect_component=0.5, rationale_refs=("r",), predicted_outcome_ref="")


# ------------------------------------------------------------ 元决策
def test_meta_decision_full_order() -> None:
    """多触发全序 = SEEK_HELP > ABANDON > OBSERVE > THINK > ACT（REV-0017 R4）。"""
    all_on = MetaTriggers(
        capability_boundary_hit=True, loss_of_control=True, viability_critical=True,
        blocked_over_threshold=True, ood_or_abstain_event=True,
        conflict_unresolved=True, model_error_rising=True)
    assert decide(all_on) == "SEEK_HELP"
    assert decide(MetaTriggers(viability_critical=True, ood_or_abstain_event=True)) == "ABANDON"
    assert decide(MetaTriggers(ood_or_abstain_event=True, conflict_unresolved=True)) == "OBSERVE"
    assert decide(MetaTriggers(conflict_unresolved=True)) == "THINK"
    assert decide(MetaTriggers()) == "ACT"


def test_loss_of_control_constants_anchored() -> None:
    """触发常数锚定（Q-L09-03：L_c=16=4×T4 / band=0.1=2σ / 128=TTL/2 / 0.8 分级锚）。"""
    from galatea.subject.action.metacontrol import (
        BLOCKED_ABANDON_THRESHOLD, CRITICAL_ERROR, HELP_FREQUENCY_CAP_WINDOW,
        LOSS_OF_CONTROL_BAND, LOSS_OF_CONTROL_WINDOW,
    )
    assert LOSS_OF_CONTROL_WINDOW == 16 and LOSS_OF_CONTROL_WINDOW == 4 * 4
    assert LOSS_OF_CONTROL_BAND == PARAMS.affect_factor_bound[0] - 0.4 or LOSS_OF_CONTROL_BAND == 0.1
    assert BLOCKED_ABANDON_THRESHOLD == 128
    assert CRITICAL_ERROR == 0.8
    assert HELP_FREQUENCY_CAP_WINDOW == 64


def test_metacontrol_dwell_and_hysteresis() -> None:
    """驻留 4 拍 + 2 驻留窗累计确认（Q-L09-04；REV-0017 R4 滞回累计语义）——切换时序。"""
    st = MetaControlState(now_cycle=0)
    obs = MetaTriggers(ood_or_abstain_event=True)
    # 驻留期内（<4）不切
    for c in range(4):
        d, switched = st.step(obs, c)
        assert d == "ACT" and not switched
    # 驻留期满 + 第 1 确认窗（4//4=0）：pending 建立，仍 ACT
    d, switched = st.step(obs, 4)
    assert d == "ACT" and not switched
    # 第 2 确认窗（8//4=2 ≠ 0）：累计 2 窗 → 切换
    d, switched = st.step(obs, 8)
    assert d == "OBSERVE" and switched
    # 切换后驻留期：条件消失也不立即回切
    d, switched = st.step(MetaTriggers(), 9)
    assert d == "OBSERVE" and not switched
    # 条件解除跨 2 驻留窗（13、17）→ 回 ACT（累计制：13//4=3 一窗、17//4=4 二窗）
    _, _ = st.step(MetaTriggers(), 13)
    d, switched = st.step(MetaTriggers(), 17)
    assert d == "ACT" and switched
    assert st.digest() == st.digest()


def test_metacontrol_sparse_events_accumulate() -> None:
    """稀疏事件（每 8 拍 OOD）跨窗累计可切（连续制构造性不可切换的修正语义）。"""
    st = MetaControlState()
    # 注入拍 0（驻留内不切）、8、16：pending 自 8，16 落第二窗 → 切
    for c in range(0, 20):
        d, _ = st.step(MetaTriggers(ood_or_abstain_event=(c % 8 == 0)), c)
    assert d == "OBSERVE"


def test_seek_help_frequency_cap() -> None:
    """SEEK_HELP 频次帽 ≤1/64（Q-L09-07③）：第二次 64 拍内留痕不发送。"""
    st = MetaControlState()
    ok1, tag1 = st.request_help(10)
    ok2, tag2 = st.request_help(50)
    ok3, tag3 = st.request_help(80)
    assert ok1 and tag1 == "HELP_REQUESTED"
    assert not ok2 and tag2 == "HELP_CAP_EXCEEDED"
    assert ok3 and tag3 == "HELP_REQUESTED"    # 80−10 ≥ 64 → 解除
    assert st.digest() == st.digest()


def test_state_digest_changes_on_transition() -> None:
    """状态 digest 在切换处变化（checkpoint 载体——Q-L11-06）。"""
    st = MetaControlState()
    d0 = st.digest()
    st.step(MetaTriggers(ood_or_abstain_event=True), 4)
    st.step(MetaTriggers(ood_or_abstain_event=True), 8)
    assert st.digest() != d0
