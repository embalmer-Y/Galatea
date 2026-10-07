"""感觉层预测误差（L02 §4.5/§10 pred_error.py；C1 接线——L04 预测源已存在）。

特征空间 = formed features 的规范化展平（Q-L02-06：特征空间由形成层唯一决定，
禁评价侧自造特征工程）：
- EXT_LOCAL_OBS = 5×5 窗展平 25 维（行优先，窗载荷约定）；
- EXT_EVENT = 冻结事件种枚举 one-hot（Q-L01-08 M0 事件集，EVENT_KINDS）；
- INTERO = 四 sensation 标量（Q-L02-05 集合 + Q-L02-06 展平序）；
- PROPRIO = 朝向 one-hot（载荷域 ORIENTATION_TOKENS）。
残差 = 同维 float64 向量差（Q-T10）；精度加权归 C2（Q-L02-06）——无权残差。
预测无匹配帧 / 帧无匹配预测 → typed Unknown 留痕（禁伪造零误差，C0 成规）。
层级化纪律：本函数只产**感觉层**分量，禁与知觉层（L03 pred_error）/模型层
（L04 mismatch）顶替或合并（Q-L09-08 1:1:1 禁跨层归一）。
"""
from dataclasses import dataclass

from galatea.subject.c1profile import EVENT_KINDS, INTERO_SCALARS, ORIENTATION_TOKENS
from galatea.subject.models.ports import ModelPrediction
from galatea.subject.sensorium.ports import (
    ExtEventFeatures,
    ExtLocalObsFeatures,
    InteroSensations,
    ProprioFeatures,
    SensoryFrame,
)


@dataclass(frozen=True, slots=True)
class SensoryPredictionError:
    """感觉层预测误差（层级化三分量之一；predicted_ref = 预测 id）。"""

    frame_id: str
    predicted_ref: str
    modality: str
    residual: tuple[float, ...]
    cycle_id: int


def flatten_frame(frame: SensoryFrame) -> tuple[float, ...]:
    """formed_features_flat 展平（Q-L02-06；维度域由形成层唯一决定）。"""
    features = frame.features
    if isinstance(features, ExtLocalObsFeatures):
        return tuple(float(v) for row in features.window for v in row)
    if isinstance(features, ExtEventFeatures):
        return tuple(1.0 if kind in features.events else 0.0 for kind in EVENT_KINDS)
    if isinstance(features, InteroSensations):
        values: dict[str, float] = {
            "energy_level": features.energy_level,
            "integrity_level": features.integrity_level,
            "damage_event": 1.0 if features.damage_event else 0.0,
            "energy_depleted": 1.0 if features.energy_depleted else 0.0,
        }
        return tuple(values[name] for name in INTERO_SCALARS)
    if isinstance(features, ProprioFeatures):
        # C4：LANGUAGE 帧不参与 pred_error 特征空间（Q-L12-06① 零后验权重——
        # flatten 的调用面为非语言模态；语言帧传入 = 调用方路由缺陷，显式拒绝）
        return tuple(1.0 if features.orientation == token else 0.0 for token in ORIENTATION_TOKENS)
    raise ValueError(
        f"LANGUAGE frame {frame.frame_id} has no pred_error feature space"
        "（语言帧零后验权重——不入误差特征空间，Q-L12-06①）"
    )


def _expected_vector(prediction: ModelPrediction) -> tuple[float, ...] | None:
    """预测 → 同一特征空间向量（模态互斥面）。"""
    if prediction.expected_window is not None:
        return tuple(float(v) for row in prediction.expected_window for v in row)
    if prediction.expected_body is not None:
        return (prediction.expected_body[0], prediction.expected_body[1], 0.0, 0.0)
    if prediction.expected_orientation is not None:
        return tuple(
            1.0 if prediction.expected_orientation == token else 0.0
            for token in ORIENTATION_TOKENS
        )
    return None


def _modality_of(prediction: ModelPrediction) -> str:
    return prediction.target_modality


def sense_errors(
    predictions: tuple[ModelPrediction, ...], frames: tuple[SensoryFrame, ...]
) -> tuple[tuple[SensoryPredictionError, ...], tuple[str, ...]]:
    """感觉层预测误差（同模态 valid_time 匹配；float64 残差；确定性序）。

    返回 (errors, unmatched_predictions)：预测无匹配帧 → unmatched 留痕
    （处置面归 L09/L04——禁伪造零误差）。无预测 → ((), ())（C0 成规保持）。
    """
    if not predictions:
        return (), ()
    errors: list[SensoryPredictionError] = []
    matched: set[str] = set()
    for prediction in predictions:
        expected = _expected_vector(prediction)
        if expected is None:
            continue
        modality = _modality_of(prediction)
        candidates = [
            frame for frame in frames
            if frame.modality.value == modality and frame.effective_time == prediction.valid_time
        ]
        if not candidates:
            continue
        frame = candidates[0]
        observed = flatten_frame(frame)
        if len(observed) != len(expected):
            raise ValueError(
                f"feature space dimension mismatch for {frame.frame_id}: "
                f"{len(observed)} vs {len(expected)}（Q-L02-06 特征空间由形成层唯一决定）"
            )
        errors.append(SensoryPredictionError(
            frame_id=frame.frame_id,
            predicted_ref=prediction.prediction_id,
            modality=modality,
            residual=tuple(o - e for o, e in zip(observed, expected)),
            cycle_id=frame.effective_time,
        ))
        matched.add(prediction.prediction_id)
    unmatched = tuple(p.prediction_id for p in predictions if p.prediction_id not in matched)
    return tuple(errors), unmatched
