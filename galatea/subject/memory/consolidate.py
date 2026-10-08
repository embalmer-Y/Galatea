"""T6 慢速巩固：类型级确定性合并（L06 §9 C5 行 + Q-L06-04；L11 §4.1 第三层协同）。

合并式 = (α·prior + positives) / (α + count)，α = 8（Q-L04-10 冻结常数——
Laplace 等价伪计数，步长 1/(α+n) ≤ 0.125 起步；c5 profile v1.1 物化）。
确定性、零 RNG；同计数 → 同合并值；巩固永不直写记忆库——产出 TABLE 类
LearningProposal 走 promotion（三层可塑性纪律，L11 §4.1）。
"""
from dataclasses import dataclass

from galatea.subject.learning.proposal import DataScope, LearningProposal, ProposalKind

__all__ = ["TypeCounts", "laplace_merge", "consolidate_types"]

ALPHA = 8   # Q-L04-10 冻结常数（c5 profile v1.1 物化——REV-0021 R3）


@dataclass(frozen=True, slots=True)
class TypeCounts:
    """类型级观测计数（同 patch 类型 × 同 regime 的经验计数——Q-L06-04②）。"""

    counts: dict[str, int]
    positives: dict[str, int]

    def __post_init__(self) -> None:
        if set(self.counts) != set(self.positives):
            raise ValueError("TypeCounts keys mismatch（每类须双计数）")
        for k in self.counts:
            if self.counts[k] < 0 or not 0 <= self.positives[k] <= self.counts[k]:
                raise ValueError(f"TypeCounts[{k}] malformed（positives ≤ count）")


def laplace_merge(prior: float, count: int, positives: int) -> float:
    """Laplace 合并（域保持 ∈ (0,1)；零计数 → 先验原值）。"""
    if not 0.0 < prior < 1.0:
        raise ValueError(f"prior out of (0,1): {prior!r}")
    return (ALPHA * prior + positives) / (ALPHA + count)


def consolidate_types(counts: TypeCounts, priors: dict[str, float],
                      proposal_id: str, parent_digest: str, run_id: str,
                      cycle: int) -> LearningProposal:
    """类型级合并 → TABLE 类 LearningProposal（巩固候选——永不直写）。"""
    merged = {
        k: round(laplace_merge(priors[k], counts.counts[k], counts.positives[k]), 10)
        for k in counts.counts
    }
    if len(merged) < 2:
        raise ValueError("consolidation requires >=2 type dims（反塌缩 schema 面）")
    return LearningProposal(
        proposal_id=proposal_id,
        target_artifact="semantic.type_level",
        kind=ProposalKind.TABLE,
        parent_digest=parent_digest,
        data_scope=DataScope(
            run_ids=(run_id,), branch_ids=("B",), window=(0, cycle),
            item_count=sum(counts.counts.values()),
        ),
        seed=0,
        rng_stream_ref="(learning,consolidation)",
        metrics_snapshot={"coverage": sum(counts.counts.values()) / 64.0,
                          "type_dims": float(len(merged))},
        content=merged,
    )
