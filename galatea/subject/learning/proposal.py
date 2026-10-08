"""LearningProposal 构造与谱系强制（L11 §4.2 / §10 proposal.py；C5）。

五类 kind（L11 §4.2 枚举原文）；parent_digest 必填（无父即拒——防伪更新）；
metrics 向量 ≥2 维（禁单标量折叠，L11 §4.4）；data_scope/seed 随提案必带。
"""
import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict
from enum import StrEnum

from galatea.subject.learning.ports import LearningPlaneViolation

__all__ = ["ProposalKind", "DataScope", "LearningProposal"]


class ProposalKind(StrEnum):
    """五类（L11 §4.2 枚举原文；c5 profile kinds_enabled 同集）。"""

    ADAPTER = "ADAPTER"
    CALIBRATION = "CALIBRATION"
    WEIGHTS = "WEIGHTS"
    TABLE = "TABLE"
    POLICY_PARAMS = "POLICY_PARAMS"   # 有界标量（Q-L10-07：gateway policy 仅经 promotion）


@dataclass(frozen=True, slots=True)
class DataScope:
    """数据范围（run/branch/窗/条数/排除集——二阶纠偏可区分性的比较面）。"""

    run_ids: tuple[str, ...]
    branch_ids: tuple[str, ...]
    window: tuple[int, int]
    item_count: int
    exclusions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.run_ids or not self.branch_ids:
            raise ValueError("DataScope requires run_ids and branch_ids（可区分性前提）")
        if self.item_count < 0 or self.window[1] < self.window[0]:
            raise ValueError("DataScope item_count/window malformed")


@dataclass(frozen=True, slots=True)
class LearningProposal:
    """学习提案（候选不覆盖原工件——promotion 只切换 registry 引用，L11 §4.2）。"""

    proposal_id: str
    target_artifact: str
    kind: ProposalKind
    parent_digest: str
    data_scope: DataScope
    seed: int
    rng_stream_ref: str
    metrics_snapshot: Dict[str, float]      # 向量（≥2 维；维度名 → 值）
    content: Dict[str, float] = field(default_factory=dict[str, float])   # 工件数值面（TABLE 类条目）
    bounded: bool = True
    bound_ref: str | None = None

    def __post_init__(self) -> None:
        if not self.proposal_id or not self.target_artifact:
            raise ValueError("LearningProposal requires proposal_id and target_artifact")
        if len(self.parent_digest) < 16:
            raise ValueError(
                "LearningProposal requires parent_digest（无父即拒——伪更新防线，L11 §4.2）"
            )
        if len(self.metrics_snapshot) < 2:
            raise LearningPlaneViolation(
                f"metrics_snapshot must be a vector with >=2 dims（禁单标量折叠，L11 §4.4）: "
                f"{list(self.metrics_snapshot)}"
            )
        if not self.rng_stream_ref:
            raise ValueError("LearningProposal requires rng_stream_ref（承 L00 §4.3 派生流）")

    @property
    def content_digest(self) -> str:
        payload = json.dumps(
            {"proposal_id": self.proposal_id, "target": self.target_artifact,
             "kind": self.kind.value, "parent": self.parent_digest,
             "metrics": self.metrics_snapshot, "content": self.content,
             "scope": [self.data_scope.run_ids, self.data_scope.window]},
            sort_keys=True, separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
