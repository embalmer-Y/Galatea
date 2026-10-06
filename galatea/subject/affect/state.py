"""九维感受态与动力学标记（L05 §4.1/§10 state.py，C2 实现期）。

九维 = valence/arousal/urgency/controllability/uncertainty/novelty/social_relevance/
tendencies/persistence（Q-L05-01 域：valence ∈ [−1,1] 对称，其余 [0,1]；
**禁跨维聚合**——本类型不提供任何标量汇总方法，anti-reward-collapse 结构面）。
tendencies.action_class = L10 五原语枚举（Q-L05-06，权威源
f0_action_contract@v1.0 containment_whitelist_mw0）；inhibited 默认 True（不变量 5，
倾向 ≠ 命令；释放经 L09 仲裁 = C3 接线）。
"""
import enum
from dataclasses import dataclass, field

from galatea.kernel.digest import content_digest
from galatea.kernel.unknown import Unknown

__all__ = [
    "ActionClass",
    "Tendency",
    "ActionTendencySet",
    "DynamicsTrace",
    "FunctionalExperientialState",
]


class ActionClass(enum.StrEnum):
    """tendencies 动作类枚举（Q-L05-06①：= L10 MW0 五原语，引用冻结合同不自造）。"""

    MOVE = "move"
    FORAGE = "forage"
    EAT = "eat"
    REST = "rest"
    LOOK = "look"


@dataclass(frozen=True, slots=True)
class Tendency:
    """行动倾向（L05 §4.1：倾向 ≠ 命令；inhibited 默认保守）。"""

    action_class: ActionClass
    strength: float
    inhibited: bool = True

    def __post_init__(self) -> None:
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError(f"tendency strength out of [0,1]: {self.strength!r}")


@dataclass(frozen=True, slots=True)
class ActionTendencySet:
    """倾向集（确定性序 = action_class 升序；缺源时空集 + Unknown 由状态承载）。"""

    items: tuple[Tendency, ...] = ()

    def __post_init__(self) -> None:
        keys = [t.action_class for t in self.items]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate action_class in tendencies")
        if keys != sorted(keys):
            object.__setattr__(self, "items", tuple(sorted(self.items, key=lambda t: t.action_class)))


@dataclass(frozen=True, slots=True)
class DynamicsTrace:
    """动力学标记（L05 §4.1/§4.3：六机制可测痕迹的公开面）。"""

    integrator_state: float        # valence 积分器当前值（发布前）
    hysteresis_band: float         # 迟滞带宽（frozen）
    decay_rate: float              # 慢尺度衰减率 1/τ_dec（frozen）
    saturation_hits: int           # 饱和计数（累计）
    recovery_phase: bool           # 恢复相位（误差回落 set-point±band 内）


@dataclass(frozen=True, slots=True)
class FunctionalExperientialState:
    """九维感受态（持续动力学状态，非标签——L05 §8 不变量 4）。

    禁跨维聚合（Q-L05-01③）：本类型**不存在**任何 `summary()/score()/reward()`
    标量方法；跨维使用只允许读者各自取维（evaluator 侧 anti-reward-collapse
    判据 Q-L05-07 的结构前提）。
    """

    state_id: str
    t_eff: int
    valence: float                                  # [−1,1]（改善正/恶化负）
    arousal: float
    urgency: float
    controllability: float
    uncertainty: float
    novelty: float
    social_relevance: float                         # MW0 恒 0.0 + Unknown（D-14）
    tendencies: ActionTendencySet
    persistence: float
    dynamics_trace: DynamicsTrace
    reappraisal_history: tuple[str, ...] = ()
    unknowns: tuple[Unknown, ...] = ()
    content_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not -1.0 <= self.valence <= 1.0:
            raise ValueError(f"valence out of [−1,1]: {self.valence!r}")
        for name in ("arousal", "urgency", "controllability", "uncertainty", "novelty",
                     "social_relevance", "persistence"):
            v = getattr(self, name)
            if not 0.0 <= v <= 1.0:
                raise ValueError(f"{name} out of [0,1]: {v!r}")
        object.__setattr__(self, "content_digest", content_digest({
            "state_id": self.state_id, "t_eff": self.t_eff,
            "valence": self.valence, "arousal": self.arousal, "urgency": self.urgency,
            "controllability": self.controllability, "uncertainty": self.uncertainty,
            "novelty": self.novelty, "social_relevance": self.social_relevance,
            "tendencies": [[t.action_class.value, t.strength, t.inhibited] for t in self.tendencies.items],
            "persistence": self.persistence,
            "trace": [self.dynamics_trace.integrator_state, self.dynamics_trace.saturation_hits,
                      self.dynamics_trace.recovery_phase],
            "reappraisal_history": list(self.reappraisal_history),
        }))
