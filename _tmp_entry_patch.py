# -*- coding: utf-8 -*-
"""entry.py 追加 c2 子命令（临时脚本，用后即删）。"""
from pathlib import Path

p = Path("galatea/evidence/control/entry.py")
t = p.read_text(encoding="utf-8")

# 1) imports（runs_c2 + 新判定器）
old_imp = """from galatea.evidence.control.runs_c1 import (
    c1_accuracy_diffs,
    c1_criterion_diffs,"""
new_imp = """from galatea.evidence.control.runs_c1 import (
    c1_accuracy_diffs,
    c1_criterion_diffs,"""
assert t.count(old_imp) == 1

# 找到 runs_c1 import 块结束的右括号行后追加 c2 import
anchor_import_end = "    load_c1_scenario,\n)\n"
assert t.count(anchor_import_end) == 1
t = t.replace(anchor_import_end, anchor_import_end + """from galatea.evidence.control.runs_c2 import (
    _trial_seed as _c2_trial_seed,
    c2_dynamics_diffs,
    c2_gain_diffs,
    c2_r2_max,
    c2_salience_diffs,
    c2_threshold_diffs,
    c2_valence_anchor_violations,
    load_c2_scenario,
    run_c2_evaluation,
)
from galatea.evidence.evaluator.hypotheses import (
    evaluate_c2_anti_reward_collapse,
    evaluate_c2_composite,
    evaluate_c2_dynamics_input_driven,
    evaluate_c2_modulation_causality,
)
""")

# 2) C2_PLAN 常量（_C1_PLAN 旁）
anchor_plan = '_C1_PLAN = Path("config") / "evidence" / "stat_plans" / "c1_perception_models.yaml"'
assert t.count(anchor_plan) == 1
t = t.replace(anchor_plan, anchor_plan + '\n_C2_PLAN = Path("config/evidence/stat_plans/c2_affect_workspace.yaml")')

