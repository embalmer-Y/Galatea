"""知觉流水线门面（L03 §5 T2 主知觉计算 / §10 补录件，C1 实现期）。

process_window（T2）：层级守卫（非 SENSORY_FORMED 输入 = UnauthorizedInput S0）→
模态分派 → OOD 事件级域出 → 表格融合（占格后验）→ 对象/事件/来源/affordance →
abstain 判定（ood 或 top < believe_threshold）→ FIELD 低承诺信念 → 知觉层误差 →
回执 + 审计 + workspace 候选。

确定性：全部 sorted；无 RNG 无墙钟（c1 profile determinism none_c1）。
记忆线索（cues）只记引用进回执——禁注入信念内容（L03 §8 不变量 6）。
"""
from dataclasses import dataclass

from galatea.kernel.packet import Provenance
from galatea.kernel.unknown import Unknown, UnknownReason
from galatea.subject.c1profile import C1Profile, load_c1_profile
from galatea.subject.perception.affordance import Affordance, build_affordances
from galatea.subject.perception.believe import BeliefKind, PerceptualBelief, content_ref
from galatea.subject.perception.confidence import CalibrationScale
from galatea.subject.perception.events import PerceivedEvent, build_events
from galatea.subject.perception.fusion import (
    LikelihoodTable,
    OccupancyPosterior,
    build_likelihood_table,
    fuse_window,
)
from galatea.subject.perception.objects import PerceivedObject, build_objects
from galatea.subject.perception.ood import AbstainEvent, OodAssessment, assess_ood, abstain_reason, should_abstain
from galatea.subject.perception.pred_error import PerceptualPredictionError, perceptual_errors
from galatea.subject.perception.receipt import PerceptionReceipt, audit_receipts, build_receipt
from galatea.subject.perception.source import SourceJudgement, judge_frame_source
from galatea.subject.perception.workspace_prop import WorkspaceProposal, build_proposals
from galatea.subject.sensorium.ports import (
    ExtEventFeatures,
    ExtLocalObsFeatures,
    ProprioFeatures,
    SensoryFrame,
)


class UnauthorizedInput(RuntimeError):
    """检出 SensoryFrame→PerceptualBelief 之外的输入路径（L03 §6 行 8：S0 停止）。"""


@dataclass(frozen=True, slots=True)
class PerceptionOutput:
    """单窗知觉产物（全部证据侧可审计；层级恒 PERCEIVED）。"""

    effective_time: int
    beliefs: tuple[PerceptualBelief, ...]
    objects: tuple[PerceivedObject, ...]
    events: tuple[PerceptualBelief, ...]
    affordances: tuple[Affordance, ...]
    sources: tuple[SourceJudgement, ...]
    abstains: tuple[AbstainEvent, ...]
    cells: tuple[OccupancyPosterior, ...]     # 世界模型消费的规范化占据后验
    pred_errors: tuple[PerceptualPredictionError, ...]
    receipts: tuple[PerceptionReceipt, ...]
    proposals: tuple[WorkspaceProposal, ...]
    unknowns: tuple[Unknown, ...]


