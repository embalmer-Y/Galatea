"""有界适应提案测试（L11 §9 C1 行/Q-L11-01/Q-L11-06/Q-L04-10）。"""
import pytest

from galatea.subject.c1profile import load_c1_profile
from galatea.subject.learning.proposals import (
    AdaptationLayer,
    AdaptationLedger,
    BoundedAdaptationViolated,
    PROPOSAL_STATUS_RECORDED,
)


@pytest.fixture()
def ledger():
    return AdaptationLedger(load_c1_profile())


def test_step_cap_enforced(ledger):
    """0.125 内接受；越界即拒（Q-L11-01 机械上界）。"""
    p = ledger.propose(AdaptationLayer.MODEL, "transition.cell.(0,0)", 0.125, ("err.1",), 8)
    assert p.delta == 0.125
    with pytest.raises(BoundedAdaptationViolated):
        ledger.propose(AdaptationLayer.MODEL, "transition.cell.(0,0)", 0.126, ("err.1",), 8)
    with pytest.raises(BoundedAdaptationViolated):
        ledger.propose(AdaptationLayer.SENSORY, "w_m.EXT", -0.2, ("err.2",), 8)


def test_proposals_recorded_only(ledger):
    """提案不生效只记录（L11 §9 C1 行）：状态恒 RECORDED_ONLY，无 apply 面。"""
    p = ledger.propose(AdaptationLayer.PERCEPTUAL, "prior.resource", 0.05, ("err.3",), 8)
    assert p.status == PROPOSAL_STATUS_RECORDED
    assert not hasattr(p, "apply")
    assert len(ledger.proposals()) == 1


def test_error_refs_required(ledger):
    """误差驱动：无 error_refs 的提案即拒（禁无源提案）。"""
    with pytest.raises(ValueError, match="error_refs"):
        ledger.propose(AdaptationLayer.MODEL, "transition.x", 0.01, (), 8)


def test_ledger_digest_persistence_ready(ledger):
    """台账 digest = checkpoint 增量承载（Q-L11-06）；空台账 digest 稳定。"""
    empty = ledger.digest()
    assert empty == AdaptationLedger(load_c1_profile()).digest()
    ledger.propose(AdaptationLayer.MODEL, "t.x", 0.01, ("e",), 8)
    assert ledger.digest() != empty


def test_layers_independent(ledger):
    """三层独立提案（Q-L09-08 等权禁跨层归一——按层记录，无跨层聚合面）。"""
    for layer in AdaptationLayer:
        ledger.propose(layer, f"target.{layer.value}", 0.01, ("e",), 8)
    assert len({p.layer for p in ledger.proposals()}) == 3
