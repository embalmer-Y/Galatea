"""ModelPrediction 发布（L04 §5 T1 先行/§10 prediction.py）。

预测先行原则：下一窗的模型预测在知觉计算前发布，供 L02 感觉层比较（Q-L02-06
formed_features_flat）与 L03 知觉层比较。C1 预测语义（Q-L04-09 转移语义推论）：
- EXTERO 窗 = 位姿无歧义时占据信念的 egocentric 平移投影；从未观测格 = 先验
  （Q-L04-11 冻结初始条件，声明来源非观测）；位姿歧义 → 不发窗预测（禁伪装）；
- INTERO = 身体信念持续性；PROPRIO = 朝向持续性。
precision 恒 typed Unknown（精度加权归 C2，Q-L02-06）。
"""
from galatea.kernel.unknown import Unknown, UnknownReason
from galatea.subject.c1profile import C1Profile
from galatea.subject.models.body import BodyBelief
from galatea.subject.models.ports import ModelPrediction
from galatea.subject.models.world import WorldStateBelief


def predict_window(
    belief: WorldStateBelief, profile: C1Profile, valid_time: int
) -> tuple[ModelPrediction, ...]:
    """下一窗外感受窗预测（**值空间**：期望渲染值 = posterior × g(d)——观察者
    自身通道合同（Q-L03-03 同源），与渲染值/持续基线同标度可比）。

    位姿歧义 → 空预测 + 调用方 Unknown 留痕（禁伪装）。"""
    if len(belief.pose_candidates) != 1:
        return ()
    pose = belief.pose_candidates[0]
    occupancy = dict(belief.occupancy)
    prior = profile.perception.prior_resource_density
    gain = profile.perception.gain_by_distance
    offset = 2
    window: list[tuple[float, ...]] = []
    for r in range(5):
        row: list[float] = []
        for c in range(5):
            dx, dy = c - offset, r - offset
            subject_cell = (pose.position[0] + dx, pose.position[1] + dy)
            cell = occupancy.get(subject_cell)
            posterior = cell.posterior_present if cell is not None else prior
            row.append(posterior * gain[f"d{max(abs(dx), abs(dy))}"])
        window.append(tuple(row))
    return (ModelPrediction(
        prediction_id=f"mp.EXT.{valid_time}",
        target_modality="EXT_LOCAL_OBS",
        expected_window=tuple(window),
        valid_time=valid_time,
    ),)


def predict_body(belief: BodyBelief | None, valid_time: int) -> tuple[ModelPrediction, ...]:
    """内感受持续性预测（无身体信念 → 空预测——禁先验冒充观测）。"""
    if belief is None:
        return ()
    return (ModelPrediction(
        prediction_id=f"mp.INTERO.{valid_time}",
        target_modality="INTERO",
        expected_body=(belief.energy_belief, belief.integrity_belief),
        valid_time=valid_time,
    ),)


def predict_orientation(belief: BodyBelief | None, valid_time: int) -> tuple[ModelPrediction, ...]:
    """本体感受朝向持续性预测。"""
    if belief is None or belief.orientation is None:
        return ()
    return (ModelPrediction(
        prediction_id=f"mp.PROPRIO.{valid_time}",
        target_modality="PROPRIO",
        expected_orientation=belief.orientation,
        valid_time=valid_time,
    ),)


def prediction_coverage_unknown(cycle: int) -> Unknown:
    """窗预测缺席说明（位姿歧义期；消费方处置面）。"""
    return Unknown(
        reason=UnknownReason.INSUFFICIENT_OBSERVATION,
        evidence_refs=(),
        detail="window prediction withheld: pose ambiguous（Q-L04-09③ 禁伪装映射）",
        detected_by="models.prediction",
        virtual_time=cycle,
    )
