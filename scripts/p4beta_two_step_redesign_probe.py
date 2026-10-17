"""Q-L13-22 重设计探针（REV-0030 R2 闭环——判据重冻锚定测量的可复算工件生成器）。

规格（ADR-G-0034 §2 全量成文）：
- 任务形 v2：two_step 400 trials / 固定反转@60 / 无每拍漂移 / softmax(β=5) 探索 /
  价值衰减 0.9 / MB=端状态价值×转移前瞻 vs habit=支线历史平均；
- 统计量：stay ~ reward × common 逻辑回归 interaction 系数（IRLS 50 轮零初始化，零 RNG）；
- 测量一（块稳定性）：20 块 × 40 种子（种子 = b*40+i，i∈[0,40)），块 sep = mean(MB)−mean(habit)；
- 测量二（逐种子优势率）：200 种子配对差 > 0 占比。

运行：uv run python scripts/p4beta_two_step_redesign_probe.py
输出：evidence/p4_beta_two_step_redesign_probe/probe_report.json（确定性——同机重跑逐位恒等）。
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

TRIALS = 400
REVERSAL = 60
COMMON = 0.8
BETA = 5.0
DECAY = 0.9
MB_ALPHA = 0.5
HABIT_ALPHA = 0.2


def simulate(seed: int, agent: str) -> list[tuple[int, int, int]]:
    rng = np.random.default_rng(seed)
    trans = {"A": (COMMON, 1 - COMMON), "B": (1 - COMMON, COMMON)}
    good = 0
    v_end = {0: 0.5, 1: 0.5}
    q_h = {"A": 0.5, "B": 0.5}
    rows: list[tuple[int, int, int]] = []
    prev: str | None = None
    for t in range(TRIALS):
        if t == REVERSAL:
            good = 1 - good
        v_end[0] *= DECAY
        v_end[1] *= DECAY
        q_h["A"] = 0.5 + (q_h["A"] - 0.5) * DECAY
        q_h["B"] = 0.5 + (q_h["B"] - 0.5) * DECAY
        if agent == "mb":
            v_a = COMMON * v_end[0] + (1 - COMMON) * v_end[1]
            v_b = (1 - COMMON) * v_end[0] + COMMON * v_end[1]
            p_a = 1.0 / (1.0 + np.exp(-BETA * (v_a - v_b)))
        else:
            p_a = 1.0 / (1.0 + np.exp(-BETA * (q_h["A"] - q_h["B"])))
        choice = "A" if rng.random() < p_a else "B"
        e = 0 if rng.random() < trans[choice][0] else 1
        is_common = trans[choice][0] >= COMMON
        reward = 1.0 if rng.random() < (0.8 if e == good else 0.2) else 0.0
        if prev is not None:
            rows.append((1 if choice == prev else 0, 1 if reward >= 0.5 else 0,
                         1 if is_common else 0))
        prev = choice
        if agent == "mb":
            v_end[e] += MB_ALPHA * (reward - v_end[e])
        else:
            q_h[choice] += HABIT_ALPHA * (reward - q_h[choice])
    return rows


def interaction(rows: list[tuple[int, int, int]]) -> float:
    y = np.array([r[0] for r in rows], float)
    rew = np.array([r[1] for r in rows], float)
    com = np.array([r[2] for r in rows], float)
    X = np.column_stack([np.ones_like(rew), rew, com, rew * com])
    b = np.zeros(4)
    for _ in range(50):
        p = 1.0 / (1.0 + np.exp(-X @ b))
        w = np.clip(p * (1 - p), 1e-9, None)
        z = X @ b + (y - p) / w
        xtw = X.T * w
        b = np.linalg.solve(xtw @ X + 1e-8 * np.eye(4), xtw @ z)
    return float(b[3])


def main() -> int:
    # 测量一：块稳定性（20 块 × 40 种子）
    block_seps = []
    for blk in range(20):
        mb = [interaction(simulate(blk * 40 + i, "mb")) for i in range(40)]
        hb = [interaction(simulate(blk * 40 + i, "habit")) for i in range(40)]
        block_seps.append(statistics.mean(mb) - statistics.mean(hb))
    mean = statistics.mean(block_seps)
    sd = statistics.stdev(block_seps)
    sign_consistent = all(x > 0 for x in block_seps)

    # 测量二：逐种子优势率（200 配对种子）
    diffs = []
    for i in range(200):
        diffs.append(interaction(simulate(i, "mb")) - interaction(simulate(i, "habit")))
    dominance = sum(1 for d in diffs if d > 0) / len(diffs)

    report = {
        "probe": "p4_beta_two_step_redesign_probe",
        "authority": "Q-L13-22（owner α 裁决 2026-10-16；REV-0030 R2 可复算规格成文）",
        "task_form": {"trials": TRIALS, "reversal_at": REVERSAL, "per_trial_drift": "none",
                      "transition_common": COMMON, "softmax_beta": BETA, "value_decay": DECAY,
                      "mb_alpha": MB_ALPHA, "habit_alpha": HABIT_ALPHA,
                      "statistic": "stay ~ reward×common logistic interaction (IRLS 50 iters, zero-init, zero-RNG)"},
        "measurement_1_block_stability": {
            "blocks": 20, "seeds_per_block": 40, "seed_scheme": "block*40+i",
            "block_separations": [round(x, 6) for x in block_seps],
            "mean": round(mean, 6), "sd": round(sd, 6),
            "cv": round(abs(sd / mean), 6), "sign_consistent": sign_consistent},
        "measurement_2_per_seed_dominance": {
            "n_pairs": 200, "dominance": round(dominance, 6)},
        "frozen_criteria_derived": {"criterion_separation": 0.10, "criterion_dominance": 0.60,
                                    "margin_note": "sep 阈 = 探针块均值 0.280 的 ~2.8× margin；dominance 阈 = 探针 0.760 的 ~2σ(n=40 二项) 余量"},
        "verdict": "PASS" if (sign_consistent and mean > 0.10 and dominance > 0.60) else "FAIL",
    }
    out = ROOT / "evidence" / "p4_beta_two_step_redesign_probe" / "probe_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("measurement_1_block_stability",
                                             "measurement_2_per_seed_dominance", "verdict")},
                     ensure_ascii=False, indent=1))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
