"""多未来 rollout（L04 §4.3/§10 rollout.py；恒 IMAGINED）。

C1 确定性展开（REV-0013 R3：无 RNG 算子——随机分支流预留按 Q-G00-10，C1 不注册
死流）：分支 = 位姿候选传播（width = 位姿假设数 ≤4）；转移 = 持续性 + 主体动作
合同语义（move 一步一格）+ 能力静态边界；深度 ≤8 / 宽度 ≤4（Q-L04-01），超预算
确定性裁剪（宽度优先后验降序、tie id 升序）+ 回执 CLIPPED。
输出恒 ImaginedTrajectory；价值摘要 C1 = typed Unknown（价值面归 L05 C2）；
rollout 不得生成 OwnedGoal/ActionIntention（L04 §8 禁写路径）。
"""
from galatea.kernel.unknown import Unknown, UnknownReason
from galatea.subject.c1profile import C1Profile
from galatea.subject.models.ports import (
    ImaginedTrajectory,
    RolloutBranch,
    RolloutQuery,
)
from galatea.subject.models.world import DIRECTION_VECTORS, PoseCandidate, WorldStateBelief


def run_rollout(
    belief: WorldStateBelief, query: RolloutQuery, profile: C1Profile, set_id: str
) -> ImaginedTrajectory:
    """确定性 rollout（同 (belief digest, query) → 同轨迹集，bit-exact 可复算）。"""
    depth_max = profile.models.rollout_depth_max
    width_max = profile.models.rollout_width_max
    clipped = False
    depth = min(query.depth, depth_max)
    if query.depth > depth_max:
        clipped = True
    width = min(query.width, width_max)
    if query.width > width_max:
        clipped = True

    # 分支 = 位姿候选（后验降序、tie id 升序取 width——Q-L04-01 裁剪序）
    poses = tuple(sorted(belief.pose_candidates, key=lambda p: (-p.posterior, p.candidate_id)))[:width]
    branches: list[RolloutBranch] = []
    for pose in poses:
        branches.append(_expand_branch(belief, query, pose, depth))
    uncertainty = [
        f"pose_candidates={len(belief.pose_candidates)}",
        f"coverage={dict(belief.observable_coverage).get('occupancy_outside_window', 'UNKNOWN')}",
    ]
    return ImaginedTrajectory(
        set_id=set_id,
        query_id=query.query_id,
        branches=tuple(branches),
        depth=depth,
        width=len(branches),
        value_summary=Unknown(
            reason=UnknownReason.DECISION_PATH_UNRESOLVED,
            evidence_refs=(belief.belief_id,),
            detail="C1 无价值模型（value_summary 归 L05 C2）——占位 Unknown 非零值",
            detected_by="models.rollout",
            virtual_time=belief.cycle_id,
        ),
        uncertainty=tuple(uncertainty),
        clipped=clipped,
    )


def _expand_branch(
    belief: WorldStateBelief, query: RolloutQuery, pose: PoseCandidate, depth: int
) -> RolloutBranch:
    """单分支确定性展开（转移语义与 world.py 同源：persistence + 动作合同）。"""
    position = pose.position
    orientation = pose.orientation
    steps: list[tuple[int, str, str, tuple[int, int]]] = []
    for offset, (primitive, param) in enumerate(query.action_sequence[:depth]):
        if primitive == "move" and param in DIRECTION_VECTORS:
            dx, dy = DIRECTION_VECTORS[param]
            position = (position[0] + dx, position[1] + dy)
            orientation = param
        # 非 move 原语：占据持续性（C1 无生成式转移——Q-L04-09① 禁模拟隐藏过程）
        steps.append((offset, f"{primitive}{':' + param if param else ''}", orientation, position))
    return RolloutBranch(
        branch_id=f"{query.query_id}.{pose.candidate_id}",
        pose_ref=pose.candidate_id,
        steps=tuple(steps),
        final_position=position,
    )
