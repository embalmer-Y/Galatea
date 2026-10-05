"""Affordance 提取（L03 §2.2/§10 affordance.py；C3/C4 消费面，C1 构建合同）。

C1 MW0 affordance 面（action_class 枚举对齐 L10 五原语；Q-L03-06 affordance 枚举
细化留 C3/C4）：
- forage：前置 = 自身所在格（窗中心 (0,0)）资源占据后验 ≥ believe_threshold——
  置信 = 该格后验（感知推导）；
- eat：前置 = 储存食物 ≥1——从已收觅食/进食回执派生台账（Q-L08-09⑩ 语义）；
  回执缺失 → Unknown(INSUFFICIENT_OBSERVATION)，禁默认可食；
- rest / look：无前置（自持动作）——置信 1.0（无前置的恒可行动作，非估计值）。
禁写目标/意图（L03 §8 禁写路径）；仅 PERCEIVED 感知推导。
"""
import re
from dataclasses import dataclass

from galatea.kernel.unknown import Unknown, UnknownReason
from galatea.subject.c1profile import C1PerceptionParams
from galatea.subject.perception.fusion import OccupancyPosterior

_STORED_RE = re.compile(r"^forage_success_stored_(\d+)$")


@dataclass(frozen=True, slots=True)
class Affordance:
    """可供性（L03 §2.2：action_class, preconditions_est, confidence）。"""

    action_class: str
    preconditions_est: "float | Unknown"
    confidence: "float | Unknown"
    evidence_refs: tuple[str, ...]
    cycle_id: int

    def __post_init__(self) -> None:
        for name in ("preconditions_est", "confidence"):
            value = getattr(self, name)
            if isinstance(value, float) and not 0.0 <= value <= 1.0:
                raise ValueError(f"affordance {name} out of [0,1]: {value!r}")


def stored_food_from_receipts(effects: tuple[str, ...]) -> int | None:
    """已收回执 → 储存食物台账（Q-L08-09⑩：forage_success_stored_N 绝对计数 +
    eat_success −1；blocked/fault 不计）。无任何相关回执 → None（不可判定）。"""
    count: int | None = None
    for effect in effects:
        match = _STORED_RE.match(effect)
        if match:
            count = int(match.group(1))
        elif effect == "eat_success" and count is not None:
            count -= 1
    return count


def build_affordances(
    cells: tuple[OccupancyPosterior, ...], params: C1PerceptionParams,
    outcome_effects: tuple[str, ...], effective_time: int,
) -> tuple[Affordance, ...]:
    """逐 affordance 构建（确定性：action_class 升序）。"""
    center = next(
        (c for c in cells if c.dx == 0 and c.dy == 0), None
    )
    stored = stored_food_from_receipts(outcome_effects)
    out: list[Affordance] = []
    # forage：窗中心占据后验（感知推导）
    if center is not None:
        out.append(Affordance(
            action_class="forage",
            preconditions_est=center.posterior_present,
            confidence=center.posterior_present,
            evidence_refs=(center.evidence_frame_id,),
            cycle_id=effective_time,
        ))
    # eat：台账派生（回执缺失 → typed Unknown）
    if stored is None:
        eat_pre: "float | Unknown" = Unknown(
            reason=UnknownReason.INSUFFICIENT_OBSERVATION,
            evidence_refs=tuple(outcome_effects),
            detail="no forage/eat receipts in received effects（Q-L08-09⑩ 台账不可判定）",
            detected_by="perception.affordance",
            virtual_time=effective_time,
        )
        eat_conf: "float | Unknown" = eat_pre
    else:
        eat_pre = 1.0 if stored >= 1 else 0.0
        eat_conf = eat_pre
    out.append(Affordance(
        action_class="eat", preconditions_est=eat_pre, confidence=eat_conf,
        evidence_refs=tuple(outcome_effects), cycle_id=effective_time,
    ))
    # rest / look：自持动作（无前置）
    for action_class in ("look", "rest"):
        out.append(Affordance(
            action_class=action_class, preconditions_est=1.0, confidence=1.0,
            evidence_refs=(), cycle_id=effective_time,
        ))
    _ = params  # believe_threshold 经 center 后验链消费（forage 前置即后验）
    return tuple(sorted(out, key=lambda a: a.action_class))
