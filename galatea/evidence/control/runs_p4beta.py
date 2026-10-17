"""P4-β sealed 评价 runner（stat plan p4_beta_mind v1.0 冻结承载；GCTB P4-β 子集）。

三 claim（Q-L13-21 立法；判据数值 = p4_beta_mind.profile 冻结探针值）：
1. two_step 双分离（Daw 谱系 MW0 小型化）：MB 原型 stay 调节 > habit 原型
   （sep > 0.01 ∧ 配对优势 > 0.5）——**门判据核心**（Q-L13-21①）；
2. opt_out 元认知经济：校准置信弃权增益 > 0（Q-L13-21②）；
3. think_first_advantage：草稿板 + 思维迭代在超预算陷阱场景纠正置信直选
   （TFA == true ∧ 矛盾检出开火——机械门，INC-08 可失败性）（Q-L13-21④/Q-L07-10）。

种子派生（stat plan seed_derivation，Q-L13-12④）：master = b"p4-beta-mind"（hex 内嵌
stat plan）；trial_seed = sha256("{task}|{index}" + master)。两步/弃权任务为纯确定性
numpy 模拟（device 无关）；think_first 世界布局 = 真实 MW0（trial_seed 派生），
想象评估器 = P4-α RSSM（探针 B3 协议：p4.alpha cell-0 流 300 epochs 训练一次、
20 世界种子共用同一评估器仪器——配对 like-for-like）。

剔除去（stat plan unknown_handling）：think_first 布局资源 < 2 的 seed 剔除留痕
（世界真实布局禁伪造）；two_step 样本不足的 stay 桶如实 0.0（探针同式）。
"""
from __future__ import annotations

import hashlib
import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from galatea.subject.p4profile import P4BetaMindParams, load_p4_beta_profile

_ROOT = Path(__file__).resolve().parents[3]
_MASTER_SEED = bytes.fromhex("70342d626574612d6d696e64")     # = b"p4-beta-mind"（stat plan 内嵌）
assert _MASTER_SEED == b"p4-beta-mind"

_N_TWO_STEP = 40                              # stat plan n_per_arm（配对种子）
_N_OPTOUT = 20
_N_THINK_FIRST = 20
_TRAP_FAR_MIN_DIST = 8                        # 探针 B3 冻结场景形（远支线须超预算邻域）
_TFA_EPOCHS = 300                             # 探针 B3 训练预算（ Imagine 评估器仪器）
_BUDGET_FALLBACK = 8                          # think_first 预算回退（profile 冻结值兜底）


def trial_seed(task: str, index: int) -> bytes:
    """stat plan trial_seed 派生（Q-L13-12④：sha256("{task}|{index}" + master)）。"""
    return hashlib.sha256(f"{task}|{index}".encode("utf-8") + _MASTER_SEED).digest()


# ---------------------------------------------------------------- claim 1: two_step
def two_step_stay_signal(agent_kind: str, seed: bytes,
                         params: P4BetaMindParams) -> float:
    """two_step 单种子 stay 调节（rewarded × common-transition stay 率差；探针 B1 同式）。

    MB 原型 = endstate 价值 + 转移概率前瞻（mb_alpha 更新）；habit 原型 = 支线历史
    平均（habit_alpha 更新）。转移反转 @reversal_at + 每拍 drift 概率反转——MB 应
    立即跟随、habit 滞后 → 调节差 = 双分离信号。
    """
    import numpy as np

    rng = np.random.default_rng(int.from_bytes(seed[:8], "big"))
    common = params.two_step_transition_common
    trans = {"A": (common, 1.0 - common), "B": (1.0 - common, common)}
    good = 0
    v_end = {0: 0.5, 1: 0.5}
    q_h = {"A": 0.5, "B": 0.5}
    stay_common: list[int] = []
    stay_rare: list[int] = []
    prev: str | None = None
    for t in range(params.two_step_trials):
        if t == params.two_step_reversal or rng.random() < params.two_step_drift_prob:
            good = 1 - good
        if agent_kind == "mb":
            v_a = common * v_end[0] + (1.0 - common) * v_end[1]
            v_b = (1.0 - common) * v_end[0] + common * v_end[1]
            choice = "A" if v_a > v_b else ("B" if v_b > v_a else ("A" if rng.random() < 0.5 else "B"))
        else:
            choice = ("A" if q_h["A"] > q_h["B"] else
                      ("B" if q_h["B"] > q_h["A"] else ("A" if rng.random() < 0.5 else "B")))
        end_state = 0 if rng.random() < trans[choice][0] else 1
        is_common = trans[choice][0] >= 0.8
        reward = 1.0 if rng.random() < (0.8 if end_state == good else 0.2) else 0.0
        if prev is not None:
            stay = 1 if choice == prev else 0
            if reward and is_common:
                stay_common.append(stay)
            elif reward and not is_common:
                stay_rare.append(stay)
        prev = choice
        if agent_kind == "mb":
            v_end[end_state] += params.two_step_mb_alpha * (reward - v_end[end_state])
        else:
            q_h[choice] += params.two_step_habit_alpha * (reward - q_h[choice])
    return ((statistics.mean(stay_common) if stay_common else 0.0)
            - (statistics.mean(stay_rare) if stay_rare else 0.0))


