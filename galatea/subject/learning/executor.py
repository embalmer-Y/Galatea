"""promotion ACCEPTED 执行器（REV-0022 R1①③硬前置）。

职责（L11 §4.5 原文的承载代码）：门 ACCEPTED → (1) registry 引用切换（候选
入 registry + 当前有效引用指向新 digest，原工件与谱系保留）；(2) Consolidation
LearnReceipt 签发（谱系三元组）；(3) 学习者侧 ReadOnlyDecisionView 注入。
防伪/防刷由 gate 侧已裁决（Ledger）；本模块零决策权（自批禁止——只消费 decision）。
"""
import json
from dataclasses import dataclass

from galatea.kernel.registry import Registry
from galatea.subject.learning.proposal import LearningProposal
from galatea.subject.learning.receipt import ConsolidationLearnReceipt

__all__ = ["PromotionExecutor", "promote"]


@dataclass(frozen=True, slots=True)
class PromotionExecutor:
    """执行器绑定（registry 实例 + 决策引用——全部由装配层注入）。"""

    registry: Registry
    decision_ref: str          # PromotionDecision 的 digest（gate 侧签发留痕）

    def promote(self, proposal: LearningProposal, accepted_at_cycle: int) -> ConsolidationLearnReceipt:
        """ACCEPTED 执行（三步，顺序固定）：
        1. 候选工件入 registry（kind=learning:artifact，parent 谱系 = 提案 parent）；
        2. ConsolidationLearnReceipt 签发（proposal/activated/parent 三元组）；
        3. 回执 digest 返回（registry 引用切换面由调用方按 receipt 承载——
           引用表 = subject_state 侧 checkpoint 载体，本执行器不触碰证据平面外状态）。"""
        blob = json.dumps(proposal.content, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ref = self.registry.put(
            blob, kind="learning:artifact",
            parent_digests=(proposal.parent_digest,),
        )
        return ConsolidationLearnReceipt(
            proposal_digest=proposal.content_digest,
            activated_digest=ref.digest,
            parent_digest=proposal.parent_digest,
            decision_ref=self.decision_ref,
            accepted_at_cycle=accepted_at_cycle,
        )


def promote(
    proposal: LearningProposal, registry: Registry, decision_ref: str, accepted_at_cycle: int
) -> ConsolidationLearnReceipt:
    """模块级便捷入口（executor 语义同上）。"""
    return PromotionExecutor(registry, decision_ref).promote(proposal, accepted_at_cycle)
