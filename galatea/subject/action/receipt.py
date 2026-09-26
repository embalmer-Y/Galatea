"""ActionChainReceipt（L10 §2.2 act.receipt / §10 receipt.py）。

ADR-G-0005 R5 移交件（M1）：行动链回执 = 链条 id 集 + 校验记录 + 分支引用，
EVIDENCE_ONLY，digest = canonical JSON sha256（kernel.digest，L00 §4.4）——
5×5 干预矩阵逐格回执的证据载体（ADR-G-0005 R5 口径钉死：M0 逐类首测，
全矩阵实例化与 blocked 回执归 M1）。
"""
from dataclasses import dataclass

from galatea.kernel.digest import content_digest

__all__ = ["ActionChainReceipt"]


@dataclass(frozen=True, slots=True)
class ActionChainReceipt:
    """行动链回执（L10 §2.2：chain_ids[]/checks[]/branch_refs[]；EVIDENCE_ONLY）。"""

    chain_ids: tuple[str, ...]
    checks: tuple[str, ...]               # AuthorizationDecision/校验记录引用
    branch_refs: tuple[str, ...]          # execution_branches[] 引用（EVIDENCE_ONLY 侧）
    digest: str

    def __post_init__(self) -> None:
        if not self.chain_ids:
            raise ValueError("ActionChainReceipt requires chain_ids")
        if not self.digest:
            raise ValueError("ActionChainReceipt requires digest")

    @staticmethod
    def build(
        chain_ids: tuple[str, ...],
        checks: tuple[str, ...],
        branch_refs: tuple[str, ...],
    ) -> "ActionChainReceipt":
        """digest 与字段一致地构造（canonical JSON sha256）。"""
        return ActionChainReceipt(
            chain_ids=chain_ids,
            checks=checks,
            branch_refs=branch_refs,
            digest=content_digest(
                {
                    "chain_ids": list(chain_ids),
                    "checks": list(checks),
                    "branch_refs": list(branch_refs),
                }
            ),
        )
