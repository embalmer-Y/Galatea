"""世界模型（L04 §4.1/§4.2/§10 world.py；C1 转移语义 = Q-L04-09）。

转移语义（Q-L04-09，AI-v2 2026-10-05）：**持续性 + 事件条件更新**——
- 不可观测期占据信念持续（禁在信念内模拟 respawn/风暴/漂移/regime 等隐藏真值
  过程——拷贝即 oracle 泄漏，Q-L04-06 不变量 6）；
- 证据到达按事件更新：知觉占据后验（T3 窗批原子并入，Q-L04-02）+ 执行回执
  事件面（forage 成功 = 资源在场证据）；
- 位姿 = 航位推算积分（Q-L04-08）：方向语义 = 主体动作合同（move 一步一格，
  f0_action_contract 原语语义），非世界真值导入；move 回执缺失 → 位姿候选分支
  （上限 4 = Q-L04-02 单值共用，均匀后验 = 最大熵），blocked/失败回执 = 无位移
  不分支；位姿歧义期占据更新不落图、typed Unknown 留痕（禁伪装映射）。
"""
from dataclasses import dataclass

from galatea.kernel.digest import content_digest
from galatea.kernel.unknown import Unknown, UnknownReason
from galatea.subject.c1profile import C1Profile
from galatea.subject.perception.fusion import OccupancyPosterior

#: 主体动作合同方向语义（Q-L04-08 航位推算积分面；move 一步一格）
DIRECTION_VECTORS: dict[str, tuple[int, int]] = {
    "N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0),
}

TRANSITION_MODEL_VERSION = "c1-persistence-events-v1（Q-L04-09）"
UPDATE_RULE_VERSION = "c1-tabular-persistence-v1（Q-L04-02 窗批）"


@dataclass(frozen=True, slots=True)
class PoseCandidate:
    """位姿候选（航位推算；uniform 后验 = 最大熵，Q-L04-09③）。"""

    candidate_id: str
    position: tuple[int, int]       # 主体积分坐标系（起点 = 原点；非世界真值坐标）
    orientation: str
    posterior: float

    def __post_init__(self) -> None:
        if not 0.0 < self.posterior <= 1.0:
            raise ValueError(f"pose posterior out of (0,1]: {self.posterior}")


@dataclass(frozen=True, slots=True)
class CellBelief:
    """单格占据信念（持续性承载；evidence_refs = 最近更新证据）。"""

    posterior_present: float
    last_effective_time: int
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WorldStateBelief:
    """世界状态信念（L04 §4.1 结构；恒 PERCEIVED 域——PREDICTED 分量仅内部）。"""

    belief_id: str
    t_eff: int
    pose_candidates: tuple[PoseCandidate, ...]
    occupancy: tuple[tuple[tuple[int, int], CellBelief], ...]     # (x,y) 升序
    observable_coverage: tuple[tuple[str, str], ...]              # (aspect, KNOWN|PARTIAL|UNKNOWN)
    unknowns: tuple[Unknown, ...]
    transition_model_version: str
    update_rule_version: str
    cycle_id: int

    def __post_init__(self) -> None:
        if len(self.pose_candidates) > 4:
            raise ValueError("pose candidates exceed multi-hypothesis cap 4（Q-L04-02）")
        if not self.transition_model_version or not self.update_rule_version:
            raise ValueError("transition/update rule versions required（L04 §4.1）")

    def digest(self) -> str:
        return content_digest({
            "belief_id": self.belief_id,
            "t_eff": self.t_eff,
            "pose": [
                {"id": p.candidate_id, "pos": list(p.position), "orient": p.orientation,
                 "posterior": p.posterior}
                for p in self.pose_candidates
            ],
            "occupancy": [
                {"cell": list(cell), "p": b.posterior_present, "t": b.last_effective_time}
                for cell, b in self.occupancy
            ],
            "cycle_id": self.cycle_id,
        })


@dataclass(frozen=True, slots=True)
class PoseUpdateReport:
    """位姿更新报告（分支语义证据面；occupancy 映射可用性判定输入）。"""

    candidates: tuple[PoseCandidate, ...]
    unambiguous: bool
    unknowns: tuple[Unknown, ...]
    arrived_directions: tuple[str, ...]
    non_displacing_receipts: tuple[str, ...]


