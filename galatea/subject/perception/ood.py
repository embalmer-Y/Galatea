"""OOD 评分与 abstain 判定（L03 §4.4/§10 ood.py；Q-L03-02 事件级域出，零连续阈值）。

规则（c1 profile ood_rule = event_level_domain_exit）：特征越冻结定义域即 OOD——
窗值越 [0,1]、事件种越 EVENT_KINDS、朝向越 ORIENTATION_TOKENS、距离键越冻结增益表。
abstain = binary（Q-L03-02）：believe_threshold 判定，分级承诺留 C2。
abstain 可复算：candidates_considered + threshold_ref 完整留存（L03 §4.4）。
"""
from dataclasses import dataclass

from galatea.kernel.unknown import Unknown, UnknownReason
from galatea.subject.c1profile import C1PerceptionParams, EVENT_KINDS, ORIENTATION_TOKENS
from galatea.subject.perception.fusion import LikelihoodTable


@dataclass(frozen=True, slots=True)
class OodAssessment:
    """事件级 OOD 评估（flag 二值；score 恒 1.0 = 事件发生，无连续阈值）。"""

    ood_flag: bool
    ood_score: float
    reasons: tuple[str, ...]
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.ood_flag and self.ood_score != 1.0:
            raise ValueError("event-level OOD score is binary（Q-L03-02 零连续阈值）")


def assess_ood(
    window: tuple[tuple[float, ...], ...] | None,
    event_kinds: tuple[str, ...],
    orientation: str | None,
    table: LikelihoodTable,
    frame_ids: tuple[str, ...],
    cycle: int,
) -> OodAssessment:
    """域出检测（全部冻结域：值域/事件集/朝向集/增益表距离键）。"""
    reasons: list[str] = []
    if window is not None:
        for r, row_values in enumerate(window):
            for c, value in enumerate(row_values):
                if not 0.0 <= float(value) <= 1.0:
                    reasons.append(f"window[{r}][{c}]={value!r} outside [0,1]")
    for kind in event_kinds:
        if kind not in EVENT_KINDS:
            reasons.append(f"event kind {kind!r} outside frozen enum（Q-L01-08 M0 事件集）")
    if orientation is not None and orientation not in ORIENTATION_TOKENS:
        reasons.append(f"orientation {orientation!r} outside frozen tokens")
    if window is not None and len(window) > 0:
        offset = (len(window) - 1) // 2
        dist_key = f"d{offset}"
        try:
            table.row("present", dist_key)
        except Exception:
            reasons.append(f"distance key {dist_key!r} outside frozen gain map")
    return OodAssessment(
        ood_flag=bool(reasons),
        ood_score=1.0 if reasons else 0.0,
        reasons=tuple(reasons),
        evidence_refs=frame_ids,
    )


@dataclass(frozen=True, slots=True)
class AbstainEvent:
    """一等输出：弃权事件（L03 §2.2/§4.4；不是异常，禁以高置信假设填补）。"""

    abstain_id: str
    reason: Unknown
    candidates_considered: tuple[str, ...]   # 候选假设内容引用（可复算）
    threshold_ref: str                        # believe_threshold 来源（c1 profile ref）
    cycle_id: int


def should_abstain(
    top_posterior: float | None, params: C1PerceptionParams, ood: OodAssessment
) -> bool:
    """abstain 判定：OOD 触发，或最高后验 < believe_threshold（Q-L03-02）。"""
    if ood.ood_flag:
        return True
    if top_posterior is None:
        return True
    return top_posterior < params.believe_threshold


def abstain_reason(cycle: int, ood: OodAssessment) -> Unknown:
    """abstain 原因类型化：OOD 域出 vs 证据不足（L03 §6 失败模式两行）。"""
    if ood.ood_flag:
        return Unknown(
            reason=UnknownReason.OOD,
            evidence_refs=ood.evidence_refs,
            detail="; ".join(ood.reasons),
            detected_by="perception.ood",
            virtual_time=cycle,
        )
    return Unknown(
        reason=UnknownReason.INSUFFICIENT_OBSERVATION,
        evidence_refs=ood.evidence_refs,
        detail="top posterior below believe_threshold（Q-L03-02）",
        detected_by="perception.ood",
        virtual_time=cycle,
    )
