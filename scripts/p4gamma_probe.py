"""P4-γ 冻结前可行性探针（硬机制第九次）——正式生成器（Q-L04-16/Q-G00-16）。

核心 = galatea/evidence/control/runs_p4gamma.py（规格 ADR-G-0035 §2 全量成文）：
动作条件化 RSSM（input_dim=4）+ EFE-MPC（8 候选 4 步计划枚举）+ 生成式重放
做梦巩固（dream 600 步）+ 在线双域不退化门。零全局 RNG。

运行：uv run python scripts/p4gamma_probe.py
输出：evidence/p4_gamma_probe/probe_report.json（确定性——同机重跑逐位恒等）。
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import torch  # noqa: E402

from galatea.evidence.control.runs_p4gamma import (  # noqa: E402
    repo_root as _ROOT,
    collect_conditioned,
    dream_samples,
    heldout_mse,
    run_episode,
    seed_for,
    to_tensors,
    train_conditioned,
)
from galatea.subject.brain.world_model import RSSMWorldModel  # noqa: E402
from galatea.subject.p4profile import load_p4_alpha_profile  # noqa: E402


def finetune_from(parent: Any, mix: list[torch.Tensor]) -> Any:
    """在线学习语义：从父权重起步微调（Q-L11-09①——非重训）。"""
    params = load_p4_alpha_profile(_ROOT / "config/profiles/p4_alpha_brain.profile.yaml")
    m = RSSMWorldModel(params, parent_digest="root", init_seed=params.init_seed, input_dim=4)
    m.load_state(parent.state_dict())
    m.train_on_sequence(mix, lr=params.lr, epochs=100, target_dims=(0,))
    return m


def main() -> int:
    results: dict[str, Any] = {}

    # 训练流（混合动作脚本——三动作条件齐备）
    rows = collect_conditioned(seed_for("p4.gamma|train"), cycles=256)
    assert {a for _, a in rows} == {0, 1, 2}, "脚本必须覆盖三动作（条件化前提）"
    xs = to_tensors(rows)
    model = train_conditioned(xs[: len(xs) - 31], 300)

    # 探针 1：MPC vs 脚本（8 世界种子配对）
    mpc_scores: list[float] = []
    script_scores: list[float] = []
    for i in range(8):
        seed = seed_for(f"p4.gamma|world|{i}")
        ep_mpc = run_episode(seed, model, mode="mpc")
        ep_script = run_episode(seed, model, mode="script")
        mpc_scores.append(ep_mpc["mean_energy"])
        script_scores.append(ep_script["mean_energy"])
    advantage = statistics.mean(mpc_scores) - statistics.mean(script_scores)
    wins = sum(1 for a, b in zip(mpc_scores, script_scores) if a > b)
    results["mpc_advantage_mean"] = advantage
    results["mpc_advantage_wins"] = f"{wins}/8"
    results["mpc_scores"] = mpc_scores
    results["script_scores"] = script_scores

    # 探针 2：睡眠增益（两相流）
    rows1 = collect_conditioned(seed_for("p4.gamma|phase1"), cycles=256)
    rows2 = collect_conditioned(seed_for("p4.gamma|phase2"), cycles=256)
    xs1, xs2 = to_tensors(rows1), to_tensors(rows2)
    half1, half2 = len(xs1) // 2, len(xs2) // 2
    model_p1 = train_conditioned(xs1[: half1 + 1], 300)
    pre = heldout_mse(model_p1, xs1[half1:])

    model_a = finetune_from(model_p1, xs2[: half2 + 1])
    post_a = heldout_mse(model_a, xs1[half1:])
    dream = dream_samples(model_p1, xs1[: half1 + 1], steps=600)
    model_b = finetune_from(model_p1, xs2[: half2 + 1] + dream)
    post_b = heldout_mse(model_b, xs1[half1:])
    forget_a, forget_b = post_a - pre, post_b - pre
    results["dream"] = {"pre": pre, "forget_a": forget_a, "forget_b": forget_b,
                        "sleep_gain": forget_a - forget_b}

    # 探针 3：在线门（双域不退化——A 拒 / B 入）
    # REV-0031 R2 修正：同尺参照 = 父模型（未学习相 2）的相 2 held-out——
    # improve = 候选相 2 误差 ≤ 父模型相 2 误差（学习发生）；no_regress = 相 1 ≤ pre×1.5。
    phase2_holdout = xs2[len(xs2) // 2:]
    parent_p2 = heldout_mse(model_p1, phase2_holdout)

    def dual_gate(model_c: Any) -> tuple[bool, dict[str, float]]:
        b2 = heldout_mse(model_c, phase2_holdout)
        b1 = heldout_mse(model_c, xs1[half1:])
        improve = b2 <= parent_p2
        no_regress = b1 <= pre * 1.5
        return (improve and no_regress,
                {"phase1": b1, "phase2": b2, "pre_p1": pre, "parent_p2": parent_p2})

    gate_a, det_a = dual_gate(model_a)
    gate_b, det_b = dual_gate(model_b)
    results["gate"] = {"A": {"admit": gate_a, **det_a}, "B": {"admit": gate_b, **det_b}}

    # 确定性：MPC 规划双跑 bit-exact
    r1 = run_episode(seed_for("p4.gamma|world|0"), model, mode="mpc")
    r2 = run_episode(seed_for("p4.gamma|world|0"), model, mode="mpc")
    det = r1["plans"] == r2["plans"] and r1["mean_energy"] == r2["mean_energy"]
    results["determinism_double_run"] = det

    report = {
        "probe": "p4_gamma_freeze_feasibility",
        "authority": "Q-L04-16/Q-L08-11/Q-L10-18/Q-L11-09/Q-L06-09/Q-L13-23/Q-G00-16（AI-v2 2026-10-17）",
        "task_form": {"input_dim": 4, "actions": list(("move", "rest", "forage")),
                      "train_epochs": 300, "plan_horizon": 4,
                      "candidate_plans": 8, "set_point": 0.7, "w_epistemic": 0.1,
                      "dream_steps": 600, "finetune_epochs": 100, "world_seeds": 8},
        "mpc_advantage": {"mean": results["mpc_advantage_mean"],
                          "wins": results["mpc_advantage_wins"],
                          "mpc": results["mpc_scores"], "script": results["script_scores"]},
        "dream": results["dream"],
        "gate": results["gate"],
        "determinism_double_run": results["determinism_double_run"],
        "verdict": ("PASS" if (results["mpc_advantage_mean"] > 0
                               and results["dream"]["sleep_gain"] > 0
                               and not results["gate"]["A"]["admit"]
                               and results["gate"]["B"]["admit"]
                               and results["determinism_double_run"]) else "FAIL"),
    }
    print(json.dumps(report, ensure_ascii=False, indent=1, default=str))
    out = REPO / "evidence" / "p4_gamma_probe" / "probe_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str) + "\n",
                   encoding="utf-8")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
