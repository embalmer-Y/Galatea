"""世界信念表格更新测试（L04 §7 unit：表格更新规则可手算复核；Q-L04-02/Q-L04-09）。"""
import pytest

from galatea.subject.models.tests.conftest import perception_output, world_with_observation
from galatea.subject.models.world import WorldModel


def test_window_batch_updates_observed_cells():
    """T3 窗批：观测格后验并入占据图（evidence 引用 = 帧来源）。"""
    _, _, belief, out = world_with_observation(7, 0.9)
    pose = belief.pose_candidates[0]
    center = (pose.position[0] + 0, pose.position[1] + 0)
    cell = dict(belief.occupancy)[center]
    assert cell.posterior_present > 0.999
    assert cell.last_effective_time == 7
    assert cell.evidence_refs == (out.cells[0].evidence_frame_id,)


def test_persistence_for_unobserved_cells():
    """持续性语义（Q-L04-09①）：未观测格保持既有 posterior/时间戳不动。"""
    prof, model, belief, _ = world_with_observation(7, 0.9)
    first = dict(belief.occupancy)
    # 下一窗批：全零窗（资源消失）——只有本批观测格更新
    out2 = model.update(11, (), move_receipts=(), forage_receipts=(), requested_moves=())
    assert out2.t_eff == 11
    for cell, b in out2.occupancy:
        if b.last_effective_time != 11:
            assert first[cell] == b        # 未观测格：逐字段恒等（持续性）


def test_forage_success_event_conditions_own_cell():
    """事件条件更新（Q-L04-09②）：forage 成功回执 → 自在格后验 = 1.0（在场证据）。"""
    prof, model, _, _ = world_with_observation(7, 0.9)
    belief = model.update(
        11, (), move_receipts=(), forage_receipts=("forage_success_stored_1",),
        requested_moves=(),
    )
    own = dict(belief.occupancy)[(0, 0)]
    assert own.posterior_present == 1.0
    assert own.evidence_refs == ("forage_success_stored_1",)


def test_move_receipt_integration_dead_reckoning():
    """航位推算（Q-L04-08）：move_n_arrived → 位姿 +1 于 N=(0,+1) 动作合同方向。"""
    prof, model, _, _ = world_with_observation(7, 0.9)
    belief = model.update(
        11, (), move_receipts=("move_n_arrived",), forage_receipts=(),
        requested_moves=("N",),
    )
    assert belief.pose_candidates[0].position == (0, 1)
    assert belief.pose_candidates[0].orientation == "N"


def test_unreadable_receipt_integrates_per_contract():
    """回执不可读（传输损坏）→ 位移按动作合同积分 + typed Unknown 留痕（Q-L04-09③⁺：
    loss_rate=0 合同 + requested=effective——损坏非缺失，禁分支伪装不确定性）。"""
    prof, model, _, _ = world_with_observation(7, 0.9)
    belief = model.update(
        11, (), move_receipts=(), forage_receipts=(),
        requested_moves=("N", "N", "E"),
    )
    # 合同积分：N+N+E → 位移 (1, 2)
    assert belief.pose_candidates[0].position == (1, 2)
    assert len(belief.pose_candidates) == 1
    assert any("unreadable" in u.detail and "合同" in u.detail for u in belief.unknowns)


def test_blocked_receipt_no_branch():
    """blocked 回执 = 无位移不分支（Q-L04-09③）。"""
    prof, model, _, _ = world_with_observation(7, 0.9)
    belief = model.update(
        11, (), move_receipts=("move_n_blocked",), forage_receipts=(),
        requested_moves=("N",),
    )
    assert len(belief.pose_candidates) == 1
    assert belief.pose_candidates[0].position == (0, 0)


def test_pose_prune_deterministic():
    """超容量裁剪确定性（Q-L04-01 序：后验降序、tie id 升序）——双模型同输入恒等。"""
    prof, _, _, _ = world_with_observation(7, 0.9)
    m1 = WorldModel(prof, run_id="R")
    b1 = m1.update(7, (), (), (), requested_moves=("N", "E", "S", "W", "N"))
    m2 = WorldModel(prof, run_id="R")
    b2 = m2.update(7, (), (), (), requested_moves=("N", "E", "S", "W", "N"))
    assert b1.pose_candidates == b2.pose_candidates


def test_blocked_receipt_no_displacement_but_others_integrate():
    """blocked = 已解析无位移；同批可读回执正常积分（Q-L04-09③⁺ 语义分面）。"""
    prof, model, _, _ = world_with_observation(7, 0.9)
    belief = model.update(
        11, (), move_receipts=("move_n_blocked", "move_e_arrived"), forage_receipts=(),
        requested_moves=("N", "E"),
    )
    assert belief.pose_candidates[0].position == (1, 0)   # N blocked 无位移；E 到达
    assert len(belief.pose_candidates) == 1
    assert not belief.unknowns                             # 全部回执可读 → 无缺口


def test_observable_coverage_explicit():
    """部分可观察显式承载（L04 §4.1）：窗内 KNOWN / 陈旧 PARTIAL / 窗外 UNKNOWN。"""
    _, _, belief, _ = world_with_observation(7, 0.9)
    coverage = dict(belief.observable_coverage)
    assert coverage["occupancy_window"] == "KNOWN"
    assert coverage["occupancy_stale"] == "PARTIAL"
    assert coverage["occupancy_outside_window"] == "UNKNOWN"


def test_hypothesis_cap_enforced():
    """位姿候选 > 4 构造即拒（Q-L04-02 单值上限）。"""
    from galatea.subject.models.world import PoseCandidate, WorldStateBelief

    candidates = tuple(
        PoseCandidate(f"p{i}", (i, 0), "N", 0.1) for i in range(5)
    )
    with pytest.raises(ValueError):
        WorldStateBelief(
            belief_id="w", t_eff=0, pose_candidates=candidates, occupancy=(),
            observable_coverage=(), unknowns=(),
            transition_model_version="v", update_rule_version="v", cycle_id=0,
        )
