"""思维迭代循环合同测试（Q-L07-10：四拍序/逐拍 receipt 链/矛盾检出/终止/确定性选择）。"""
from dataclasses import replace

import pytest

from galatea.subject.workspace.draft import (
    DraftDonor,
    DraftHypothesis,
    DraftStatus,
    Scratchpad,
)
from galatea.subject.workspace.thought import (
    ContradictionEvent,
    ThoughtAction,
    ThoughtBeat,
    ThoughtIterationParams,
    ThoughtLoop,
)

PARAMS = ThoughtIterationParams(
    beats=(ThoughtBeat.GENERATE, ThoughtBeat.EVALUATE, ThoughtBeat.CONTRADICT,
           ThoughtBeat.REVISE),
    think_steps_budget=8, evaluate_source="rssm_imagine_rollout",
    convergence_mode="no_new_successor")


def _submit(pad: Scratchpad, hid: str, claim: str, conf: float,
            donor: DraftDonor = DraftDonor.MODELS_ROLLOUT, **payload) -> None:
    pad.submit_from(donor.value, hypothesis_id=hid, claim=claim,
                    provenance_ref=f"src/{hid}", confidence=conf, created_cycle=1,
                    payload=payload)


def _successor(parent: DraftHypothesis) -> DraftHypothesis:
    """revise 拍后继（workspace_loop 供体 + payload.parent 引用被替代者——循环合同）。

    confidence 承继父草稿（评分面在 DraftEvaluation，禁把任意实数评分塞进 [0,1] 置信域）。
    """
    succ = replace(parent, hypothesis_id=f"{parent.hypothesis_id}-ok",
                   claim=f"{parent.claim} [feasible]", donor=DraftDonor.WORKSPACE_LOOP,
                   status=DraftStatus.OPEN)
    succ.payload["parent"] = parent.hypothesis_id
    return succ


def _frozen_params() -> ThoughtIterationParams:
    from galatea.subject.p4profile import load_p4_beta_profile
    p = load_p4_beta_profile()
    return ThoughtIterationParams(
        beats=tuple(ThoughtBeat(b) for b in p.loop_beats),
        think_steps_budget=p.think_steps_budget, evaluate_source=p.evaluate_source,
        convergence_mode=p.convergence_mode)


def test_frozen_params_from_profile() -> None:
    """循环参数逐项来自冻结 profile（INC-11：运行时消费必须经 typed loader）。"""
    params = _frozen_params()
    assert params.think_steps_budget == 8
    assert params.evaluate_source == "rssm_imagine_rollout"
    assert params.convergence_mode == "no_new_successor"
    assert params.beats == PARAMS.beats


def test_four_beats_receipt_chain_and_convergence() -> None:
    """四拍 receipt 链（prev digest 挂接）+ 零后继且零状态变化 → 收敛（第二迭代判明）。"""
    pad = Scratchpad()
    _submit(pad, "a", "plan A", 0.6, steps=3)
    loop = ThoughtLoop(
        pad, evaluator=lambda d: 0.8, conflict_fn=lambda a, b: False,
        revise_fn=lambda ev, surv, sc: (), params=PARAMS)
    result = loop.run(cycle=5, seed_ids=("a",))
    assert result.terminated_by == "converged"
    assert result.iterations == 2          # 迭代1 产生状态变化（评估）；迭代2 无变化判明收敛
    assert len(result.receipts) == 8
    assert all([r.beat for r in result.receipts[i:i + 4]] == list(PARAMS.beats)
               for i in (0, 4))
    for prev, cur in zip(result.receipts, result.receipts[1:]):
        assert cur.prev_digest == prev.digest()          # 逐拍链挂接
    eval_r = result.receipts[1]
    assert eval_r.action is ThoughtAction.SCORED
    assert eval_r.scores == (("a", 0.8),)
    assert pad.evaluations_of("a")[0].evaluator_ref == "rssm_imagine_rollout"
    assert result.selected_id == "a" and result.selected_score == 0.8
    assert pad.get("a").status is DraftStatus.EVALUATED


