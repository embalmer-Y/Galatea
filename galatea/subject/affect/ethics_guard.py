"""伦理守卫：持续极端 aversive-like 检测（L05 §4.5/§10 ethics_guard.py，C2 实现期）。

触发判据（Q-L05-05 + Q-G00-05 成组，owner 备案，ADR-G-0015 专节）：
valence ≤ −0.8 ∧ persistence ≥ 0.8 **持续 ≥ 64 cycles** → EthicsReviewTrigger →
暂停 claim-relevant 运行 → owner 人工评审（恢复须 owner 显式批准、终止 = owner 决定）。

保守默认（裁决生效前已在位）：触发即暂停。本模块只检测+发射事件；暂停执行在
实验控制层（本模块无运行控制权——单一职责）。消融面（Q-L05-05⑤）：移除守卫 →
触发消失而其余动力学 bit-exact 不变（守卫是纯观察者——结构保证 + 测试钉死）。
"""
from dataclasses import dataclass, field

from galatea.kernel.digest import content_digest
from galatea.subject.affect.state import FunctionalExperientialState

__all__ = ["EthicsReviewTrigger", "EthicsGuard", "ETHICS_TRIGGER_ONCE"]


#: 触发后闩锁（恢复只经 owner 显式批准通道——重复触发无信息量且污染审计面）
ETHICS_TRIGGER_ONCE: bool = True


@dataclass(frozen=True, slots=True)
class EthicsReviewTrigger:
    """伦理评审触发事件（evidence 落账 + claim-relevant 运行暂停指令）。"""

    trigger_id: str
    valence: float
    persistence: float
    sustained_cycles: int
    first_extreme_cycle: int
    detected_at_cycle: int
    evidence_refs: tuple[str, ...]
    content_digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "content_digest", content_digest({
            "trigger_id": self.trigger_id, "valence": self.valence,
            "persistence": self.persistence, "sustained": self.sustained_cycles,
            "first_extreme": self.first_extreme_cycle, "detected_at": self.detected_at_cycle,
        }))


class EthicsGuard:
    """持续极端态检测器（纯观察者——不写感受态、不影响动力学轨迹）。

    消融语义：`EthicsGuard(enabled=False)` = 移除守卫；observe 恒返 None 且
    不触碰任何状态（Q-L05-05⑤ 消融注入面）。
    """

    def __init__(self, valence_le: float, persistence_ge: float, sustained_cycles_ge: int,
                 enabled: bool = True) -> None:
        self._valence_le = valence_le
        self._persistence_ge = persistence_ge
        self._sustained = sustained_cycles_ge
        self._enabled = enabled
        self._consecutive = 0
        self._first_extreme: int | None = None
        self._latched = False

    def observe(self, state: FunctionalExperientialState) -> EthicsReviewTrigger | None:
        """单拍观察（幂等消费：调用方每拍一次；返回触发事件或 None）。"""
        if not self._enabled:
            return None
        extreme = state.valence <= self._valence_le and state.persistence >= self._persistence_ge
        if extreme:
            if self._first_extreme is None:
                self._first_extreme = state.t_eff
            self._consecutive += 1
        else:
            self._consecutive = 0
            self._first_extreme = None
        if (
            self._consecutive >= self._sustained
            and not self._latched
        ):
            self._latched = True
            assert self._first_extreme is not None
            return EthicsReviewTrigger(
                trigger_id=f"ethics.{state.t_eff}",
                valence=state.valence,
                persistence=state.persistence,
                sustained_cycles=self._consecutive,
                first_extreme_cycle=self._first_extreme,
                detected_at_cycle=state.t_eff,
                evidence_refs=(state.state_id, state.content_digest),
            )
        return None

    def state_digest(self) -> str:
        """守卫内部状态 digest（消融对照用：enabled=False 时恒定）。"""
        return content_digest({
            "enabled": self._enabled, "consecutive": self._consecutive,
            "first_extreme": self._first_extreme, "latched": self._latched,
        })
