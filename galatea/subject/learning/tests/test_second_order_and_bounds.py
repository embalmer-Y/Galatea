"""二阶纠偏 + 回退优先级 + 有界面 + 学习面禁写（L11 §4.5/§4.1；Q-L09-05）。"""
import pytest

from galatea.subject.learning.layers.online import (
    BoundViolation, BoundedAdaptation, propose_policy_params,
)
from galatea.subject.learning.ports import (
    LearningPlaneViolation, assert_learning_cannot_write_policy,
)
from galatea.subject.learning.proposal import DataScope, LearningProposal, ProposalKind
from galatea.subject.learning.rollback import RollbackRequest, RollbackTrigger
from galatea.subject.learning.second_order import build_correction, scopes_distinguishable


def _proposal(scope: DataScope, pid: str = "prop.1") -> LearningProposal:
    return LearningProposal(
        proposal_id=pid, target_artifact="semantic.type_level", kind=ProposalKind.TABLE,
        parent_digest="d" * 64, data_scope=scope, seed=0,
        rng_stream_ref="(learning,replay,prop.1)",
        metrics_snapshot={"coverage": 10.0, "type_dims": 2.0},
    )


def test_second_order_correction_distinguishable() -> None:
    """纠偏闭环：排除致害 run 的再提案可区分；原样重提即拒。"""
    first = DataScope(("r1", "r2"), ("B",), (0, 64), 10)
    corrected_scope = DataScope(("r3",), ("B",), (0, 64), 8)
    assert scopes_distinguishable(first, corrected_scope)
    rb = RollbackRequest(RollbackTrigger.HARMFUL_UPDATE, "semantic.type_level",
                         "d" * 64, ("ev-1",))
    correction = build_correction(rb, first, _proposal(corrected_scope))
    assert correction.distinguished
    with pytest.raises(ValueError, match="indistinguishable"):
        build_correction(rb, first, _proposal(DataScope(("r1", "r2"), ("B",), (0, 64), 12)))


def test_online_bound_enforcement() -> None:
    step = BoundedAdaptation("adaptive_gain", 1.0, 1.4)
    assert step.applied() == 1.4
    with pytest.raises(BoundViolation, match="promotion"):
        BoundedAdaptation("adaptive_gain", 1.0, 2.5).applied()
    with pytest.raises(BoundViolation):
        BoundedAdaptation("adaptive_gain", 1.0, 0.1).applied()
    assert propose_policy_params("adaptive_gain", 2.5) == "policy_params.adaptive_gain"
    with pytest.raises(ValueError, match="界内"):
        propose_policy_params("adaptive_gain", 1.2)


def test_learning_cannot_write_immutable_surfaces() -> None:
    """核心权限/安全/证据不可在线修改（L11 §9 C5 行——权限测试面）。"""
    for target in ("PERMISSION_MATRIX", "CONTAINMENT_WHITELIST", "PROTECTION_SUITE_ROSTER",
                   "SEALED_NAMESPACE", "CORE_DECISION_REGISTRY"):
        with pytest.raises(LearningPlaneViolation):
            assert_learning_cannot_write_policy(target)


def test_proposal_requires_parent_and_vector() -> None:
    scope = DataScope(("r1",), ("B",), (0, 8), 4)
    with pytest.raises(ValueError, match="parent_digest"):
        _proposal(scope). __class__(  # noqa: SLF001 — 构造面测试
            proposal_id="x", target_artifact="t", kind=ProposalKind.TABLE,
            parent_digest="short", data_scope=scope, seed=0,
            rng_stream_ref="s", metrics_snapshot={"a": 1.0, "b": 2.0})
    with pytest.raises(LearningPlaneViolation, match=">=2 dims"):
        LearningProposal(
            proposal_id="x", target_artifact="t", kind=ProposalKind.TABLE,
            parent_digest="d" * 64, data_scope=scope, seed=0,
            rng_stream_ref="s", metrics_snapshot={"only": 1.0})