def run_two_step(params: P4BetaMindParams, n: int | None = None
                 ) -> dict[str, Any]:
    """claim1 数据面：配对种子 MB/habit 调节序列 + 分离统计量。"""
    n = _N_TWO_STEP if n is None else n
    mb = [two_step_stay_signal("mb", trial_seed("two_step", i), params) for i in range(n)]
    habit = [two_step_stay_signal("habit", trial_seed("two_step", i), params) for i in range(n)]
    sep = statistics.mean(mb) - statistics.mean(habit)
    dominance = sum(1 for a, b in zip(mb, habit) if a > b) / len(mb)
    return {"mb": mb, "habit": habit, "separation": sep, "dominance": dominance, "n": n}


# ---------------------------------------------------------------- claim 2: opt_out
def optout_economy(seed: bytes, params: P4BetaMindParams) -> float:
    """弃权元认知经济（探针 B2 同式）：校准置信（Beta 后验均值）< 保底 → 弃权拿保底。"""
    import numpy as np

    rng = np.random.default_rng(int.from_bytes(seed[:8], "big"))
    true_p = rng.uniform(params.optout_true_p[0], params.optout_true_p[1],
                         size=params.optout_arms)

    def episode(optout: bool) -> float:
        alpha = np.ones(params.optout_arms)
        beta = np.ones(params.optout_arms)
        r2 = np.random.default_rng(int.from_bytes(seed[:8], "big") * 7919 + 3)
        total = 0.0
        for _ in range(params.optout_trials):
            mean = alpha / (alpha + beta)
            best = int(np.argmax(mean))
            if optout and mean[best] < params.optout_safe_harbor:
                total += params.optout_safe_harbor
                continue
            arm = best if r2.random() > 0.3 else 1 - best
            reward = 1.0 if r2.random() < true_p[arm] else 0.0
            total += reward
            alpha[arm] += reward
            beta[arm] += 1 - reward
        return total

    return episode(True) - episode(False)


def run_optout(params: P4BetaMindParams, n: int | None = None) -> dict[str, Any]:
    n = _N_OPTOUT if n is None else n
    gains = [optout_economy(trial_seed("optout", i), params) for i in range(n)]
    return {"gains": gains, "mean_gain": statistics.mean(gains), "n": n}


# ---------------------------------------------------------------- claim 3: think_first
@dataclass(frozen=True, slots=True)
class ThinkFirstTrial:
    """单世界种子 TFA 结果（陷阱场景四元组 + 剔除留痕）。"""

    index: int
    included: bool
    exclusion_reason: str | None
    without_decision: str | None          # 关慢环（置信直选）
    with_decision: str | None             # 开慢环（草稿板 + 思维迭代）
    true_best: str | None
    tfa_corrected: bool
    contradiction_fired: bool
    near_dist: int | None
    far_dist: int | None
    loop_iterations: int | None
    terminated_by: str | None


def _mw0_resources(world: Any, size: int) -> list[tuple[int, int]]:
    return [(x, y) for y in range(size) for x in range(size)
            if world._grid[y][x].kind == "resource" and world._grid[y][x].resource_level >= 1]


def _manhattan_from_center(cell: tuple[int, int], size: int) -> int:
    sx, sy = size // 2, size // 2
    return abs(cell[0] - sx) + abs(cell[1] - sy)


