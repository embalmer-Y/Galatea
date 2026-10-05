"""L11 C1 件：有界适应提案接口（L11 §9 C1 行；Q-L11-01/Q-L11-06/Q-L04-10）。

C1 语义（proposal_only，冻结 profile learning.proposal_only = True）：
- 误差驱动的提案**只记录不生效**——适应面（转移/先验修正量）在 C1 期恒等于
  初始态（Q-L04-10：零计数 + Laplace 等价步长 0.125 起步）；
- 步长上界 0.125（2^-3）机械强制：|delta| > cap 即拒（BoundedAdaptationViolated）；
- 持久化 = checkpoint 增量 digest 引用制（Q-L11-06：重启复位 = 经历可抹除违反
  连续性语义）——台账 digest 供 checkpoint 增量承载；
- 层级化：三层误差等权 1:1:1 禁跨层归一（Q-L09-08）——提案按层独立记录。
"""
from dataclasses import dataclass, field
from enum import StrEnum

from galatea.kernel.digest import content_digest
from galatea.subject.c1profile import C1Profile


class BoundedAdaptationViolated(ValueError):
    """提案步长越上界（Q-L11-01：0.125 机械上界，越界即拒）。"""


class AdaptationLayer(StrEnum):
    """三层误差的提案层（Q-L09-08：感觉/知觉/模型等权独立）。"""

    SENSORY = "SENSORY"
    PERCEPTUAL = "PERCEPTUAL"
    MODEL = "MODEL"


PROPOSAL_STATUS_RECORDED = "RECORDED_ONLY"   # C1 恒定：提案不生效（L11 §9 C1 行）


@dataclass(frozen=True, slots=True)
class AdaptationProposal:
    """适应提案（不生效只记录；delta 有界强制；目标 = 适应承载表项引用）。"""

    proposal_id: str
    layer: AdaptationLayer
    target_ref: str
    delta: float
    error_refs: tuple[str, ...]
    cycle_id: int
    status: str = PROPOSAL_STATUS_RECORDED
    extra: tuple[tuple[str, str], ...] = field(default=())

    def __post_init__(self) -> None:
        if self.status != PROPOSAL_STATUS_RECORDED:
            raise ValueError(
                f"C1 proposal status must be {PROPOSAL_STATUS_RECORDED}（提案不生效只记录，L11 §9）"
            )
        if not self.error_refs:
            raise ValueError("adaptation proposal requires error_refs（误差驱动，禁无源提案）")


class AdaptationLedger:
    """提案台账（C1 适应面的唯一增量；checkpoint 增量 digest 承载，Q-L11-06）。"""

    def __init__(self, profile: C1Profile) -> None:
        self._cap = profile.learning.online_step_cap
        self._proposal_count = 0
        self._proposals: list[AdaptationProposal] = []

    def propose(
        self, layer: AdaptationLayer, target_ref: str, delta: float,
        error_refs: tuple[str, ...], cycle: int,
    ) -> AdaptationProposal:
        """登记提案（步长越界即拒；台账序号确定性）。"""
        if abs(delta) > self._cap:
            raise BoundedAdaptationViolated(
                f"|delta|={abs(delta)} exceeds online_step_cap={self._cap}"
                "（Q-L11-01：2^-3 机械上界）"
            )
        self._proposal_count += 1
        proposal = AdaptationProposal(
            proposal_id=f"adap.{cycle}.{self._proposal_count}",
            layer=layer, target_ref=target_ref, delta=delta,
            error_refs=error_refs, cycle_id=cycle,
        )
        self._proposals.append(proposal)
        return proposal

    def proposals(self) -> tuple[AdaptationProposal, ...]:
        """台账快照（append-only）。"""
        return tuple(self._proposals)

    def digest(self) -> str:
        """台账 digest（checkpoint 增量引用；空台账 = 零计数初始态 digest）。"""
        return content_digest({
            "step_cap": self._cap,
            "count": self._proposal_count,
            "proposals": [
                {"id": p.proposal_id, "layer": p.layer.value, "target": p.target_ref,
                 "delta": p.delta, "errors": list(p.error_refs)}
                for p in self._proposals
            ],
        })
