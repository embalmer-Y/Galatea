"""自我模型（L04 §4.5/§10 self_model.py；"自我报告只是派生视图"的机械保证）。

每字段必须带 derivation_receipt（指向其派生输入事件）；无派生源的字段必须为
typed Unknown——构造期机械强制（无回执的非 Unknown 字段即 ValueError）。
连续性：只引用 L00 checkpoint 谱系（lineage_ref）；分支恢复记 gaps[]；**禁止**
把 clone 当作同一身份延续（D-12：checkpoint clone ≠ identity）。
记忆/知觉边界元信息：C1 = typed Unknown（L06/L03 联测面——判别能力测量在评价）。
禁写 OwnedGoal（current_goals_view 为装配层只读引用）。
"""
from dataclasses import dataclass, field

from galatea.kernel.digest import content_digest
from galatea.kernel.unknown import Unknown, UnknownReason
from galatea.subject.models.self_error import SelfPredictionError


@dataclass(frozen=True, slots=True)
class ContinuityGap:
    """连续性缺口（分支恢复/重置/回执缺失；clone ≠ identity 明示）。"""

    gap_id: str
    kind: str            # BRANCH | RESET | RECEIPT_GAP
    refs: tuple[str, ...]
    note: str


@dataclass(frozen=True, slots=True)
class ContinuityState:
    """连续性状态（L00 checkpoint 谱系；gaps 显式承载）。"""

    lineage_ref: str
    checkpoint_ref: str
    gaps: tuple[ContinuityGap, ...]


@dataclass(frozen=True, slots=True)
class BoundaryConfidence:
    """记忆/知觉边界判别能力（RECALLED vs PERCEIVED 可区分性的元信息）。"""

    discriminable: "bool | Unknown"
    basis: str


@dataclass(frozen=True, slots=True)
class SelfModelView:
    """自我模型视图（L04 §4.1；派生视图，非事实非报告）。"""

    view_id: str
    continuity: ContinuityState | Unknown
    source_priors: "tuple[tuple[str, float | Unknown], ...] | Unknown"
    memory_perception_boundary: BoundaryConfidence | Unknown
    current_goals_view: tuple[str, ...] | Unknown
    self_prediction_error: SelfPredictionError | Unknown
    derivation_receipts: tuple[tuple[str, tuple[str, ...]], ...]   # (field, refs)
    cycle_id: int
    content_digest: str = field(default="")

    def __post_init__(self) -> None:
        received = {name for name, _ in self.derivation_receipts}
        for name, value in (
            ("continuity", self.continuity),
            ("source_priors", self.source_priors),
            ("memory_perception_boundary", self.memory_perception_boundary),
            ("current_goals_view", self.current_goals_view),
            ("self_prediction_error", self.self_prediction_error),
        ):
            if isinstance(value, Unknown):
                continue
            if name not in received:
                raise ValueError(
                    f"SelfModelView.{name} has no derivation receipt（自我报告只是派生视图，"
                    "L04 §4.5——无派生源字段必须为 Unknown）"
                )
        computed = content_digest({
            "view_id": self.view_id,
            "cycle_id": self.cycle_id,
            "receipts": [[name, list(refs)] for name, refs in self.derivation_receipts],
        })
        if self.content_digest and self.content_digest != computed:
            raise ValueError("SelfModelView digest mismatch（改写检出）")
        object.__setattr__(self, "content_digest", computed)


class SelfModel:
    """自我模型（单写者：subject_state.models.self；T4 整合更新）。"""

    def __init__(self, lineage_ref: str, run_id: str) -> None:
        self._lineage_ref = lineage_ref
        self._run_id = run_id
        self._branch_seen: set[str] = set()
        self._gaps: list[ContinuityGap] = []
        self._gap_count = 0

    def observe_branch(self, branch_id: str, cycle: int) -> None:
        """分支观察（首次见到的 branch ≠ 初始 → gap 记录；clone ≠ identity）。"""
        if branch_id not in self._branch_seen:
            self._branch_seen.add(branch_id)
            if self._gaps or self._branch_seen != {branch_id}:
                self._gap_count += 1
                self._gaps.append(ContinuityGap(
                    gap_id=f"gap.{self._run_id}.{self._gap_count}",
                    kind="BRANCH",
                    refs=(branch_id,),
                    note="branch observed（checkpoint clone ≠ identity，D-12）",
                ))
            else:
                self._branch_seen = {branch_id}
        _ = cycle

    def update(
        self, cycle: int, checkpoint_ref: str,
        source_priors: tuple[tuple[str, "float | Unknown"], ...] | None,
        source_prior_refs: tuple[str, ...],
        goals_view: tuple[str, ...] | None,
        self_error: SelfPredictionError | None,
    ) -> SelfModelView:
        """T4 整合更新（字段级派生回执；无源字段 = Unknown）。"""
        receipts: list[tuple[str, tuple[str, ...]]] = []
        continuity = ContinuityState(
            lineage_ref=self._lineage_ref, checkpoint_ref=checkpoint_ref,
            gaps=tuple(self._gaps),
        )
        receipts.append(("continuity", (self._lineage_ref, checkpoint_ref)))
        if source_priors is None or not source_prior_refs:
            priors: tuple[tuple[str, "float | Unknown"], ...] | Unknown = Unknown(
                reason=UnknownReason.INSUFFICIENT_OBSERVATION,
                evidence_refs=(),
                detail="no source judgements observed（C1 载体级来源面待观测）",
                detected_by="models.self_model",
                virtual_time=cycle,
            )
        else:
            priors = source_priors
            receipts.append(("source_priors", source_prior_refs))
        boundary: BoundaryConfidence | Unknown = Unknown(
            reason=UnknownReason.DECISION_PATH_UNRESOLVED,
            evidence_refs=(),
            detail="RECALLED vs PERCEIVED 判别能力测量归 L06/L03 联测（C1 评价面）",
            detected_by="models.self_model",
            virtual_time=cycle,
        )
        if goals_view is None:
            goals: tuple[str, ...] | Unknown = Unknown(
                reason=UnknownReason.INSUFFICIENT_OBSERVATION,
                evidence_refs=(),
                detail="no goals view supplied（装配层只读引用缺席）",
                detected_by="models.self_model",
                virtual_time=cycle,
            )
        else:
            goals = goals_view
            receipts.append(("current_goals_view", tuple(f"goal.{g}" for g in goals_view)))
        if self_error is None:
            error: SelfPredictionError | Unknown = Unknown(
                reason=UnknownReason.MISSING_SIGNAL,
                evidence_refs=(),
                detail="no body observation yet（禁伪造零误差）",
                detected_by="models.self_model",
                virtual_time=cycle,
            )
        else:
            error = self_error
            receipts.append(("self_prediction_error", (f"selferr.{self_error.window[0]}..{self_error.window[1]}",)))
        return SelfModelView(
            view_id=f"smv.{self._run_id}.{cycle}",
            continuity=continuity,
            source_priors=priors,
            memory_perception_boundary=boundary,
            current_goals_view=goals,
            self_prediction_error=error,
            derivation_receipts=tuple(receipts),
            cycle_id=cycle,
        )
