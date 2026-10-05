"""对象信念构建（L03 §2.2/§10 objects.py；C1 MW0 对象面 = 资源占据 per 格）。

对象 = 融合后验 ≥ believe_threshold 的窗格 OBJECT 信念；塌缩语义按 Q-L03-05
（≥0.9 单信念 / 首尾差 ≥0.6；alternatives 保留备择，重开合法）。
"""
from dataclasses import dataclass

from galatea.kernel.digest import content_digest
from galatea.kernel.packet import ArtifactRef, Provenance
from galatea.subject.c1profile import C1PerceptionParams
from galatea.subject.perception.believe import AltHypothesis, BeliefKind, PerceptualBelief, content_ref
from galatea.subject.perception.fusion import OccupancyPosterior, collapse_decision


@dataclass(frozen=True, slots=True)
class PerceivedObject:
    """结构化对象分量（L03 §2.2；belief 的对象视图，供 L04/L08/L09）。"""

    cell: tuple[int, int]
    dist_key: str
    posterior: float
    belief_id: str


def build_objects(
    cells: tuple[OccupancyPosterior, ...], params: C1PerceptionParams,
    effective_time: int, calibration_version: str,
) -> tuple[tuple[PerceptualBelief, PerceivedObject], ...]:
    """逐格 OBJECT 信念（确定性：按 (dy,dx) 升序；id = pb.OBJECT.t.dxXdy）。

    返回 (belief, object_view) 对齐序列——结构化分量与信念同生同引。
    """
    out: list[tuple[PerceptualBelief, PerceivedObject]] = []
    for cell in sorted(cells, key=lambda c: (c.dy, c.dx)):
        if cell.posterior_present < params.believe_threshold:
            continue
        payload = {
            "object": "resource_presence",
            "cell_egocentric": [cell.dx, cell.dy],
            "dist_key": cell.dist_key,
            "posterior": cell.posterior_present,
        }
        absent_ref = ArtifactRef(
            digest=content_digest({**payload, "present": False}), kind="perceptual_content"
        )
        collapsed = collapse_decision(cell.posterior_present, (), params)
        alternatives: tuple[AltHypothesis, ...] = () if collapsed else (
            AltHypothesis(content_ref=absent_ref, posterior=1.0 - cell.posterior_present),
        )
        belief_id = f"pb.OBJECT.{effective_time}.{cell.dx}x{cell.dy}"
        belief = PerceptualBelief(
            belief_id=belief_id,
            kind=BeliefKind.OBJECT,
            content=content_ref(payload),
            confidence=cell.posterior_present,
            alternatives=alternatives,
            modality_support=(("EXT_LOCAL_OBS", (cell.evidence_frame_id,)),),
            ood_flag=False,
            ood_score=0.0,
            calibration_version=calibration_version,
            provenance=Provenance(
                source_events=(cell.evidence_frame_id,), calibration_version=calibration_version
            ),
            causal_parent_ids=(cell.evidence_frame_id,),
            cycle_id=effective_time,
        )
        out.append((
            belief,
            PerceivedObject(
                cell=(cell.dx, cell.dy), dist_key=cell.dist_key,
                posterior=cell.posterior_present, belief_id=belief_id,
            ),
        ))
    return tuple(out)