# 3) run_c2_first_evaluation 函数（追加在 class C1FirstEvaluation 之前）
anchor_fn = "class C1FirstEvaluation:"
fn_src = '''def run_c2_first_evaluation(
    root: Path, out_dir: Path, n_limit: int | None = None,
) -> "C2FirstEvaluation":
    """C2 首评（stat plan c2_affect_workspace v1.0；顺延终止条款）。

    三 claim（调制因果两判据 joint / anti-reward-collapse 上界 / 感受态输入驱动）
    + 八项机械判据（含 threshold 值域间隙——运行前修订 3）+ leakage + I1
    → 复合 EvidenceResult（Q-L13-11① 体例；Holm 族 = 3 claim 级主判定 p）。
    """
    plan_path = root / _C2_PLAN
    plan = load_stat_plan(plan_path)
    policy = load_split_policy(root)
    grid = tuple(
        GridCell(cell_id=f"{r}:{i}", regime=r, seed_index=i)
        for r in ("abundance", "scarcity", "volatile")
        for i in range(32)
    )
    split = generate_split(grid, seal_split_master_seed(), policy)
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True)
    run_dir = out_dir / "run"
    records, mechanical, plan_digest, split_digest, i1_match = run_c2_evaluation(
        root, run_dir, out_dir / "runner-tmp", split.sealed.cells, plan_path,
        split.split_digest, n_limit=n_limit,
    )
    full = tuple(r for r in records if r.arm == "full")
    by_arm = {arm: tuple(r for r in records if r.arm == arm)
              for arm in ("no_gain", "no_threshold", "no_salience", "flat_full")}
    gain = c2_gain_diffs(full, by_arm["no_gain"])
    salience = c2_salience_diffs(full, by_arm["no_salience"])
    r2max = c2_r2_max(full)
    dynamics = c2_dynamics_diffs(full, by_arm["flat_full"])
    anchor_violations = c2_valence_anchor_violations(full)
    modulation = evaluate_c2_modulation_causality(
        "R-c2-modulation-001", f"{_C2_PLAN.as_posix()}@{plan.version}",
        (gain, salience),
        recompute_ok=i1_match, n_expected=len(full),
    )
    collapse = evaluate_c2_anti_reward_collapse(
        "R-c2-collapse-002", f"{_C2_PLAN.as_posix()}@{plan.version}",
        r2max, recompute_ok=i1_match, n_expected=len(full),
    )
    dynamics_result = evaluate_c2_dynamics_input_driven(
        "R-c2-dynamics-003", f"{_C2_PLAN.as_posix()}@{plan.version}",
        dynamics, anchor_violations,
        recompute_ok=i1_match, n_expected=len(full),
    )
    leakage = run_leakage_suite(load_tree_sources(root))
    composite = evaluate_c2_composite(
        "R-c2-affect-001", f"{_C2_PLAN.as_posix()}@{plan.version}",
        (modulation, collapse, dynamics_result),
        mechanical_checks=mechanical,
        leakage_free=leakage.leakage_free,
        i1_match=i1_match,
        recompute_ok=i1_match,
        statistical_core=modulation,
        alpha=0.05,   # Holm 族 = 3 claim 级主判定 p（REV-0014 复核关切① 显式钉死）
    )
    _write_result(out_dir / "R-c2-affect-001.json", composite, len(full), {
        "modulation_causality": {"verdict": modulation.verdict.value,
                                 "criteria": list(modulation.data_refs),
                                 "mean_gain_diff": round(sum(gain) / len(gain), 6),
                                 "mean_salience_diff": round(sum(salience) / len(salience), 6)},
        "anti_reward_collapse": {"verdict": collapse.verdict.value,
                                 "data_refs": list(collapse.data_refs)},
        "dynamics_input_driven": {"verdict": dynamics_result.verdict.value,
                                  "mean_arousal_diff": round(sum(dynamics) / len(dynamics), 6),
                                  "anchor_violations": anchor_violations},
        "mechanical_checks": {k: bool(v) for k, v in mechanical.items()},
        "threshold_note": (
            "运行前修订 3（值域结构性发现）：believe_threshold 行为面在 MW0 量化后验值域"
            " {0, 0.2121, 0.9999, 1.0} 下结构性恒零——判据以机械面承载"
            "（threshold_value_domain_gap / chain_integrity / behavior_zero_effect），"
            "行为判据随 C3+ 值域扩展重评（Q-L02-02 行内补裁③）"
        ),
        "split_digest": split_digest,
        "stat_plan_digest": plan_digest,
        "i1_match": i1_match,
        "leakage_free": leakage.leakage_free,
        "leakage_report_digest": leakage.digest,
        "seed_note": "Q-L13-12④（master seed + 派生格式内嵌 stat plan）",
    })
    for name, result in (
        ("R-c2-modulation-001", modulation), ("R-c2-collapse-002", collapse),
        ("R-c2-dynamics-003", dynamics_result),
    ):
        _write_result(out_dir / f"{name}.json", result, len(full))
    return C2FirstEvaluation(
        composite=composite, modulation=modulation, collapse=collapse,
        dynamics=dynamics_result, mechanical=mechanical,
        i1_match=i1_match, leakage_free=leakage.leakage_free, out_dir=out_dir,
    )


class C2FirstEvaluation:
    """C2 首评数据集（复合 + 三子主张 + 机械判据）。"""

    def __init__(
        self, composite: Any, modulation: Any, collapse: Any, dynamics: Any,
        mechanical: dict[str, bool], i1_match: bool, leakage_free: bool,
        out_dir: Path,
    ) -> None:
        self.composite = composite
        self.modulation = modulation
        self.collapse = collapse
        self.dynamics = dynamics
        self.mechanical = mechanical
        self.i1_match = i1_match
        self.leakage_free = leakage_free
        self.out_dir = out_dir


'''
assert t.count(anchor_fn) == 1
t = t.replace(anchor_fn, fn_src + anchor_fn)

# 4) main() c2 分支
anchor_main = '    elif command == "c1":'
assert t.count(anchor_main) == 1
t = t.replace(anchor_main, '''    elif command == "c2":
        out_dir = root / "evidence" / "c2_affect_first_evaluation"
        result = run_c2_first_evaluation(root, out_dir)
        print(f"c2: modulation={result.modulation.verdict.value} "
              f"collapse={result.collapse.verdict.value} dynamics={result.dynamics.verdict.value} "
              f"composite={result.composite.verdict.value} i1={result.i1_match} "
              f"leakage_free={result.leakage_free}")
''' + anchor_main)

p.write_text(t, encoding="utf-8", newline="\n")
print("entry patched")