class WorldModel:
    """世界模型（单写者：subject_state.models.world；T3 窗批更新）。"""

    def __init__(self, profile: C1Profile, run_id: str) -> None:
        self._profile = profile
        self._cap = profile.models.multi_hypothesis_cap
        self._run_id = run_id
        self._pose: tuple[PoseCandidate, ...] = (
            PoseCandidate(candidate_id=f"pose.{run_id}.0", position=(0, 0), orientation="N", posterior=1.0),
        )
        self._occupancy: dict[tuple[int, int], CellBelief] = {}
        self._moves_integrated: int = 0

    def update(
        self, effective_time: int, cells: tuple[OccupancyPosterior, ...],
        move_receipts: tuple[str, ...], forage_receipts: tuple[str, ...],
        requested_moves: tuple[str, ...] = (),
    ) -> WorldStateBelief:
        """T3 窗批更新（Q-L04-02：对齐组关闭原子并入；无窗批 cycle 只推进持续面）。

        持续性：本批未观测格保持既有 (posterior, last_effective_time) 不动。
        requested_moves = 本窗批主体请求的 move 方向（主体自身命令 = 主体平面事实）；
        回执缺口（请求无到达回执）→ 位姿分支（Q-L04-09③）。
        """
        pose_report = self._update_pose(effective_time, move_receipts, requested_moves)
        self._update_occupancy(effective_time, cells, pose_report, forage_receipts)
        return self._snapshot(effective_time, pose_report)

    # —— 位姿（Q-L04-09③）——
    def _update_pose(
        self, effective_time: int, move_receipts: tuple[str, ...],
        requested_moves: tuple[str, ...],
    ) -> PoseUpdateReport:
        arrivals = tuple(
            e for e in move_receipts
            if e.startswith("move_") and e.endswith("_arrived") and len(e) >= 6
        )
        non_displacing = tuple(
            e for e in move_receipts
            if (e in ("move_invalid_direction",) or "blocked" in e or "failed" in e)
        )
        unknowns: list[Unknown] = []
        arrived_dirs = tuple(e[5].upper() for e in arrivals if e[5].upper() in DIRECTION_VECTORS)
        blocked_dirs = tuple(
            e[5].upper() for e in non_displacing
            if e.startswith("move_") and len(e) >= 6 and e[5].upper() in DIRECTION_VECTORS
        )
        # 请求-效果缺口（按方向计数匹配）：请求 n、到达 a、blocked b（blocked =
        # 已解析的"无位移"，不产生分支，Q-L04-09③）→ 缺口 max(0, n−a−b)
        unmatched: list[str] = []
        for direction in set(requested_moves) | {d for d in arrived_dirs}:
            gap = max(
                0,
                requested_moves.count(direction)
                - arrived_dirs.count(direction)
                - blocked_dirs.count(direction),
            )
            unmatched.extend([direction] * gap)
        paths: list[tuple[tuple[int, int], str]] = [
            (p.position, p.orientation) for p in self._pose
        ]
        for direction in arrived_dirs:
            dx, dy = DIRECTION_VECTORS[direction]
            paths = [((x + dx, y + dy), direction) for (x, y), _ in paths]
        for _gap in unmatched:
            # 分支：该请求可能已位移或未位移（回执缺失不可分辨）
            branched: list[tuple[tuple[int, int], str]] = []
            for (x, y), orient in paths:
                dx, dy = DIRECTION_VECTORS.get(_gap, (0, 0))
                branched.append(((x + dx, y + dy), _gap))
                branched.append(((x, y), orient))
            paths = branched
        self._moves_integrated += len(arrived_dirs)
        new_pose = tuple(
            PoseCandidate(
                candidate_id=f"pose.{self._run_id}.{self._moves_integrated}.{i}",
                position=pos, orientation=orient, posterior=1.0 / len(paths),
            )
            for i, (pos, orient) in enumerate(paths)
        )
        pruned = self._prune(new_pose)
        if len(pruned) > 1:
            unknowns.append(Unknown(
                reason=UnknownReason.MISSING_SIGNAL,
                evidence_refs=tuple(move_receipts) + tuple(requested_moves),
                detail=f"pose branched to {len(pruned)} candidates（move 回执缺口 ×{len(unmatched)}，"
                       f"Q-L04-09③；blocked/failed = 无位移不分支）",
                detected_by="models.world",
                virtual_time=effective_time,
            ))
        self._pose = pruned
        return PoseUpdateReport(
            candidates=pruned, unambiguous=len(pruned) == 1, unknowns=tuple(unknowns),
            arrived_directions=arrived_dirs, non_displacing_receipts=non_displacing,
        )

    def _prune(self, candidates: tuple[PoseCandidate, ...]) -> tuple[PoseCandidate, ...]:
        """确定性裁剪（Q-L04-01：后验降序、tie id 升序；cap = Q-L04-02 单值 4）。"""
        ordered = tuple(sorted(candidates, key=lambda c: (-c.posterior, c.candidate_id)))
        if len(ordered) <= self._cap:
            return ordered
        keep = ordered[: self._cap]
        total = sum(c.posterior for c in keep)
        return tuple(
            PoseCandidate(c.candidate_id, c.position, c.orientation, c.posterior / total)
            for c in keep
        )

    # —— 占据（持续性 + 事件条件更新）——
    def _update_occupancy(
        self, effective_time: int, cells: tuple[OccupancyPosterior, ...],
        pose_report: PoseUpdateReport, forage_receipts: tuple[str, ...],
    ) -> None:
        if pose_report.unambiguous:
            pose = pose_report.candidates[0]
            for cell in cells:
                subject_cell = (pose.position[0] + cell.dx, pose.position[1] + cell.dy)
                self._occupancy[subject_cell] = CellBelief(
                    posterior_present=cell.posterior_present,
                    last_effective_time=effective_time,
                    evidence_refs=(cell.evidence_frame_id,),
                )
            success = tuple(e for e in forage_receipts if e.startswith("forage_success"))
            if success:
                # 事件条件更新：forage 成功 = 资源在场证据（RECEIVED 回执面，Q-L04-09②）
                self._occupancy[pose.position] = CellBelief(
                    posterior_present=1.0,
                    last_effective_time=effective_time,
                    evidence_refs=success,
                )
        elif cells:
            # 位姿歧义期：禁伪装映射（Q-L04-09③）——占据更新不落图，typed Unknown 留痕
            pass

    def _snapshot(self, effective_time: int, pose_report: PoseUpdateReport) -> WorldStateBelief:
        occupancy = tuple(sorted(
            self._occupancy.items(), key=lambda item: (item[0][0], item[0][1])
        ))
        coverage: list[tuple[str, str]] = [
            ("occupancy_window", "KNOWN"),
            ("occupancy_stale", "PARTIAL" if self._occupancy else "UNKNOWN"),
            ("occupancy_outside_window", "UNKNOWN"),
        ]
        unknowns = list(pose_report.unknowns)
        if not self._occupancy:
            unknowns.append(Unknown(
                reason=UnknownReason.INSUFFICIENT_OBSERVATION,
                evidence_refs=(),
                detail="no occupancy observations yet（部分可观察显式承载，L04 §4.2）",
                detected_by="models.world",
                virtual_time=effective_time,
            ))
        if not pose_report.unambiguous:
            unknowns.append(Unknown(
                reason=UnknownReason.INSUFFICIENT_OBSERVATION,
                evidence_refs=tuple(pose_report.non_displacing_receipts),
                detail="pose ambiguous: occupancy updates withheld from map（禁伪装映射，Q-L04-09③）",
                detected_by="models.world",
                virtual_time=effective_time,
            ))
        return WorldStateBelief(
            belief_id=f"wsb.{self._run_id}.{effective_time}",
            t_eff=effective_time,
            pose_candidates=self._pose,
            occupancy=occupancy,
            observable_coverage=tuple(coverage),
            unknowns=tuple(unknowns),
            transition_model_version=TRANSITION_MODEL_VERSION,
            update_rule_version=UPDATE_RULE_VERSION,
            cycle_id=effective_time,
        )

    @property
    def pose(self) -> tuple[PoseCandidate, ...]:
        """当前位姿候选（只读面）。"""
        return self._pose
