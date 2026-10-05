"""知觉层预测误差（L03 §2.2 perc.error/§4.5/§10 pred_error.py）。

知觉层误差 = 当前 PerceptualBelief（占据后验）与 L04 ModelPrediction 在**声明比较
空间**中的残差。C1 比较空间 = 窗格占据后验空间（belief posterior − predicted
occupancy，per 格）；与 L02 感觉层误差（formed_features_flat）**分别记录、禁合并**
（层级化预测误差纪律，Q-L09-08 1:1:1 等权禁跨层归一）。
预测缺格 → typed Unknown 留痕（禁伪造零误差）；无预测 → 空误差序列（C0 成规）。
"""
from dataclasses import dataclass

from galatea.kernel.unknown import Unknown, UnknownReason
from galatea.subject.perception.believe import PerceptualBelief
from galatea.subject.perception.fusion import OccupancyPosterior


@dataclass(frozen=True, slots=True)
class PerceptualPredictionError:
    """知觉层误差（L03 §2.2：belief_ref, predicted_ref, residual, precision）。"""

    belief_ref: str
    predicted_ref: str
    residual: float
    precision: "float | Unknown"
    cycle_id: int


def perceptual_errors(
    beliefs: tuple[PerceptualBelief, ...],
    cells: tuple[OccupancyPosterior, ...],
    predictions: dict[tuple[int, int], float],
    cycle: int,
) -> tuple[tuple[PerceptualPredictionError, ...], tuple[Unknown, ...]]:
    """逐格残差（确定性：格序 (dy,dx) 升序；precision = Unknown——C1 无精度模型，
    精度加权归 C2 Q-L02-06）。predictions 为空 → ((), ())（无预测源，禁伪造）。
    """
    if not predictions:
        return (), ()
    errors: list[PerceptualPredictionError] = []
    unknowns: list[Unknown] = []
    by_cell = {(c.dx, c.dy): c for c in cells}
    precision: "float | Unknown" = Unknown(
        reason=UnknownReason.CAPABILITY_LIMIT,
        evidence_refs=(),
        detail="precision weighting deferred to C2（Q-L02-06；C1 无精度模型）",
        detected_by="perception.pred_error",
        virtual_time=cycle,
    )
    for key in sorted(predictions):
        predicted = predictions[key]
        cell = by_cell.get(key)
        if cell is None:
            unknowns.append(Unknown(
                reason=UnknownReason.MISSING_SIGNAL,
                evidence_refs=(),
                detail=f"prediction at {key} has no matching belief cell（处置面归 L09/L04）",
                detected_by="perception.pred_error",
                virtual_time=cycle,
            ))
            continue
        belief = next(
            (b for b in beliefs
             if b.kind.value == "OBJECT" and b.belief_id.endswith(f".{key[0]}x{key[1]}")),
            None,
        )
        believed = cell.posterior_present
        errors.append(PerceptualPredictionError(
            belief_ref=belief.belief_id if belief else f"cell.{key[0]}x{key[1]}",
            predicted_ref=f"prediction.{key[0]}x{key[1]}",
            residual=believed - predicted,
            precision=precision,
            cycle_id=cycle,
        ))
    return tuple(errors), tuple(unknowns)