def think_first_trial(index: int, imagine_cost_fn: Any,
                      params: P4BetaMindParams) -> ThinkFirstTrial:
    """陷阱场景单 trial（探针 B3 冻结形）：近/远双草稿，置信直选落入超预算陷阱。"""
    from galatea.env.profile import load_profile
    from galatea.env.world.mw0 import MW0World
    from galatea.kernel.rng import RngDirectory, chacha8_block
    from galatea.subject.workspace.draft import DraftDonor
    from galatea.subject.workspace.thought import (
        ThoughtBeat,
        ThoughtIterationParams,
        ThoughtLoop,
    )

    seed = trial_seed("think_first", index)
    profile = load_profile(_ROOT / "config" / "profiles" / "m0_mw0.profile.yaml")
    world = MW0World(profile.params, RngDirectory(seed, chacha8_block), branch_id="B")
    size = profile.params.grid_size
    resources = _mw0_resources(world, size)
    if len(resources) < 2:
        return ThinkFirstTrial(index=index, included=False,
                               exclusion_reason="layout_resources_lt_2", without_decision=None,
                               with_decision=None, true_best=None, tfa_corrected=False,
                               contradiction_fired=False, near_dist=None, far_dist=None,
                               loop_iterations=None, terminated_by=None)
    resources.sort(key=lambda c: _manhattan_from_center(c, size))
    near = resources[0]
    fars = [c for c in resources if _manhattan_from_center(c, size) > _TRAP_FAR_MIN_DIST]
    far = max(fars or [resources[-1]], key=lambda c: _manhattan_from_center(c, size))
    near_dist = _manhattan_from_center(near, size)
    far_dist = _manhattan_from_center(far, size)

    pad: Any = _draft_pad()
    pad.submit_from(DraftDonor.CONTROLLER_PROPOSAL.value, hypothesis_id="D1",
                    claim="far patch plan（confidence trap）", provenance_ref=f"world/{index}/far",
                    confidence=0.6, created_cycle=0,
                    payload={"target": f"{far[0]},{far[1]}", "steps": far_dist})
    pad.submit_from(DraftDonor.CONTROLLER_PROPOSAL.value, hypothesis_id="D2",
                    claim="near patch plan", provenance_ref=f"world/{index}/near",
                    confidence=0.55, created_cycle=0,
                    payload={"target": f"{near[0]},{near[1]}", "steps": near_dist})
    # 关慢环臂：置信直选（去功能基线——反应式，无草稿板）
    drafts: list[dict[str, Any]] = [{"id": "D1", "conf": 0.6, "steps": far_dist},
                                    {"id": "D2", "conf": 0.55, "steps": near_dist}]
    without = max(drafts, key=lambda d: d["conf"])["id"]

    budget = params.think_first_budget_steps or _BUDGET_FALLBACK
    loop_params = ThoughtIterationParams(
        beats=(ThoughtBeat.GENERATE, ThoughtBeat.EVALUATE, ThoughtBeat.CONTRADICT,
               ThoughtBeat.REVISE),
        think_steps_budget=budget,
        evaluate_source="rssm_imagine_rollout", convergence_mode="no_new_successor")

    def conflict_fn(a: Any, b: Any) -> bool:
        return a.payload["target"] != b.payload["target"]

    def evaluator(draft: Any) -> float:
        return -imagine_cost_fn(min(int(draft.payload["steps"]), budget))

    def revise_fn(events: Any, surviving: Any, scores: Any) -> tuple[Any, ...]:
        refs = {h for e in events for h in e.refs}
        out: list[Any] = []
        for d in surviving:
            if d.hypothesis_id in refs and int(d.payload["steps"]) <= budget:
                succ = _successor_of(d)
                out.append(succ)
        return tuple(out)

    loop = ThoughtLoop(pad, evaluator=evaluator, conflict_fn=conflict_fn,
                       revise_fn=revise_fn, params=loop_params)
    result = loop.run(cycle=0)
    with_decision = result.selected_id
    if with_decision is not None and with_decision.endswith("-ok"):
        with_decision = with_decision[:-3]
    true_best = ("D2" if near_dist <= budget
                 else ("D1" if far_dist <= budget else "D1"))
    tfa = bool(without != true_best and with_decision == true_best)
    return ThinkFirstTrial(
        index=index, included=True, exclusion_reason=None, without_decision=without,
        with_decision=with_decision, true_best=true_best, tfa_corrected=tfa,
        contradiction_fired=len(result.contradictions) > 0, near_dist=near_dist,
        far_dist=far_dist, loop_iterations=result.iterations,
        terminated_by=result.terminated_by)


def _draft_pad() -> Any:
    from galatea.subject.workspace.draft import Scratchpad
    return Scratchpad()


def _successor_of(parent: Any) -> Any:
    from dataclasses import replace

    from galatea.subject.workspace.draft import DraftDonor, DraftStatus
    succ = replace(parent, hypothesis_id=f"{parent.hypothesis_id}-ok",
                   claim=f"{parent.claim} [feasible]", donor=DraftDonor.WORKSPACE_LOOP,
                   status=DraftStatus.OPEN)
    succ.payload["parent"] = parent.hypothesis_id
    return succ


