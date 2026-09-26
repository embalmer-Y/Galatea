"""ActionChainReceipt（L10 §10 receipt.py；ADR-G-0005 R5：blocked 回执载体 + 5×5 矩阵证据面）。

断言：digest 与字段一致（同字段同 digest、异字段异 digest）；空链条拒绝；
blocked 场景回执可构造（拒绝类型化进入 checks，无分支引用）。
"""
import pytest

from galatea.subject.action.branches import CausalRole, DivergenceKind, build_branch
from galatea.subject.action.receipt import ActionChainReceipt
from galatea.subject.action.ports import ExecutionDomain


def _branch(branch_id: str = "b1") -> str:
    return build_branch(
        branch_id, "move_3_4", "move_3_4", ExecutionDomain.SIMULATED,
        (("subject", CausalRole.SOLE),), ("EF.1",),
    ).branch_id


def test_digest_consistent_and_sensitive() -> None:
    a = ActionChainReceipt.build(("chain.1",), ("authz.1",), (_branch("b1"),))
    b = ActionChainReceipt.build(("chain.1",), ("authz.1",), (_branch("b1"),))
    assert a.digest == b.digest
    c = ActionChainReceipt.build(("chain.1",), ("authz.2",), (_branch("b1"),))
    assert c.digest != a.digest


def test_blocked_receipt_constructible() -> None:
    """ADR-G-0005 R5：blocked 回执载体——拒绝类型化入 checks、无分支引用（命令未执行）。"""
    receipt = ActionChainReceipt.build(
        chain_ids=("chain.blocked",),
        checks=("authz.rejected:CONTAINMENT_VIOLATION",),
        branch_refs=(),   # 无执行分支
    )
    assert receipt.chain_ids == ("chain.blocked",)
    assert receipt.branch_refs == ()


def test_empty_chain_rejected() -> None:
    with pytest.raises(ValueError, match="chain_ids"):
        ActionChainReceipt(chain_ids=(), checks=(), branch_refs=(), digest="d" * 64)
