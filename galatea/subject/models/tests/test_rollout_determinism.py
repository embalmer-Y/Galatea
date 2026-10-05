"""rollout 确定性测试（L04 §7：同 seed/深度 → 同轨迹集；Q-L04-01 预算裁剪）。"""
import pytest

from galatea.subject.models.rollout import run_rollout
from galatea.subject.models.ports import RolloutQuery
from galatea.subject.models.tests.conftest import world_with_observation


@pytest.fixture()
def belief():
    _, _, belief, _ = world_with_observation(7, 0.9)
    return belief


def test_same_query_bit_exact(belief):
    """同 (belief, query) 双跑 → 轨迹集逐位恒等（C1 确定性、可复算）。"""
    prof, _, _, _ = world_with_observation(7, 0.9)
    query = RolloutQuery(
        query_id="q1", action_sequence=(("move", "N"), ("forage", None), ("rest", None)),
        depth=3, width=2, purpose="test",
    )
    a = run_rollout(belief, query, prof, "set.a")
    b = run_rollout(belief, query, prof, "set.a")
    assert a.branches == b.branches
    assert a.depth == b.depth and a.width == b.width


def test_depth_clip_receipt(belief):
    """深度 > 8 → 确定性裁剪至 8 + CLIPPED 标记（Q-L04-01）。"""
    prof, _, _, _ = world_with_observation(7, 0.9)
    query = RolloutQuery(
        query_id="q.deep",
        action_sequence=tuple(("move", "N") for _ in range(10)),
        depth=10, width=2, purpose="test",
    )
    traj = run_rollout(belief, query, prof, "set.deep")
    assert traj.clipped is True
    assert traj.depth == 8
    assert all(len(br.steps) == 8 for br in traj.branches)


def test_width_clip_to_pose_hypotheses():
    """宽度 > 4 → 裁剪至 4 + CLIPPED；分支 = 位姿候选传播。"""
    prof, model, _, _ = world_with_observation(7, 0.9)
    # 先制造位姿歧义（3 次请求无回执 → 8 分支 → cap 4）
    model.update(11, (), (), (), requested_moves=("N", "E", "S"))
    belief = model.update(15, (), (), (), requested_moves=())
    query = RolloutQuery(query_id="q.w", action_sequence=(("rest", None),), depth=1, width=6, purpose="test")
    traj = run_rollout(belief, query, prof, "set.w")
    assert traj.clipped is True
    assert traj.width == 4
    assert len(traj.branches) == 4


def test_imagined_level_and_unknown_value(belief):
    """恒 IMAGINED；价值摘要 = typed Unknown（C1 无价值模型，L05 归 C2）。"""
    from galatea.kernel.unknown import Unknown

    prof, _, _, _ = world_with_observation(7, 0.9)
    query = RolloutQuery(query_id="q.lv", action_sequence=(("look", None),), depth=1, width=1, purpose="test")
    traj = run_rollout(belief, query, prof, "set.lv")
    assert traj.representation_level == "IMAGINED"
    assert isinstance(traj.value_summary, Unknown)


def test_move_semantics_consistent_with_world_model(belief):
    """rollout 位移语义与 world.py 动作合同同源：move N → position +（0,1）。"""
    prof, _, _, _ = world_with_observation(7, 0.9)
    query = RolloutQuery(query_id="q.mv", action_sequence=(("move", "N"),), depth=1, width=1, purpose="test")
    traj = run_rollout(belief, query, prof, "set.mv")
    pose = belief.pose_candidates[0]
    assert traj.branches[0].final_position == (pose.position[0], pose.position[1] + 1)