class PerceptionPipeline:
    """T2 主知觉计算（对齐组关闭后的窗级批处理）。"""

    def __init__(self, profile: C1Profile | None = None) -> None:
        self._profile = profile or load_c1_profile()
        self._params = self._profile.perception
        self._table: LikelihoodTable = build_likelihood_table(
            self._params.gain_by_distance, self._params.render_noise_sigma, self._params.bin_edges
        )
        self._calibration = CalibrationScale(version_id=self._profile.sensorium_c1.calibration_version)

    def process_window(
        self, effective_time: int, frames: tuple[SensoryFrame, ...],
        predictions: dict[tuple[int, int], float] | None = None,
        outcome_effects: tuple[str, ...] = (),
        cues: tuple[str, ...] = (),
    ) -> PerceptionOutput:
        for frame in frames:
            if frame.representation_level.value != "SENSORY_FORMED":
                raise UnauthorizedInput(
                    f"frame {frame.frame_id} level {frame.representation_level}（禁非感觉帧输入，S0）"
                )
        window_frame = next((f for f in frames if f.modality.value == "EXT_LOCAL_OBS"), None)
        ext_event_frame = next((f for f in frames if f.modality.value == "EXT_EVENT"), None)
        intero_frame = next((f for f in frames if f.modality.value == "INTERO"), None)
        proprio_frame = next((f for f in frames if f.modality.value == "PROPRIO"), None)

        window: tuple[tuple[float, ...], ...] | None = None
        if window_frame is not None and isinstance(window_frame.features, ExtLocalObsFeatures):
            window = tuple(tuple(float(v) for v in row) for row in window_frame.features.window)
        event_kinds: tuple[str, ...] = ()
        if ext_event_frame is not None and isinstance(ext_event_frame.features, ExtEventFeatures):
            event_kinds = tuple(str(k) for k in ext_event_frame.features.events)
        orientation: str | None = None
        if proprio_frame is not None and isinstance(proprio_frame.features, ProprioFeatures):
            orientation = proprio_frame.features.orientation
        all_frame_ids = tuple(f.frame_id for f in frames)
        ood = assess_ood(window, event_kinds, orientation, self._table, all_frame_ids, effective_time)

        beliefs: list[PerceptualBelief] = []
        cells: tuple[OccupancyPosterior, ...] = ()
        object_pairs: tuple[tuple[PerceptualBelief, PerceivedObject], ...] = ()
        event_pairs: tuple[tuple[PerceptualBelief, PerceivedEvent], ...] = ()
        abstains: tuple[AbstainEvent, ...] = ()
        unknowns: list[Unknown] = []
        domain_failures: tuple[str, ...] = ()

        if not ood.ood_flag and window is not None:
            cells, domain_failures = fuse_window(
                window, self._params.prior_resource_density, self._table,
                window_frame.frame_id,  # type: ignore[union-attr]
            )
            if domain_failures:
                unknowns.append(Unknown(
                    reason=UnknownReason.OOD,
                    evidence_refs=all_frame_ids,
                    detail="; ".join(domain_failures),
                    detected_by="perception.pipeline",
                    virtual_time=effective_time,
                ))
            else:
                object_pairs = build_objects(cells, self._params, effective_time, self._calibration.version_id)
                beliefs.extend(b for b, _ in object_pairs)
        elif ood.ood_flag:
            unknowns.append(Unknown(
                reason=UnknownReason.OOD,
                evidence_refs=all_frame_ids,
                detail="; ".join(ood.reasons),
                detected_by="perception.pipeline",
                virtual_time=effective_time,
            ))

        if not ood.ood_flag and not domain_failures:
            event_pairs = build_events(intero_frame, ext_event_frame, effective_time, self._calibration.version_id)
            beliefs.extend(b for b, _ in event_pairs)

        ood_effective = ood if not domain_failures else OodAssessment(
            ood_flag=True, ood_score=1.0,
            reasons=ood.reasons + domain_failures, evidence_refs=all_frame_ids,
        )
        top = max((c.posterior_present for c in cells), default=None)
        if should_abstain(top, self._params, ood_effective):
            abstains = (AbstainEvent(
                abstain_id=f"abstain.{effective_time}",
                reason=abstain_reason(effective_time, ood_effective),
                candidates_considered=tuple(
                    content_ref({"cell": [c.dx, c.dy], "posterior": c.posterior_present}).digest
                    for c in sorted(cells, key=lambda c: (c.dy, c.dx))
                ),
                threshold_ref=f"believe_threshold={self._params.believe_threshold}@{self._profile.ref()}",
                cycle_id=effective_time,
            ),)
            if window is not None and window_frame is not None:
                # 低承诺 FIELD 信念（L03 §4.4：看到但无法归类；OOD 时置信 Unknown）
                top_cell = min(cells, key=lambda c: (-c.posterior_present, c.dy, c.dx)) if cells else None
                field_conf: "float | Unknown"
                if ood_effective.ood_flag:
                    field_conf = Unknown(
                        reason=UnknownReason.OOD, evidence_refs=all_frame_ids,
                        detail="window present but out of frozen domain",
                        detected_by="perception.pipeline", virtual_time=effective_time,
                    )
                else:
                    field_conf = top_cell.posterior_present if top_cell else 0.0
                field_payload = {
                    "field": "unclassified_window",
                    "effective_time": effective_time,
                    "top_cell": [top_cell.dx, top_cell.dy] if top_cell else None,
                }
                beliefs.append(PerceptualBelief(
                    belief_id=f"pb.FIELD.{effective_time}",
                    kind=BeliefKind.FIELD,
                    content=content_ref(field_payload),
                    confidence=field_conf,
                    alternatives=(),
                    modality_support=(("EXT_LOCAL_OBS", (window_frame.frame_id,)),),
                    ood_flag=ood_effective.ood_flag,
                    ood_score=ood_effective.ood_score,
                    calibration_version=self._calibration.version_id,
                    provenance=Provenance(
                        source_events=all_frame_ids, calibration_version=self._calibration.version_id
                    ),
                    causal_parent_ids=all_frame_ids,
                    cycle_id=effective_time,
                ))

        sources = tuple(judge_frame_source(f) for f in sorted(frames, key=lambda f: f.frame_id))
        affordances = build_affordances(
            cells if not (ood.ood_flag or domain_failures) else (), self._params, outcome_effects, effective_time
        )
        pred_errors, pred_unknowns = perceptual_errors(
            tuple(beliefs), cells, predictions or {}, effective_time
        )
        unknowns.extend(pred_unknowns)

        receipts = tuple(
            build_receipt(
                belief_id=b.belief_id,
                source_frames=tuple(fid for _, fids in b.modality_support for fid in fids) or all_frame_ids,
                calibration_version=b.calibration_version,
                cycle_id=effective_time,
                cues=cues,
                ood_flags=tuple(ood.reasons) if b.ood_flag else (),
            )
            for b in beliefs
        )
        audit_receipts(tuple(b.belief_id for b in beliefs), receipts)
        proposals = build_proposals(tuple(beliefs), effective_time)
        return PerceptionOutput(
            effective_time=effective_time,
            beliefs=tuple(beliefs),
            objects=tuple(o for _, o in object_pairs),
            events=tuple(b for b, _ in event_pairs),
            affordances=affordances,
            sources=sources,
            abstains=abstains,
            cells=cells,
            pred_errors=pred_errors,
            receipts=receipts,
            proposals=proposals,
            unknowns=tuple(unknowns),
        )
