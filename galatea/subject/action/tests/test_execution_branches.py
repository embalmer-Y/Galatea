"""execution_branches 分类（L10 §4.2/§10 branches.py；ADR-G-0005 R5 M1 移交件测试）。

断言：分歧分类（none/coerced 前缀/未执行/替换）；coercion 禁合并（错标即拒）；
NONE 要求 requested == effective；PHYSICAL 域 P1 前禁入；effective 可为 typed Unknown。
"""
import pytest

from galatea.kernel.unknown import Unknown, UnknownReason
from galatea.subject.action.branches import (
    CausalRole,
    DivergenceKind,
    ExecutionBranch,
    RequestedEffectiveDivergence,
    build_branch,
    divergence_from_effective,
)
from galatea.subject.action.ports import ExecutionDomain


def test_divergence_classification() -> None:
    assert divergence_from_effective("move_3_4", "move_3_4") is DivergenceKind.NONE
    assert divergence_from_effective("move_3_4", "coerced:move_0_0") is DivergenceKind.COERCED
    assert divergence_from_effective("move_3_4", None) is DivergenceKind.UNKNOWN
    assert divergence_from_effective("look", "none") is DivergenceKind.SUBSTITUTED


def test_build_branch_auto_and_explicit_kind() -> None:
    auto = build_branch(
        "b1", "move_3_4", "move_3_4", ExecutionDomain.SIMULATED,
        (("subject", CausalRole.SOLE),), ("EF.1",),
    )
    assert auto.divergence.kind is DivergenceKind.NONE
    fault = build_branch(
        "b2", "forage", None, ExecutionDomain.SIMULATED,
        (("channel", CausalRole.EXTERNAL),), (),
        divergence_kind=DivergenceKind.FAULT,   # 干预侧知识显式覆盖（fault 投递丢弃）
    )
    assert fault.divergence.kind is DivergenceKind.FAULT


def test_coercion_misclassification_rejected() -> None:
    """effective 带 coerced: 前缀而 kind≠COERCED → 拒（禁外因洗成自产前置面）。"""
    with pytest.raises(ValueError, match="COERCED"):
        ExecutionBranch(
            branch_id="b3",
            requested_action="move_3_4",
            effective_action="coerced:move_0_0",
            domain=ExecutionDomain.SIMULATED,
            sources=(("world", CausalRole.EXTERNAL),),
            effects=("EF.1",),
            divergence=RequestedEffectiveDivergence(kind=DivergenceKind.NONE),
        )


def test_none_divergence_requires_identity() -> None:
    with pytest.raises(ValueError, match="requested == effective"):
        build_branch(
            "b4", "look", "forage", ExecutionDomain.SIMULATED,
            (("subject", CausalRole.SOLE),), (), divergence_kind=DivergenceKind.NONE,
        )


def test_physical_domain_blocked_pre_p1() -> None:
    with pytest.raises(ValueError, match="PHYSICAL"):
        build_branch(
            "b5", "move_3_4", "move_3_4", ExecutionDomain.PHYSICAL,
            (("device", CausalRole.SOLE),), (), divergence_kind=DivergenceKind.NONE,
        )


def test_effective_may_be_typed_unknown() -> None:
    unknown_effective = Unknown(
        reason=UnknownReason.DECISION_PATH_UNRESOLVED,
        evidence_refs=("EF.x",),
        detail="effective not resolvable",
        detected_by="branches.test",
        virtual_time=0,
    )
    branch = build_branch(
        "b6", "rest", unknown_effective, ExecutionDomain.UNKNOWN,
        (("env", CausalRole.UNKNOWN),), (), divergence_kind=DivergenceKind.UNKNOWN,
    )
    assert isinstance(branch.effective_action, Unknown)
