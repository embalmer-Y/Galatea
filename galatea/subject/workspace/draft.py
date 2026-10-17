"""假设槽草稿板（L07 P4-β 扩展——Q-L07-09；profile p4_beta_mind scratchpad 节）。

合同（Q-L07-09）：
- **非信念原则**：草稿板条目不是信念——DraftHypothesis 禁直进 L03 believe_threshold
  面与 L04 信念图；晋升只经 Q-L07-10 评估回路显式产出（逐案留痕）。本模块零 import
  perception/models 信念面（结构守卫 test_draft_no_belief_plane 消费）；
- **写权限**（③）：供体白名单 = L03 假设槽 / L04 rollout / L09 控制器提案 /
  L07 思维循环（generate/revise 拍）——白名单外提交 = UnauthorizedDraftDonor
  （UnauthorizedWrite 家族语义，S1）；
- **状态机**（①）：open → evaluated → superseded|contradicted（禁跳级、禁复活——
  终态写后二次转移 = DraftStateViolation）；
- **确定性**（④）：全状态（草稿 + 评分 + 回执）入 snapshot（Q-L13-17 同族形态），
  state_digest 供 checkpoint 审计字段；
- **层级纪律**（⑤）：草稿板是跨模块聚合层——provenance_ref 引用源对象（感觉帧/
  rollout/记忆/控制器提案），禁复制内容（引用不复制）。
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, cast

from galatea.kernel.digest import content_digest

__all__ = [
    "DraftStatus",
    "DraftDonor",
    "DraftHypothesis",
    "DraftEvaluation",
    "UnauthorizedDraftDonor",
    "DraftStateViolation",
    "DraftSchemaViolation",
    "Scratchpad",
]


class DraftStatus(enum.StrEnum):
    """草稿状态词表（profile scratchpad.status_vocabulary 冻结四态）。"""

    OPEN = "open"
    EVALUATED = "evaluated"
    SUPERSEDED = "superseded"
    CONTRADICTED = "contradicted"


class DraftDonor(enum.StrEnum):
    """写权限矩阵（Q-L07-09③：既有权限矩阵的草稿板扩展——白名单外 = 拒）。"""

    PERCEPTION_HYPOTHESIS = "perception_hypothesis"   # L03 假设槽
    MODELS_ROLLOUT = "models_rollout"                 # L04 rollout
    CONTROLLER_PROPOSAL = "controller_proposal"       # L09 控制器提案
    WORKSPACE_LOOP = "workspace_loop"                 # L07 思维循环 generate/revise 拍


class UnauthorizedDraftDonor(ValueError):
    """白名单外供体提交（Q-L07-09③——UnauthorizedWrite 家族，S1）。"""


class DraftStateViolation(ValueError):
    """状态机违例（跳级/终态复活/未知 hypothesis_id 转移）。"""


class DraftSchemaViolation(ValueError):
    """DraftHypothesis 合同不符（空 claim / 空 provenance_ref / confidence 越域 / 引用复制）。"""


@dataclass(frozen=True, slots=True)
class DraftHypothesis:
    """草稿假设（Q-L07-09① 冻结 schema；payload 为域数据 = 引用与判据素材，非信念内容）。"""

    hypothesis_id: str
    claim: str
    provenance_ref: str          # 出处引用（感觉帧/rollout/记忆/控制器提案的 registry ref）
    confidence: float            # [0,1]
    created_cycle: int
    donor: DraftDonor
    status: DraftStatus = DraftStatus.OPEN
    payload: dict[str, Any] = field(default_factory=lambda: dict[str, Any]())

    def __post_init__(self) -> None:
        if not self.hypothesis_id or not self.claim or not self.provenance_ref:
            raise DraftSchemaViolation("draft requires hypothesis_id/claim/provenance_ref（Q-L07-09①）")
        if not 0.0 <= self.confidence <= 1.0:
            raise DraftSchemaViolation(f"confidence out of [0,1]: {self.confidence!r}")
        if type(self.donor) is not DraftDonor:   # 运行时合同守卫（位置传参误用面）
            raise DraftSchemaViolation("donor must be DraftDonor（白名单矩阵外提交禁入）")
        if type(self.status) is not DraftStatus:
            raise DraftSchemaViolation("status must be DraftStatus")

    def with_status(self, status: DraftStatus) -> DraftHypothesis:
        from dataclasses import replace
        return replace(self, status=status)


@dataclass(frozen=True, slots=True)
class DraftEvaluation:
    """评估记录（evaluate 拍产物；draft 本体不可变——评分挂账不写条目）。"""

    hypothesis_id: str
    cycle: int
    score: float
    evaluator_ref: str            # 评分源引用（rssm_imagine_rollout / 测试合成源）
    beat: int                     # 思维循环拍号


class Scratchpad:
    """草稿板（Q-L07-09——跨模块聚合层；单写者 = 本类唯一变更入口）。

    层级纪律（⑤）：只存 DraftHypothesis 与 DraftEvaluation，不复制源内容；
    禁提供任何返回"已确证信念"语义的面（非信念原则的 API 形状承诺）。
    """

    def __init__(self) -> None:
        self._drafts: dict[str, DraftHypothesis] = {}
        self._evaluations: dict[str, tuple[DraftEvaluation, ...]] = {}

    # —— 写面（供体白名单强制）——
    def submit(self, draft: DraftHypothesis) -> DraftHypothesis:
        if draft.hypothesis_id in self._drafts:
            raise DraftStateViolation(f"duplicate hypothesis_id: {draft.hypothesis_id}")
        self._drafts[draft.hypothesis_id] = draft
        return draft

    def submit_from(self, donor: str, **kwargs: Any) -> DraftHypothesis:
        """供体面提交（donor 串 → 白名单校验后构造；矩阵外 = UnauthorizedDraftDonor）。"""
        try:
            donor_enum = DraftDonor(donor)
        except ValueError as exc:
            raise UnauthorizedDraftDonor(f"donor {donor!r} not in scratchpad write matrix（Q-L07-09③）") from exc
        return self.submit(DraftHypothesis(donor=donor_enum, **kwargs))

    def evaluate(self, hypothesis_id: str, evaluation: DraftEvaluation) -> DraftEvaluation:
        draft = self._require(hypothesis_id)
        if draft.status is not DraftStatus.OPEN:
            raise DraftStateViolation(f"evaluate requires open draft, got {draft.status.value}")
        if evaluation.hypothesis_id != hypothesis_id:
            raise DraftSchemaViolation("evaluation hypothesis_id mismatch")
        self._evaluations.setdefault(hypothesis_id, ())
        self._evaluations[hypothesis_id] = self._evaluations[hypothesis_id] + (evaluation,)
        self._drafts[hypothesis_id] = draft.with_status(DraftStatus.EVALUATED)
        return evaluation

    def supersede(self, hypothesis_id: str, successor_id: str) -> None:
        """修正转移（revise 拍：被替代者留痕；后继须已存在——禁悬空引用）。"""
        draft = self._require(hypothesis_id)
        if draft.status is not DraftStatus.EVALUATED:
            raise DraftStateViolation(f"supersede requires evaluated draft, got {draft.status.value}")
        successor = self._require(successor_id)
        if successor.donor is not DraftDonor.WORKSPACE_LOOP:
            raise DraftStateViolation("supersede successor must come from workspace_loop（revise 拍供体）")
        self._drafts[hypothesis_id] = draft.with_status(DraftStatus.SUPERSEDED)

    def contradict(self, hypothesis_id: str) -> None:
        draft = self._require(hypothesis_id)
        if draft.status is not DraftStatus.EVALUATED:
            raise DraftStateViolation(f"contradict requires evaluated draft, got {draft.status.value}")
        self._drafts[hypothesis_id] = draft.with_status(DraftStatus.CONTRADICTED)

    # —— 读面（非信念原则：无"确证"语义出口；conflicts/status 原样可审计）——
    def _require(self, hypothesis_id: str) -> DraftHypothesis:
        draft = self._drafts.get(hypothesis_id)
        if draft is None:
            raise DraftStateViolation(f"unknown hypothesis_id: {hypothesis_id}")
        return draft

    def get(self, hypothesis_id: str) -> DraftHypothesis:
        return self._require(hypothesis_id)

    def by_status(self, status: DraftStatus) -> tuple[DraftHypothesis, ...]:
        return tuple(d for d in self._drafts.values() if d.status is status)

    def all_drafts(self) -> tuple[DraftHypothesis, ...]:
        return tuple(sorted(self._drafts.values(), key=lambda d: d.hypothesis_id))

    def evaluations_of(self, hypothesis_id: str) -> tuple[DraftEvaluation, ...]:
        return self._evaluations.get(hypothesis_id, ())

    def latest_score(self, hypothesis_id: str) -> float | None:
        evals = self.evaluations_of(hypothesis_id)
        return evals[-1].score if evals else None

    # —— 快照面（Q-L07-09④；Q-L13-17 同族）——
    def state_digest(self) -> str:
        return content_digest(self.snapshot())

    def snapshot(self) -> dict[str, Any]:
        return {
            "drafts": [
                {
                    "hypothesis_id": d.hypothesis_id,
                    "claim": d.claim,
                    "provenance_ref": d.provenance_ref,
                    "confidence": d.confidence,
                    "created_cycle": d.created_cycle,
                    "donor": d.donor.value,
                    "status": d.status.value,
                    "payload": _freeze_payload(d.payload),
                }
                for d in self.all_drafts()
            ],
            "evaluations": [
                {
                    "hypothesis_id": h,
                    "cycle": e.cycle,
                    "score": e.score,
                    "evaluator_ref": e.evaluator_ref,
                    "beat": e.beat,
                }
                for h in sorted(self._evaluations)
                for e in self._evaluations[h]
            ],
        }

    def restore_snapshot(self, state: dict[str, Any]) -> None:
        """快照恢复（全量替换；逐条目过构造合同——被篡改快照 fail closed）。"""
        if set(state) != {"drafts", "evaluations"}:
            raise DraftSchemaViolation("snapshot shape violation")
        drafts: dict[str, DraftHypothesis] = {}
        evaluations: dict[str, tuple[DraftEvaluation, ...]] = {}
        for row in state["drafts"]:
            draft = DraftHypothesis(
                hypothesis_id=row["hypothesis_id"], claim=row["claim"],
                provenance_ref=row["provenance_ref"], confidence=row["confidence"],
                created_cycle=row["created_cycle"], donor=DraftDonor(row["donor"]),
                status=DraftStatus(row["status"]), payload=dict(row["payload"]),
            )
            drafts[draft.hypothesis_id] = draft
        for row in state["evaluations"]:
            hid = row["hypothesis_id"]
            if hid not in drafts:
                raise DraftStateViolation(f"evaluation references unknown draft: {hid}")
            if drafts[hid].status is DraftStatus.OPEN:
                raise DraftStateViolation("snapshot has evaluation for open draft")
            e = DraftEvaluation(
                hypothesis_id=hid, cycle=row["cycle"], score=row["score"],
                evaluator_ref=row["evaluator_ref"], beat=row["beat"],
            )
            evaluations[hid] = evaluations.get(hid, ()) + (e,)
        self._drafts = drafts
        self._evaluations = evaluations


def _freeze_payload(payload: dict[str, Any]) -> list[tuple[str, Any]]:
    """payload 规范化（排序键值对列表——digest 稳定；值须 JSON 可容型）。"""
    out: list[tuple[str, Any]] = []
    for key in sorted(payload):
        value: Any = payload[key]
        if isinstance(value, (str, int, float, bool)) or value is None:
            out.append((key, value))
        elif isinstance(value, (tuple, list)):
            items = cast(list[Any], value)
            out.append((key, [str(v) for v in items]))
        else:
            raise DraftSchemaViolation(f"payload value not snapshot-safe: {key}")
    return out
