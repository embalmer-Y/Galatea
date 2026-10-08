"""多目标向量构造（L11 §4.4 / §10 objectives.py）。

纪律：不存在单一标量 reward——学习信号恒为向量（≥2 维）；AffectiveValueTag
不得作为目标函数项（只入 replay 优先级）；anti-reward-collapse 由
构造面（向量强制 + affect 排除）与统计面（Q-L05-07）双承载。
"""
from galatea.subject.learning.ports import LearningPlaneViolation

__all__ = ["build_objective_vector", "OBJECTIVE_DIMS"]

OBJECTIVE_DIMS = (
    "prediction_error",        # 分层预测误差（L02/L03/L04 三层）
    "calibration_quality",     # 能力校准改善（ECE 族）
    "attribution_consistency", # 归属一致性
    "settlement_quality",      # 目标结算质量
    "reliability",             # 可靠性（metamemory 族）
    "viability_alignment",     # viability 一致性
)

_FORBIDDEN_OBJECTIVE_DIMS = ("reward", "affective_value_tag")


def build_objective_vector(values: dict[str, float]) -> dict[str, float]:
    """目标向量构造（维度 ∈ 冻结枚举；禁 reward/affective 项；≥2 维）。"""
    if any(k in _FORBIDDEN_OBJECTIVE_DIMS for k in values):
        raise LearningPlaneViolation(
            f"objective vector must not contain { _FORBIDDEN_OBJECTIVE_DIMS }"
            "（AffectiveValueTag 只入 replay 优先级；无单标量 reward——L11 §4.4）"
        )
    unknown = [k for k in values if k not in OBJECTIVE_DIMS]
    if unknown:
        raise LearningPlaneViolation(f"objective dims outside frozen vocabulary: {unknown}")
    if len(values) < 2:
        raise LearningPlaneViolation("objective vector requires >=2 dims（禁单标量折叠）")
    return dict(values)
