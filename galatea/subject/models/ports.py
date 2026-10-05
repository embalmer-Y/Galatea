"""模型面端口与预测/查询 schema（L04 §2/§10 ports.py）。

层级纪律：ModelPrediction 恒 PREDICTED、ImaginedTrajectory 恒 IMAGINED
（构造期守卫，禁提升/改写——消费越级即 RepresentationEscalation，L04 §6 行 8）。
输入白名单：PerceptualBelief（PERCEIVED）、SensoryFrame（SENSORY_FORMED）、
执行回执（RECEIVED 主体可见侧）；禁读 ExecutionFact 隐藏真值与 evaluator 标签
（L04 §2.1 model.action_feedback 纪律）。
"""
from dataclasses import dataclass, field

from galatea.kernel.unknown import Unknown, UnknownReason
from galatea.subject.sensorium.ports import SensoryFrame  # noqa: F401  (输入类型引用)


class RepresentationEscalation(RuntimeError):
    """IMAGINED/PREDICTED/RECALLED 被当 PERCEIVED 使用或层级被改写（L04 §6 行 8：S0）。"""


def c1_precision_unknown(virtual_time: int = 0) -> Unknown:
    """C1 统一精度面：typed Unknown（精度加权归 C2，Q-L02-06——零精度常量）。"""
    return Unknown(
        reason=UnknownReason.CAPABILITY_LIMIT,
        evidence_refs=(),
        detail="precision weighting deferred to C2（Q-L02-06）",
        detected_by="models.ports",
        virtual_time=virtual_time,
    )


@dataclass(frozen=True, slots=True)
class ModelPrediction:
    """模型预测（L04 §2.2 model.prediction；T1 先行发布，恒 PREDICTED）。

    expected_* 三面按模态互斥：EXTERO 窗 / INTERO 身体标量 / PROPRIO 朝向。
    """

    prediction_id: str
    target_modality: str
    expected_window: tuple[tuple[float, ...], ...] | None = None
    expected_body: tuple[float, float] | None = None       # (energy, integrity) 持续性
    expected_orientation: str | None = None
    valid_time: int = 0
    precision: "float | Unknown" = field(default_factory=c1_precision_unknown)
    source_module: str = "models"
    representation_level: str = field(default="PREDICTED", init=False)

    def __post_init__(self) -> None:
        if self.representation_level != "PREDICTED":
            raise RepresentationEscalation("ModelPrediction level is fixed to PREDICTED（L04 §2.2）")
        if self.expected_window is None and self.expected_body is None and self.expected_orientation is None:
            raise ValueError("ModelPrediction requires one expected face（窗/身体/朝向）")


@dataclass(frozen=True, slots=True)
class RolloutQuery:
    """rollout 查询（L04 §2.1 model.rollout_request；超预算裁剪 + 回执 CLIPPED）。"""

    query_id: str
    action_sequence: tuple[tuple[str, str | None], ...]   # (primitive, param)
    depth: int
    width: int
    purpose: str


@dataclass(frozen=True, slots=True)
class RolloutBranch:
    """单分支轨迹（确定性展开；位置 = 航位推算积分面）。"""

    branch_id: str
    pose_ref: str                       # 依赖的位姿候选（Q-L04-09③ 分支传播）
    steps: tuple[tuple[int, str, str, tuple[int, int]], ...]   # (offset, action, orientation, position)
    final_position: tuple[int, int]


@dataclass(frozen=True, slots=True)
class ImaginedTrajectory:
    """多未来轨迹（L04 §2.2 model.rollout；恒 IMAGINED——消费者越级 = S0）。"""

    set_id: str
    query_id: str
    branches: tuple[RolloutBranch, ...]
    depth: int
    width: int
    value_summary: Unknown                    # C1 无价值模型（L05 归 C2）——恒 Unknown
    uncertainty: tuple[str, ...]              # 位姿分支数 / 覆盖盲区说明
    clipped: bool = False
    representation_level: str = field(default="IMAGINED", init=False)

    def __post_init__(self) -> None:
        if self.representation_level != "IMAGINED":
            raise RepresentationEscalation("ImaginedTrajectory level is fixed to IMAGINED（L04 §4.3）")
        if not self.uncertainty:
            raise ValueError("ImaginedTrajectory requires uncertainty notes（位姿分支/覆盖盲区说明）")


def require_perceived_level(belief_level: str, source: str) -> None:
    """输入白名单断言：信念输入必须 PERCEIVED（L04 §2.1）。"""
    if belief_level != "PERCEIVED":
        raise RepresentationEscalation(f"{source}: belief level must be PERCEIVED, got {belief_level}")


def require_formed_frame(frame: SensoryFrame, source: str) -> None:
    """输入白名单断言：感觉帧必须 SENSORY_FORMED（L04 §2.1）。"""
    if frame.representation_level.value != "SENSORY_FORMED":
        raise RepresentationEscalation(f"{source}: frame level must be SENSORY_FORMED")


def require_window_shape(window: tuple[tuple[float, ...], ...]) -> None:
    """窗形状守卫（5×5 egocentric，Q-L01-01 冻结；非方阵 = schema 违规）。"""
    if len(window) != 5 or any(len(row) != 5 for row in window):
        raise ValueError(
            f"expected 5x5 egocentric window, got {len(window)}x{len(window[0]) if window else 0}"
        )
