"""慢环调度合同测试（Q-L09-11：触发判据/频度/产物供体/审计记录）。"""
import json

import pytest

from galatea.subject.p4profile import load_p4_beta_profile
from galatea.subject.workspace.draft import DraftDonor, DraftHypothesis, Scratchpad
from galatea.subject.workspace.slow_clock import (
    SlowClock,
    SlowClockParams,
    SlowClockTrigger,
    require_controller_donors,
)
from galatea.subject.workspace.thought import ThoughtBeat, ThoughtIterationParams, ThoughtLoop

PARAMS = SlowClockParams(
    triggers=(SlowClockTrigger.IDLE_CYCLE, SlowClockTrigger.LOW_AROUSAL),
    arousal_low=0.1, urgency_idle=0.0, check_interval_cycles=1)


def _frozen_params() -> SlowClockParams:
    p = load_p4_beta_profile()
    return SlowClockParams(
        triggers=tuple(SlowClockTrigger(t) for t in p.triggers),
        arousal_low=p.arousal_low, urgency_idle=p.urgency_idle,
        check_interval_cycles=p.check_interval_cycles)


def test_frozen_params_from_profile() -> None:
    """慢环参数逐项来自冻结 profile v1.1（Q-L09-11③ 数值随实现冻结）。"""
    params = _frozen_params()
    assert params.arousal_low == 0.1
    assert params.urgency_idle == 0.0
    assert params.check_interval_cycles == 1
    assert params.triggers == PARAMS.triggers


def test_trigger_conditions() -> None:
    """空闲（urgency=0 且无 pending）或低唤起触发；紧迫/高唤起/有命令不触发。"""
    clock = SlowClock(PARAMS)
    d = clock.should_trigger(cycle=0, arousal=0.05, urgency_max=0.0, pending_command=False)
    assert d is not None
    assert set(d.triggers) == {SlowClockTrigger.IDLE_CYCLE, SlowClockTrigger.LOW_AROUSAL}
    d = clock.should_trigger(cycle=1, arousal=0.05, urgency_max=0.0, pending_command=True)
    assert d is not None and d.triggers == (SlowClockTrigger.LOW_AROUSAL,)  # pending 只挡空闲
    assert clock.should_trigger(2, arousal=0.5, urgency_max=0.3, pending_command=False) is None
    assert clock.should_trigger(3, arousal=0.5, urgency_max=0.0, pending_command=False) is not None
    assert clock.should_trigger(4, arousal=0.05, urgency_max=0.5, pending_command=False) is not None
    # 逐拍检测（check_interval=1）：任意拍可触发；≥2 间隔参数下跳拍
    tight = SlowClockParams(triggers=PARAMS.triggers, arousal_low=0.1,
                            urgency_idle=0.0, check_interval_cycles=2)
    assert SlowClock(tight).should_trigger(5, 0.0, 0.0, False) is None   # 5 % 2 ≠ 0


def test_episode_accounting_and_audit() -> None:
    """episode 落账：审计记录 jsonl 可序列化 + digest 稳定 + 供体白名单出口校验。"""
    clock = SlowClock(PARAMS)
    decision = clock.should_trigger(7, arousal=0.05, urgency_max=0.0, pending_command=False)
    assert decision is not None
    pad = Scratchpad()
    pad.submit_from("controller_proposal", hypothesis_id="s1", claim="rest is optimal",
                    provenance_ref="ctrl/prop-9", confidence=0.4, created_cycle=7)
    loop_params = ThoughtIterationParams(
        beats=(ThoughtBeat.GENERATE, ThoughtBeat.EVALUATE, ThoughtBeat.CONTRADICT,
               ThoughtBeat.REVISE), think_steps_budget=8,
        evaluate_source="rssm_imagine_rollout", convergence_mode="no_new_successor")
    loop = ThoughtLoop(pad, evaluator=lambda d: 0.9, conflict_fn=lambda a, b: False,
                       revise_fn=lambda ev, s, sc: (), params=loop_params)
    result = loop.run(cycle=7, seed_ids=("s1",))
    episode = clock.run_episode(decision, result, drafts_created=1, proposal_ref="ctrl/prop-9")
    digest = episode.digest()
    assert digest == episode.digest()
    (record,) = clock.records
    assert record.cycle == 7 and record.drafts_created == 1 and record.terminated_by == "converged"
    parsed = json.loads(record.to_jsonl())
    assert parsed["kind"] == "slow_clock_episode" and parsed["episode_digest"] == digest
    # 供体出口校验：慢环种子必须来自 controller_proposal（产物纪律②）
    bad = DraftHypothesis(hypothesis_id="s2", claim="x", provenance_ref="p", confidence=0.1,
                          created_cycle=0, donor=DraftDonor.MODELS_ROLLOUT)
    with pytest.raises(ValueError, match="controller_proposal"):
        require_controller_donors((bad,))
    assert require_controller_donors(()) == ()
