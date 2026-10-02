"""ExpansionDecision 记录与门规则（L13 §2.2 evd.expansion_decision / HLD §10.2–10.3）。

纪律（Q-L13-03）：与 EvidenceResult **分别记录、双签发者**——本模块独立签发，
仅可消费根 EvidenceResult 的 digest（禁携带统计中间态）；ALLOW_NEXT_STAGE 的
前置 = REV 独立评审引用（Q-DEV-05）+ 绑定物齐备（HLD §10.3）。
门规则（HLD §10.2 R0 行）：SUPPORTED 无约束 → 可 ALLOW；有约束/INCONCLUSIVE →
HOLD；REFUTED → REWORK。
"""
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from galatea.evidence.evaluator.hypotheses import EvidenceResult, HypothesisVerdict
from galatea.kernel.digest import content_digest

__all__ = [
    "ExpansionOutcome",
    "ExpansionDecision",
    "decide_from_root",
    "StatPlanRefMissing",
    "collect_binding_digests",
]


def collect_binding_digests(root: Path) -> tuple[tuple[str, str], ...]:
    """HLD §10.3 绑定物收集器（Q-L13-11②；REV-0010 R4 计算域成文：config 合同 digest
    = canonical content_digest(文件 UTF-8 文本)，relpath 排序，posix 键）。"""
    entries: list[tuple[str, str]] = []
    config_dir = root / "config"
    for path in sorted(config_dir.rglob("*.y*ml")):
        entries.append((path.relative_to(root).as_posix(), content_digest(path.read_text(encoding="utf-8"))))
    return tuple(entries)


class ExpansionOutcome(StrEnum):
    """扩展决定三态（HLD §10.2 R0 行）。"""

    ALLOW_NEXT_STAGE = "ALLOW_NEXT_STAGE"
    HOLD = "HOLD"
    REWORK = "REWORK"


class StatPlanRefMissing(ValueError):
    """绑定物缺失（root stat plan digest 未提供 → 签发拒绝，HLD §10.3）。"""


@dataclass(frozen=True, slots=True)
class ExpansionDecision:
    """扩展授权决定（签发者 = gate/expansion.py；与 EvidenceResult 分离记录）。"""

    decision_id: str
    stage: str                                    # "R0"
    decision: ExpansionOutcome
    root_evidence_digest: str                     # 根结果内容 digest（非对象引用——签发隔离）
    basis_evidence_ids: tuple[str, ...]
    constraints: tuple[str, ...]                  # HOLD 约束（ALLOW 须为空）
    bound_digests: tuple[tuple[str, str], ...]    # HLD §10.3 绑定物（名, digest）
    rev_review_ref: str                           # REV 独立评审引用（ALLOW 前置）
    independent_of: str                           # 根结果签发者声明（Q-L13-03）
    reason: str = ""

    @property
    def digest(self) -> str:
        """canonical digest（分别记录的载体；入 registry kind=governance:expansion_decision）。"""
        return content_digest(
            {
                "decision_id": self.decision_id,
                "stage": self.stage,
                "decision": self.decision.value,
                "root_evidence_digest": self.root_evidence_digest,
                "basis_evidence_ids": list(self.basis_evidence_ids),
                "constraints": list(self.constraints),
                "bound_digests": [list(b) for b in self.bound_digests],
                "rev_review_ref": self.rev_review_ref,
                "independent_of": self.independent_of,
                "reason": self.reason,
            }
        )

    def __post_init__(self) -> None:
        if not self.root_evidence_digest:
            raise StatPlanRefMissing("ExpansionDecision requires root evidence digest（HLD §10.3 绑定物）")
        if not self.bound_digests:
            raise StatPlanRefMissing("ExpansionDecision requires bound digests（HLD §10.3：profile/system/artifact）")
        if self.decision is ExpansionOutcome.ALLOW_NEXT_STAGE:
            if not self.rev_review_ref:
                raise StatPlanRefMissing("ALLOW_NEXT_STAGE requires an independent REV review ref（Q-L13-03③）")
            if self.constraints:
                raise StatPlanRefMissing(
                    "ALLOW_NEXT_STAGE must be unconstrained; constrained outcomes are HOLD（HLD §10.2）"
                )


def decide_from_root(
    root: EvidenceResult, constraints: tuple[str, ...] = ()
) -> ExpansionOutcome:
    """HLD §10.2 R0 行的机械映射：SUPPORTED 无约束 → ALLOW；有约束/INCONCLUSIVE →
    HOLD；REFUTED → REWORK。"""
    if root.verdict is HypothesisVerdict.REFUTED:
        return ExpansionOutcome.REWORK
    if root.verdict is HypothesisVerdict.INCONCLUSIVE:
        return ExpansionOutcome.HOLD
    return ExpansionOutcome.HOLD if constraints else ExpansionOutcome.ALLOW_NEXT_STAGE