def build_imagine_evaluator(epochs: int = _TFA_EPOCHS) -> tuple[Any, str]:
    """想象评估器仪器（探针 B3 协议：p4.alpha cell-0 流 → RSSM 训练一次共用）。

    返回 (imagine_cost_fn(steps) -> float, 流 digest)——闭环负预测成本 = 想象走
    n 步的累计预测能耗（负号在 evaluator 侧转评分）。
    """
    import torch

    from galatea.evidence.control.runs_p4 import (cell_master_seed, collect_stream_vectors, task_rates, zscore_train_stats)
    from galatea.subject.brain.world_model import RSSMWorldModel
    from galatea.subject.p4profile import load_p4_alpha_profile

    _rows, intero, _ud, stream_digest = collect_stream_vectors(cell_master_seed(0))
    rates = task_rates(intero)
    n_train = len(rates) - 64
    norm, mu, sd = zscore_train_stats(rates, n_train)
    alpha_params = load_p4_alpha_profile(_ROOT / "config" / "profiles" / "p4_alpha_brain.profile.yaml")
    model = RSSMWorldModel(alpha_params, parent_digest="root",
                           init_seed=alpha_params.init_seed, input_dim=1)
    xs = [torch.tensor([r], dtype=torch.float32) for r in norm][:n_train + 1]
    model.train_on_sequence(xs, lr=alpha_params.lr, epochs=epochs,
                            target_dims=(0,), val_context=(mu, sd))

    dev = next(model.module.parameters()).device   # NeuralModule.module 公开面（禁 _module 私有触达）

    def imagine_cost(steps: int) -> float:
        h = torch.zeros(model.det_dim, device=dev)
        z = torch.zeros(model.latent_dim, device=dev)
        x = torch.zeros(1, device=dev)
        x_prev = None
        cost = 0.0
        with torch.no_grad():
            for _ in range(steps):
                h, _mq, _lq, _mp, _lp, xp = model.step(x, h, z, x_prev)
                z = _mq
                x_prev = x
                x = xp
                cost += float(xp[0].cpu())
        return cost

    return imagine_cost, stream_digest


def run_think_first(params: P4BetaMindParams, n: int | None = None,
                    imagine_cost_fn: Any = None,
                    stream_digest: str | None = None) -> dict[str, Any]:
    """claim3 数据面：n 个真实 MW0 世界种子 × 陷阱场景；资源不足 seed 剔除留痕。"""
    n = _N_THINK_FIRST if n is None else n
    if imagine_cost_fn is None:
        imagine_cost_fn, stream_digest = build_imagine_evaluator()
    trials: list[dict[str, Any]] = []
    for i in range(n):
        t = think_first_trial(i, imagine_cost_fn, params)
        trials.append({
            "index": t.index, "included": t.included,
            "exclusion_reason": t.exclusion_reason,
            "without": t.without_decision, "with": t.with_decision,
            "true_best": t.true_best, "tfa_corrected": t.tfa_corrected,
            "contradiction_fired": t.contradiction_fired,
            "near_dist": t.near_dist, "far_dist": t.far_dist,
            "loop_iterations": t.loop_iterations, "terminated_by": t.terminated_by,
        })
    included: list[dict[str, Any]] = [t for t in trials if t["included"]]
    return {
        "trials": trials,
        "n_included": len(included),
        "n_excluded": n - len(included),
        "all_tfa": all(t["tfa_corrected"] for t in included) if included else False,
        "all_contradiction": all(t["contradiction_fired"] for t in included) if included else False,
        "stream_digest": stream_digest,
    }


# ---------------------------------------------------------------- 汇总
def run_p4beta_tasks(params: P4BetaMindParams, n_limit: int | None = None) -> dict[str, Any]:
    """三任务一次执行（评价单元 + I1 双跑共用——确定性双跑 byte-identical 判据）。"""
    two = run_two_step(params, None if n_limit is None else min(n_limit, _N_TWO_STEP))
    opt = run_optout(params, None if n_limit is None else min(n_limit, _N_OPTOUT))
    imagine_cost_fn, stream_digest = build_imagine_evaluator()
    tf = run_think_first(params, None if n_limit is None else min(n_limit, _N_THINK_FIRST),
                         imagine_cost_fn=imagine_cost_fn, stream_digest=stream_digest)
    return {"two_step": two, "optout": opt, "think_first": tf}


