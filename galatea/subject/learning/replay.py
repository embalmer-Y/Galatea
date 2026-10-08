"""replay：经历重放计划与确定性选择（L11 §4.3 / §10 replay.py；Q-L11-02）。

等权 1:1:1:1（情感标注/新颖性/误差/时间多样性——零参数先例链第七次）；
budget 每 T6 重放 8 条（调度挂 T5 拍、记账窗 = T6——L11 §5 节拍注记 REV-0021 R6）；
同 (seed, plan) → 同序列（选择 = 纯排序零采样：等权和降序、tie 按 id 升序；
RNG 流 (learning,replay,proposal_id) 供重放内容面按需消费，选择序本身确定性）；
PROTECTED 项排除出降级/遗忘面（protection.py 拒绝面承载）；AffectiveValueTag
只入此优先级、不入任何目标函数（L11 §4.4——objectives 断言 + CI 面）。
replay 只读 L06 事件引用——不重放 recorder 真值、不用 evaluator 标签（泄漏纪律）。
"""
import hashlib
from dataclasses import dataclass

from galatea.subject.c5profile import C5ContinuedLearningParams

__all__ = ["ReplayItem", "ReplayPlan", "replay_select"]

_WEIGHT_KEYS = ("affective_tag", "novelty", "error_magnitude", "time_diversity")


@dataclass(frozen=True, slots=True)
class ReplayItem:
    """可重放条目视图（只读事件引用——禁真值引用，test_replay_no_truth 承载）。"""

    item_id: str
    affective_tag: float
    novelty: float
    error_magnitude: float
    time_diversity: float
    event_ref: str          # L06 事件引用

    def score(self, weights: dict[str, float]) -> float:
        return sum(getattr(self, k) * w for k, w in weights.items())


@dataclass(frozen=True, slots=True)
class ReplayPlan:
    """重放计划（c5 profile 冻结值；RNG 流 = (learning,replay,proposal_id)）。"""

    weights: dict[str, float]
    budget_per_t6: int
    proposal_id: str

    def rng_stream(self, seed: int) -> bytes:
        """RNG 流（L11 §4.3 原文格式；同 (seed, plan) → 同流）。"""
        return hashlib.sha256(
            f"learning|replay|{self.proposal_id}|{seed}".encode()
        ).digest()


def replay_select(items: tuple[ReplayItem, ...], plan: ReplayPlan,
                  params: C5ContinuedLearningParams) -> tuple[str, ...]:
    """确定性选择（等权和降序、tie 按 item_id 升序；budget 截断）。"""
    if set(plan.weights) != set(_WEIGHT_KEYS):
        raise ValueError(f"ReplayPlan weights keys mismatch: {sorted(plan.weights)}")
    if any(v != 1.0 for v in plan.weights.values()):
        raise ValueError("replay weights must stay 1.0（等权冻结——偏离 = profile 篡改）")
    budget = min(plan.budget_per_t6, params.replay_budget_per_t6)
    ranked = sorted(items, key=lambda it: (-it.score(plan.weights), it.item_id))
    return tuple(it.item_id for it in ranked[:budget])
