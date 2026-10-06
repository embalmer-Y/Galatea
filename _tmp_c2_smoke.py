# -*- coding: utf-8 -*-
"""C2 冒烟 n=2：五臂全链 + 机械判据 + I1（临时脚本，用后即删）。"""
import tempfile
import time
from pathlib import Path

from galatea.evidence.control.runs import seal_split_master_seed
from galatea.evidence.control.runs_c2 import (
    ARMS,
    C2Runner,
    _trial_seed,
    c2_dynamics_diffs,
    c2_gain_diffs,
    c2_r2_max,
    c2_salience_diffs,
    c2_threshold_diffs,
    load_c2_scenario,
    run_c2_evaluation,
)
from galatea.evidence.evaluator.sealed import GridCell, generate_split, load_split_policy

root = Path(".").resolve()
plan_path = root / "config/evidence/stat_plans/c2_affect_workspace.yaml"
grid = tuple(
    GridCell(cell_id=f"{r}:{i}", regime=r, seed_index=i)
    for r in ("abundance", "scarcity", "volatile")
    for i in range(32)
)
split = generate_split(grid, seal_split_master_seed(), load_split_policy(root))
with tempfile.TemporaryDirectory() as td:
    t0 = time.time()
    records, mechanical, plan_digest, split_digest, i1 = run_c2_evaluation(
        root, Path(td) / "run", Path(td) / "tmp", split.sealed.cells, plan_path,
        split.split_digest, n_limit=2,
    )
    dt = time.time() - t0
    print("records:", len(records), "| arms:", sorted(set(r.arm for r in records)))
    print("mechanical:", mechanical)
    print("i1_match:", i1, "| elapsed %.1fs for 2 runs x5 arms" % dt)
    full = [r for r in records if r.arm == "full"]
    for r in full:
        gates = [s["gate_gain_on"] + s["gate_threshold_on"] + s["gate_salience_on"]
                 for s in r.state_rows]
        act = [sum(int(w["gain_active"]) for w in r.window_rows),
               sum(int(w["threshold_active"]) for w in r.window_rows),
               sum(int(w["salience_active"]) for w in r.window_rows)]
        print(f"  run#{r.run_index}: gate-on beats={sum(gates)} active-windows(G/T/S)={act} "
              f"eff_access={r.effective_access_count} formation={r.formation_counts}")
    by_arm = {a: [r for r in records if r.arm == a] for a in ARMS}
    full_t = tuple(by_arm["full"])
    print("gain diffs:", [round(x, 5) for x in c2_gain_diffs(full_t, tuple(by_arm["no_gain"]))])
    print("threshold diffs:", [round(x, 5) for x in c2_threshold_diffs(full_t, tuple(by_arm["no_threshold"]))])
    print("salience diffs:", [round(x, 5) for x in c2_salience_diffs(full_t, tuple(by_arm["no_salience"]))])
    print("r2max:", [round(x, 4) for x in c2_r2_max(full_t)])
    print("dynamics diffs:", [round(x, 5) for x in c2_dynamics_diffs(full_t, tuple(by_arm["flat_full"]))])