def run_smoke(n_two: int = 4, n_opt: int = 3, n_tfa: int = 3) -> dict[str, Any]:
    """缩规模冒烟（INC-08：runner 路径必须有端到端覆盖——REV-0014 R1 教训）。"""
    params = load_p4_beta_profile()
    two = run_two_step(params, n_two)
    opt = run_optout(params, n_opt)
    imagine_cost_fn, stream_digest = build_imagine_evaluator()
    tf = run_think_first(params, n_tfa, imagine_cost_fn=imagine_cost_fn,
                         stream_digest=stream_digest)
    return {"two_step": two, "optout": opt, "think_first": tf, "stream_digest": stream_digest}


def _jsonify(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=1)


def _frozen_refs() -> tuple[str, str]:
    """冻结物版本标签动态读取（REV-0029 R2：禁硬编码——INC-15 家族教训）。"""
    import yaml

    profile_doc = yaml.safe_load(
        (_ROOT / "config" / "profiles" / "p4_beta_mind.profile.yaml").read_text(encoding="utf-8"))
    plan_doc = yaml.safe_load(
        (_ROOT / "config" / "evidence" / "stat_plans" / "p4_beta_mind.yaml").read_text(encoding="utf-8"))
    return (f"p4_beta_mind@{profile_doc['profile']['version']}",
            f"p4_beta_mind@{plan_doc['stat_plan']['version']}")


def run_p4beta_first_evaluation(root: Path, out_dir: Path,
                                n_limit: int | None = None) -> dict[str, Any]:
    """正式评价入口（entry p4beta）：三任务双跑 I1 → 判定器 → 工件落盘。"""
    from galatea.evidence.evaluator.evaluate_p4beta import (
        evaluate_p4beta_composite,
        evaluate_p4beta_optout,
        evaluate_p4beta_think_first,
        evaluate_p4beta_two_step,
    )

    params = load_p4_beta_profile()
    profile_ref, plan_ref = _frozen_refs()
    out_dir.mkdir(parents=True, exist_ok=True)

    tasks = run_p4beta_tasks(params, n_limit)
    payload = _jsonify(tasks)
    tasks_rerun = run_p4beta_tasks(params, n_limit)
    i1_match = _jsonify(tasks_rerun) == payload
    (out_dir / "p4beta_tasks.json").write_text(payload + "\n", encoding="utf-8")

    two_result = evaluate_p4beta_two_step(
        "R-p4beta-two-step-001", plan_ref,
        tuple(tasks["two_step"]["mb"]), tuple(tasks["two_step"]["habit"]),
        separation_threshold=params.criterion_separation,
        dominance_threshold=params.criterion_dominance,
        data_ref=f"n={tasks['two_step']['n']}")
    opt_result = evaluate_p4beta_optout(
        "R-p4beta-optout-001", plan_ref,
        tuple(tasks["optout"]["gains"]), data_ref=f"n={tasks['optout']['n']}")
    tf_result = evaluate_p4beta_think_first(
        "R-p4beta-think-first-001", plan_ref,
        tuple(tasks["think_first"]["trials"]),
        data_ref=(f"n_included={tasks['think_first']['n_included']} "
                  f"n_excluded={tasks['think_first']['n_excluded']}"))
    composite = evaluate_p4beta_composite(
        "R-p4beta-mind-001", plan_ref,
        two_result, opt_result, tf_result, leakage_free=True, i1_match=i1_match)

    result_doc = {
        "results": [_result_dict(r) for r in (two_result, opt_result, tf_result, composite)],
        "i1_match": i1_match,
        "profile_ref": profile_ref,
        "stream_digest": tasks["think_first"]["stream_digest"],
        "exclusions": [t for t in tasks["think_first"]["trials"] if not t["included"]],
    }
    (out_dir / "p4beta_first_evaluation.json").write_text(
        _jsonify(result_doc) + "\n", encoding="utf-8")
    result_doc["results"] = {"two_step": two_result, "optout": opt_result,
                             "think_first": tf_result, "composite": composite}
    return result_doc


def _result_dict(r: Any) -> dict[str, Any]:
    return {
        "result_id": r.result_id, "hypothesis_refs": list(r.hypothesis_refs),
        "estimand": r.estimand, "effect_size": r.effect_size,
        "p_or_bayes": r.p_or_bayes, "verdict": r.verdict.value,
        "refutations": list(r.refutations), "data_refs": list(r.data_refs),
        "recompute_ok": r.recompute_ok,
    }