def test_contradiction_fires_and_loop_corrects_trap() -> None:
    """矛盾检出开火（INC-08 可失败性）+ revise 后继纠正选择（TFA 结构面）。"""
    pad = Scratchpad()
    _submit(pad, "D1", "far plan (confidence trap)", 0.6, target="far", steps=16)
    _submit(pad, "D2", "near plan", 0.55, target="near", steps=4)

    def conflict(a: DraftHypothesis, b: DraftHypothesis) -> bool:
        return a.payload["target"] != b.payload["target"]

    def revise(events: tuple[ContradictionEvent, ...], surviving: tuple[DraftHypothesis, ...],
               scores: dict[str, float]) -> tuple[DraftHypothesis, ...]:
        # 预算可行性筛选（探针 B3 语义）：仅对矛盾事件引用中的可行者生成修正后继
        refs = {h for e in events for h in e.refs}
        return [_successor(d)
                for d in surviving if d.hypothesis_id in refs and d.payload["steps"] <= 8]

    loop = ThoughtLoop(pad, evaluator=lambda d: -float(d.payload["steps"]),
                       conflict_fn=conflict, revise_fn=revise, params=PARAMS)
    result = loop.run(cycle=1)
    assert result.contradictions, "目标互斥必须开火（矛盾检出可失败性）"
    assert all(isinstance(e, ContradictionEvent) for e in result.contradictions)
    assert result.contradictions[0].refs == ("D1", "D2")
    assert pad.get("D1").status is DraftStatus.CONTRADICTED   # 互斥未被修正 → 驳倒留痕
    assert pad.get("D2").status is DraftStatus.SUPERSEDED     # 可行矛盾方被后继覆盖
    assert pad.get("D2-ok").hypothesis_id == "D2-ok"
    assert result.terminated_by == "converged"                # 后继评估后无新事件 → 收敛
    assert result.selected_id == "D2-ok"                      # 纠正到可行后继
    superseded_receipts = [r for r in result.receipts if r.action is ThoughtAction.SUPERSEDED]
    assert superseded_receipts and superseded_receipts[0].donor == DraftDonor.WORKSPACE_LOOP.value


def test_budget_termination_and_deterministic_tiebreak() -> None:
    """预算终止（生成器永不枯竭）+ 同分确定性 tie-break（hypothesis_id 字典序）。"""
    pad = Scratchpad()
    _submit(pad, "x2", "tie B", 0.5)
    _submit(pad, "x1", "tie A", 0.5)
    counter = {"n": 0}

    def endless_revise(events, surviving, scores):
        counter["n"] += 1
        succ = DraftHypothesis(hypothesis_id=f"gen-{counter['n']}", claim="gen",
                               provenance_ref="loop", confidence=0.1, created_cycle=1,
                               donor=DraftDonor.WORKSPACE_LOOP)
        succ.payload["parent"] = surviving[-1].hypothesis_id
        return (succ,)

    result = ThoughtLoop(pad, evaluator=lambda d: 1.0, conflict_fn=lambda a, b: False,
                         revise_fn=endless_revise, params=PARAMS).run(cycle=2)
    assert result.terminated_by == "budget"
    assert result.iterations == 8
    assert len(result.receipts) == 32                          # 8 迭代 × 4 拍
    # 收敛分支：平分零后继 → selected = 字典序最小同分者
    pad2 = Scratchpad()
    _submit(pad2, "x2", "tie B", 0.5)
    _submit(pad2, "x1", "tie A", 0.5)
    result2 = ThoughtLoop(pad2, evaluator=lambda d: 0.9, conflict_fn=lambda a, b: False,
                          revise_fn=lambda ev, s, sc: (), params=PARAMS).run(cycle=3)
    assert result2.terminated_by == "converged"
    assert result2.selected_id == "x1"


def test_seed_must_be_open() -> None:
    """seed_ids 引用非 open 草稿 = 拒（循环入口合同）。"""
    pad = Scratchpad()
    loop = ThoughtLoop(pad, evaluator=lambda d: 0.0, conflict_fn=lambda a, b: False,
                       revise_fn=lambda ev, s, sc: (), params=PARAMS)
    with pytest.raises(ValueError, match="not open"):
        loop.run(cycle=0, seed_ids=("ghost",))
