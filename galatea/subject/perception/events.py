"""事件信念构建与跨模态事件融合（L03 §4.2/§10 events.py）。

事件证据双模态（Q-G00-12①：INTERO 直收 + EXT_EVENT 观测面渲染同一
interoceptive_state.events）。聚合规则 C1 = 保守 min（无精度模型；精度加权归 C2，
Q-L02-06）——聚合规则非数值常量，min 选取如实在 docstring 记录。
冲突：一模态报有、另一在场模态报无 → Unknown(CONFLICTING_EVIDENCE) + 保留
alternatives（禁强调和，L03 §4.2/§8 不变量 5）。
一致报无（两模态在场均无事件）→ 不发事件信念（无证据不发信念，禁零置信占位）。
"""
from dataclasses import dataclass

from galatea.kernel.packet import Provenance
from galatea.kernel.unknown import Unknown, UnknownReason
from galatea.subject.perception.believe import AltHypothesis, BeliefKind, PerceptualBelief, content_ref
from galatea.subject.sensorium.ports import SensoryFrame


@dataclass(frozen=True, slots=True)
class PerceivedEvent:
    """结构化事件分量（L03 §2.2）。"""

    event_kind: str
    confidence: "float | Unknown"
    belief_id: str


def intero_event_kinds(frame: SensoryFrame) -> tuple[str, ...]:
    """INTERO 特征 → 事件种（四 sensation 中的二值事件位；Q-L01-08 M0 事件集）。"""
    features = frame.features
    kinds: list[str] = []
    if getattr(features, "energy_depleted", False) is True:
        kinds.append("energy_depleted")
    if getattr(features, "damage_event", False) is True:
        kinds.append("integrity_damage_event")
    return tuple(sorted(kinds))


def ext_event_kinds(frame: SensoryFrame) -> tuple[str, ...]:
    """EXT_EVENT 特征 → 事件种（冻结枚举域检测归 OOD 面）。"""
    features = frame.features
    return tuple(sorted(str(k) for k in getattr(features, "events", ())))


def build_events(
    intero_frame: SensoryFrame | None, ext_event_frame: SensoryFrame | None,
    effective_time: int, calibration_version: str,
) -> tuple[tuple[PerceptualBelief, PerceivedEvent], ...]:
    """事件信念（确定性：事件种升序；id = pb.EVENT.t.kind）。返回 (belief, view) 对。"""
    intero_kinds = set(intero_event_kinds(intero_frame)) if intero_frame is not None else None
    ext_kinds = set(ext_event_kinds(ext_event_frame)) if ext_event_frame is not None else None
    present = (intero_kinds or set()) | (ext_kinds or set())
    conflict = (intero_kinds is not None and ext_kinds is not None) and (intero_kinds ^ ext_kinds)
    out: list[tuple[PerceptualBelief, PerceivedEvent]] = []
    for kind in sorted(present | (conflict or set())):
        supports: list[tuple[str, tuple[str, ...], float]] = []
        if intero_kinds is not None and intero_frame is not None:
            supports.append((
                "INTERO", (intero_frame.frame_id,),
                intero_frame.quality.completeness if kind in intero_kinds else 0.0,
            ))
        if ext_kinds is not None and ext_event_frame is not None:
            supports.append((
                "EXT_EVENT", (ext_event_frame.frame_id,),
                ext_event_frame.quality.completeness if kind in ext_kinds else 0.0,
            ))
        present_scores = [s for s in supports if s[2] > 0.0]
        absent_scores = [s for s in supports if s[2] == 0.0]
        frame_ids = tuple(fid for _, fids, _ in supports for fid in fids)
        if not present_scores and not absent_scores:
            continue
        if present_scores and absent_scores:
            confidence: "float | Unknown" = Unknown(
                reason=UnknownReason.CONFLICTING_EVIDENCE,
                evidence_refs=frame_ids,
                detail=f"event {kind}: INTERO/EXT_EVENT disagreement（禁强调和，L03 §4.2）",
                detected_by="perception.events",
                virtual_time=effective_time,
            )
            alternatives: tuple[AltHypothesis, ...] = (
                AltHypothesis(content_ref=content_ref({"event": kind, "present": False}), posterior=0.5),
            )
        else:
            confidence = min(s[2] for s in present_scores)
            alternatives = ()
        belief = PerceptualBelief(
            belief_id=f"pb.EVENT.{effective_time}.{kind}",
            kind=BeliefKind.EVENT,
            content=content_ref({"event": kind, "support": [s[0] for s in supports]}),
            confidence=confidence,
            alternatives=alternatives,
            modality_support=tuple((name, fids) for name, fids, _ in supports),
            ood_flag=False,
            ood_score=0.0,
            calibration_version=calibration_version,
            provenance=Provenance(source_events=frame_ids, calibration_version=calibration_version),
            causal_parent_ids=frame_ids,
            cycle_id=effective_time,
        )
        out.append((belief, PerceivedEvent(event_kind=kind, confidence=confidence, belief_id=belief.belief_id)))
    return tuple(out)
