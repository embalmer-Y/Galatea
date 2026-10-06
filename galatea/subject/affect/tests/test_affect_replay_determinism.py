"""bit-exact 重放（L05 §7 deterministic replay：同 (profile, 输入序列) → 轨迹恒等）。"""
import pytest

from galatea.subject.affect.ports import AffectCycleInputs
from galatea.subject.affect.pipeline import AffectPipeline
from galatea.subject.c2profile import C2AffectParams


def _scenario() -> list[AffectCycleInputs]:
    inputs = []
    for c in range(48):
        inputs.append(AffectCycleInputs(
            cycle=c,
            body_energy=max(0.0, 1.0 - 0.02 * c) if c < 30 else 0.4 + 0.02 * (c - 30),
            body_integrity=1.0 if (c // 6) % 2 == 0 else 0.9,
            sensory_residual_mean=0.1 + 0.05 * (c % 4),
            belief_uncertainty_mean=0.3 + 0.1 * (c % 3),
            action_receipt_success=(c % 5 != 0),
            affordance_strengths=(("forage", 0.4 + 0.1 * (c % 5)), ("rest", 1.0)),
        ))
    return inputs


def test_double_run_bit_exact(affect_params: C2AffectParams) -> None:
    """同输入序列双跑 → 轨迹 digest bit-exact 恒等（零 RNG 零墙钟）。"""
    p1 = AffectPipeline(affect_params)
    p2 = AffectPipeline(affect_params)
    scenario = _scenario()
    outs1 = tuple(p1.step(i) for i in scenario)
    outs2 = tuple(p2.step(i) for i in scenario)
    assert p1.trajectory_digest(outs1) == p2.trajectory_digest(outs2)
    assert all(a.state.content_digest == b.state.content_digest
               for a, b in zip(outs1, outs2))


def test_modulation_ledger_deterministic(affect_params: C2AffectParams) -> None:
    """台账 digest 双跑恒等（发放/回执确定性）。"""
    from galatea.subject.affect.modulation import ModulationReceiptRecord

    p1 = AffectPipeline(affect_params)
    p2 = AffectPipeline(affect_params)
    for c in range(20):
        inp = AffectCycleInputs(cycle=c, body_energy=0.2, body_integrity=1.0)  # 过增益门
        o1 = p1.step(inp)
        o2 = p2.step(inp)
        for f in o1.modulations:
            p1.ledger.record_receipt(ModulationReceiptRecord(
                modulation_id=f.modulation_id, accepted=True,
                applied_value=f.requested_value, bound_check="IN_BOUND", received_at=c,
            ))
        for f in o2.modulations:
            p2.ledger.record_receipt(ModulationReceiptRecord(
                modulation_id=f.modulation_id, accepted=True,
                applied_value=f.requested_value, bound_check="IN_BOUND", received_at=c,
            ))
    assert p1.ledger.digest() == p2.ledger.digest()
    assert len(p1.ledger.confirmed_fields(19)) > 0


def test_different_inputs_diverge(affect_params: C2AffectParams) -> None:
    """异输入 → 轨迹 digest 必异（检出面可见且能失败——INC-08 纪律）。"""
    p1 = AffectPipeline(affect_params)
    p2 = AffectPipeline(affect_params)
    s = _scenario()
    outs1 = tuple(p1.step(i) for i in s)
    diverged = list(s)
    diverged[10] = AffectCycleInputs(
        cycle=10, body_energy=0.9, body_integrity=1.0,
        sensory_residual_mean=0.9, belief_uncertainty_mean=0.9,
    )
    outs2 = tuple(p2.step(i) for i in diverged)
    assert p1.trajectory_digest(outs1) != p2.trajectory_digest(outs2)


def test_reappraisal_deterministic_and_recorded(affect_params: C2AffectParams) -> None:
    """重评价：同请求双跑回执恒等；revision 入史（追加式）。"""
    from galatea.subject.affect.reappraisal import ReappraisalRequest

    p1 = AffectPipeline(affect_params)
    p2 = AffectPipeline(affect_params)
    req = ReappraisalRequest(
        target_belief_ref="belief.12", reason_code="memory_cue", requested_by="l06.test",
        original_input=0.4, revised_input=0.2, requested_at=5,
    )
    r1 = p1.handle_reappraisal(req)
    r2 = p2.handle_reappraisal(req)
    assert r1.delta == pytest.approx(0.0875)     # ADR 构造式锚
    assert r1 == r2
    out = p1.step(AffectCycleInputs(cycle=6, body_energy=1.0, body_integrity=1.0))
    assert out.state.reappraisal_history and "revision.5.belief.12" in out.state.reappraisal_history[0]
