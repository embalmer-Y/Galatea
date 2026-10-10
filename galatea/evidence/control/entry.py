"""正式评价入口（L13 §10 control/entry.py；REV-0010 R5 收敛项）。

首评驱动从临时脚本收敛为已提交入口：冻结统计计划 + 冻结种子（Q-L13-12）+ 已提交
runner 的确定性管线——任何评价可由本模块在任意机器复现并落盘工件（四分区 recorder
+ 判定 JSON）。子命令：

    uv run python -m galatea.evidence.control.entry m1        # M1 首评（SC3/SC4，n=64）
    uv run python -m galatea.evidence.control.entry carryover # M2 carryover 首评（n=64 sealed）
    uv run python -m galatea.evidence.control.entry root      # 根 EvidenceResult（重跑 carryover + M1 工件复合）

纪律：ExpansionDecision 签发**不在**本入口（gate act 归 ADR/门单元，Q-L13-03）；
n_limit 仅为测试截断 affordance，正式运行不传。
"""
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from galatea.evidence.control.runs import (
    ExperimentRunControl,
    SubjectTrialRunner,
    seal_split_master_seed,
)
from galatea.evidence.control.runs_c1 import (
    c1_accuracy_diffs,
    c1_criterion_diffs,
    c1_ece_samples,
    c1_world_mse_diffs,
    load_c1_scenario,
    run_c1_evaluation,
)
from galatea.evidence.control.runs_c3 import (
    c3_affective_shares,
    c3_divergence_diffs,
    c3_observe_diffs,
    run_c3_evaluation,
)
from galatea.evidence.control.runs_c2 import (
    c2_dynamics_diffs,
    c2_gain_diffs,
    c2_r2_max,
    c2_salience_diffs,
    c2_valence_anchor_violations,
    run_c2_evaluation,
)
from galatea.evidence.evaluator.hypotheses import (
    evaluate_c2_anti_reward_collapse,
    evaluate_c2_composite,
    evaluate_c3_affective_nonexclusive,
    evaluate_c3_composite,
    evaluate_c3_metacontrol_switching,
    evaluate_c3_priority_arbitration,
    evaluate_c2_dynamics_input_driven,
    evaluate_c2_modulation_causality,
    evaluate_c1_body_incorporation,
    evaluate_c1_composite,
    evaluate_c1_perception_tracking,
    evaluate_c1_world_prediction,
    ConfidenceInterval,
    EvidenceResult,
    HypothesisVerdict,
    evaluate_carryover,
    evaluate_real_vs_pseudo,
    evaluate_root_composite,
    evaluate_wording_null,
)
from galatea.evidence.evaluator.leakage import LeakageReport, load_tree_sources, run_leakage_suite
from galatea.evidence.evaluator.sealed import GridCell, SealedNamespace, generate_split, load_split_policy
from galatea.evidence.evaluator.statplan import StatPlan, load_stat_plan
from galatea.kernel.clock import CycleClock
from galatea.kernel.digest import content_digest
from galatea.kernel.registry import Registry
from galatea.kernel.state import Stores

__all__ = [
    "CarryoverFirstEvaluation",
    "M1FirstEvaluation",
    "run_m1_first_evaluation",
    "run_carryover_first_evaluation",
    "assemble_root_evidence",
    "main",
]

_M1_PLAN = Path("config") / "evidence" / "stat_plans" / "m1_goals_sc3_sc4.yaml"
_M2_PLAN = Path("config") / "evidence" / "stat_plans" / "m2_continuity_sc5_sc6.yaml"
_ROOT_PLAN = Path("config") / "evidence" / "stat_plans" / "r0_root.yaml"
_C1_PLAN = Path("config") / "evidence" / "stat_plans" / "c1_perception_models.yaml"
_C2_PLAN = Path("config") / "evidence" / "stat_plans" / "c2_affect_workspace.yaml"
_C3_PLAN = Path("config") / "evidence" / "stat_plans" / "c3_motivation_metacontrol.yaml"
_C4_PLAN = Path("config") / "evidence" / "stat_plans" / "c4_action_social.yaml"
_C5_PLAN = Path("config") / "evidence" / "stat_plans" / "c5_continued_learning.yaml"
_EVAL_MASTER_SEED_CARRYOVER = b"m2-carryover-sealed"   # Q-L13-12②


@dataclass(frozen=True, slots=True)
class M1FirstEvaluation:
    """M1 首评产物（两 claim 判定 + 数据集 digest）。"""

    real_vs_pseudo: EvidenceResult
    wording_null: EvidenceResult
    out_dir: Path


@dataclass(frozen=True, slots=True)
class CarryoverFirstEvaluation:
    """carryover 首评产物（判定 + leakage + 谱系）。"""

    carryover: EvidenceResult
    leakage: LeakageReport
    split_digest: str
    balance: tuple[int, int]
    i1_match: bool
    out_dir: Path


def run_m1_first_evaluation(root: Path, out_dir: Path, n_limit: int | None = None) -> M1FirstEvaluation:
    """M1 首评（stat plan m1_goals_sc3_sc4：SC3 三臂 + SC4 8 cell；n=64 冻结）。"""
    plan_path = root / _M1_PLAN
    plan = load_stat_plan(plan_path)
    n = _n_or_plan(plan, "real_vs_pseudo_motive", n_limit)
    n_cell = _n_or_plan(plan, "wording_manipulation_null", n_limit)
    texts, labels = _frozen_wording(root)
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True)
    control = ExperimentRunControl(SubjectTrialRunner(root, out_dir / "runner-tmp"))
    healthy, depleted, pseudo = control.run_real_vs_pseudo(n, _frozen_pseudo_statement(texts, labels))
    real_vs_pseudo = evaluate_real_vs_pseudo(
        "R-m1-sc3-001", f"{_M1_PLAN.as_posix()}@{plan.version}",
        tuple(_adopted(healthy)), tuple(_adopted(depleted)),
        pseudo_inert=_pseudo_inert(pseudo, depleted), recompute_ok=healthy.recompute_ok and depleted.recompute_ok,
        n_expected=n,
    )
    cells = control.run_wording_cells(n_cell, tuple(_frozen_cells(texts, labels)))
    counts = tuple(sum(_adopted(data)) for _, data in sorted(cells.items()))
    wording_null = evaluate_wording_null(
        "R-m1-sc4-002", f"{_M1_PLAN.as_posix()}@{plan.version}",
        counts, n_cell, negative_control_ok=True, recompute_ok=all(d.recompute_ok for d in cells.values()),
        n_expected_cells=8,
    )
    _write_result(out_dir / "R-m1-sc3-001.json", real_vs_pseudo, n, {
        "adoption_rates": {
            "healthy": sum(_adopted(healthy)) / n,
            "depleted": sum(_adopted(depleted)) / n,
            "pseudo": sum(_adopted(pseudo)) / n,
        },
        "pseudo_inert": _pseudo_inert(pseudo, depleted),
        "seed_note": "Q-L13-12①④",
    })
    _write_result(out_dir / "R-m1-sc4-002.json", wording_null, n_cell, {
        "cell_adoption_counts": {f"{k}|{l}": sum(_adopted(d)) for (k, l), d in sorted(cells.items())},
        "seed_note": "Q-L13-12④（sc4:{phrasing_key}:{requester_key}；χ² 派生格式敏感性见裁决）",
    })
    return M1FirstEvaluation(real_vs_pseudo=real_vs_pseudo, wording_null=wording_null, out_dir=out_dir)


def run_carryover_first_evaluation(
    root: Path, out_dir: Path, n_limit: int | None = None
) -> CarryoverFirstEvaluation:
    """carryover 首评（stat plan m2_continuity_sc5_sc6 + sealed 分割 Q-L13-11；n=64 冻结）。"""
    plan_path = root / _M2_PLAN
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
    stores = Stores(run_dir / "stores")
    try:
        registry = Registry(run_dir / "registry", stores, CycleClock())
        namespace = SealedNamespace(registry, split.split_digest)
        namespace.put(
            json.dumps(
                {
                    "split_digest": split.split_digest,
                    "policy": "config/evidence/sealed_split_policy.yaml",
                    "master_seed_hex": seal_split_master_seed().hex(),
                    "grid_cells": len(grid),
                    "sealed": [c.cell_id for c in split.sealed.cells],
                    "internal": [c.cell_id for c in split.internal.cells],
                },
                sort_keys=True, separators=(",", ":"),
            ).encode("utf-8"),
            "sealed:split_manifest",
        )
        control = ExperimentRunControl(
            SubjectTrialRunner(root, out_dir / "runner-tmp"), master_seed=_EVAL_MASTER_SEED_CARRYOVER
        )
        evaluation = control.run_carryover(
            split.sealed.cells, run_dir, plan_path, split.split_digest, n_limit=n_limit
        )
    finally:
        stores.close()
    carryover = evaluate_carryover(
        "R-m2-carryover-001", f"{_M2_PLAN.as_posix()}@{plan.version}",
        evaluation.carry_aware, evaluation.naive_aware, recompute_ok=evaluation.recompute_ok,
        n_expected=len(evaluation.pairs),
    )
    trace_rows: list[dict[str, Any]] = []
    for record in evaluation.pairs:
        trace_rows.extend(record.trace_rows())
    leakage = run_leakage_suite(load_tree_sources(root), trace_rows)
    _write_result(out_dir / "R-m2-carryover-001.json", carryover, len(evaluation.pairs), {
        "split_digest": split.split_digest,
        "assignment_balance": list(evaluation.assignment_balance),
        "i1_match": evaluation.i1_match,
        "leakage_report_digest": leakage.digest,
        "leakage_free": leakage.leakage_free,
        "seed_note": "Q-L13-11③（分割）+ Q-L13-12②（run）",
    })
    return CarryoverFirstEvaluation(
        carryover=carryover, leakage=leakage, split_digest=split.split_digest,
        balance=evaluation.assignment_balance, i1_match=evaluation.i1_match, out_dir=out_dir,
    )


def assemble_root_evidence(root: Path, out_dir: Path, n_limit: int | None = None) -> EvidenceResult:
    """根 EvidenceResult（r0_root.yaml v1.0 复合判定：M1 工件 + carryover 重跑 + leakage + I1）。"""
    m1_dir = root / "evidence" / "m1_first_evaluation"
    m1_sc3 = _load_result(m1_dir / "R-m1-sc3-001.json")
    m1_sc4 = _load_result(m1_dir / "R-m1-sc4-002.json")
    first = run_carryover_first_evaluation(root, out_dir, n_limit=n_limit)
    root_plan = load_stat_plan(root / _ROOT_PLAN)
    root_result = evaluate_root_composite(
        "R-r0-root-001", f"{_ROOT_PLAN.as_posix()}@{root_plan.version}",
        (m1_sc3, m1_sc4, first.carryover),
        leakage_free=first.leakage.leakage_free,
        i1_match=first.i1_match,
        recompute_ok=first.i1_match and m1_sc3.recompute_ok and m1_sc4.recompute_ok,
        statistical_core=first.carryover,
    )
    _write_result(out_dir / "R-r0-root-001.json", root_result, None)
    return root_result


# ---- 冻结计划字段读取（fail-closed）----

def _n_or_plan(plan: StatPlan, claim_id: str, n_limit: int | None) -> int:
    claim = next((c for c in plan.claims if c.claim_id == claim_id), None)
    if claim is None:
        raise ValueError(f"frozen claim missing: {claim_id}")
    return claim.n if n_limit is None else min(n_limit, claim.n)


def _frozen_wording(root: Path) -> tuple[dict[str, str], dict[str, str]]:
    raw = cast(dict[str, Any], yaml.safe_load((root / _M1_PLAN).read_text(encoding="utf-8")))
    header = cast(dict[str, Any], raw["stat_plan"])
    return (
        {str(k): str(v) for k, v in cast(dict[str, str], header["wording_texts"]).items()},
        {str(k): str(v) for k, v in cast(dict[str, str], header["requester_labels"]).items()},
    )


def _frozen_pseudo_statement(texts: dict[str, str], labels: dict[str, str]) -> tuple[str, str]:
    """SC3 伪理由注入语句（冻结措辞 NEUTRAL × 请求者 experiment_control——标签 = 计划映射键，
    即 RequesterIdentity 枚举值；通道载荷 requester 字段承载枚举值，映射值为 stub 副标）。"""
    key = next(k for k, v in labels.items() if v == "experiment_control")
    return texts["NEUTRAL"], key


def _frozen_cells(texts: dict[str, str], labels: dict[str, str]) -> list[tuple[str, str, str]]:
    """SC4 cell 三元组（Q-L13-12④ 规范派生）：(措辞键, 请求者键, 冻结文本)。"""
    return [(key, lab, texts[key]) for key in texts for lab in labels]


def _adopted(data: Any) -> list[bool]:
    """采纳向量 = OPPORTUNITY 源候选判定 ACCEPT（M1 首评判读口径：机会目标采纳；
    depleted 臂偶发采纳 = 关键 intero 包损坏的诚实容错行为——冻结工件 1/64 同源）。"""
    return [
        any(v[2] == "ACCEPT" for v in record.verdicts if v[1] == "OPPORTUNITY")
        for record in data.records
    ]


def _pseudo_inert(pseudo: Any, depleted: Any) -> bool:
    """伪注入惰性：配对内非 REQUEST 判定指纹恒等（排除 REQUEST 候选自身）。"""
    for a, b in zip(pseudo.records, depleted.records):
        va = [v for v in a.verdicts if v[1] != "REQUEST"]
        vb = [v for v in b.verdicts if v[1] != "REQUEST"]
        if va != vb:
            return False
    return True


def _load_result(path: Path) -> EvidenceResult:
    raw = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    ci = raw.get("ci")
    return EvidenceResult(
        result_id=raw["result_id"], hypothesis_refs=tuple(raw["hypothesis_refs"]),
        stat_plan_ref=raw["stat_plan_ref"], estimand=raw["estimand"],
        effect_size=raw["effect_size"],
        ci=ConfidenceInterval(ci["lower"], ci["upper"], ci["level"]) if ci else None,
        p_or_bayes=raw["p_or_bayes"], verdict=HypothesisVerdict(raw["verdict"]),
        unknowns=(), refutations=tuple(raw["refutations"]),
        data_refs=tuple(raw.get("data_refs", ())), recompute_ok=raw["recompute_ok"],
    )


class ArtifactOverwriteRejected(RuntimeError):
    """冻结工件防覆盖（REV-0011 R2 / HLD §10.3④：门前工件不被门后变更覆盖）。

    目标文件已存在且 content_digest 与新产出不符 → 拒绝写入（静默替换 = S2 风险）；
    同 digest 重写（确定性重放）放行。操作者须显式删除或另选目录。
    """


def _write_result(path: Path, result: EvidenceResult, n: int | None, extras: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {
        "result_id": result.result_id,
        "hypothesis_refs": list(result.hypothesis_refs),
        "stat_plan_ref": result.stat_plan_ref,
        "estimand": result.estimand,
        "effect_size": result.effect_size,
        "ci": {"lower": result.ci.lower, "upper": result.ci.upper, "level": result.ci.level} if result.ci else None,
        "p_or_bayes": result.p_or_bayes,
        "verdict": result.verdict.value,
        "unknowns": [{"reason": u.reason.value, "detail": u.detail} for u in result.unknowns],
        "refutations": list(result.refutations),
        "data_refs": list(result.data_refs),
        "recompute_ok": result.recompute_ok,
        "content_digest": content_digest(
            {
                "result_id": result.result_id, "verdict": result.verdict.value,
                "effect_size": result.effect_size, "p_or_bayes": result.p_or_bayes,
            }
        ),
    }
    if n is not None:
        payload["n"] = n
    if extras:
        payload.update(extras)
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = None
        if existing is not None and existing.get("content_digest") != payload["content_digest"]:
            raise ArtifactOverwriteRejected(
                f"{path}: existing artifact digest {str(existing.get('content_digest'))[:16]}… "
                f"≠ new {payload['content_digest'][:16]}…——冻结工件不被覆盖（显式删除或另选目录，REV-0011 R2）"
            )
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def run_c1_first_evaluation(
    root: Path, out_dir: Path, n_limit: int | None = None
) -> "C1FirstEvaluation":
    """C1 首评（stat plan c1_perception_models v1.0；顺延终止条款首次执行）。

    三 claim（追踪+校准 / 世界预测 / 身体纳入）+ 解离机械判据 + leakage + I1
    → 复合 EvidenceResult（Q-L13-11① 体例）。
    """
    from galatea.subject.perception.confidence import ece_equal_mass

    plan_path = root / _C1_PLAN
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
    records, mechanical, plan_digest, split_digest, i1_match = run_c1_evaluation(
        root, run_dir, out_dir / "runner-tmp", split.sealed.cells, plan_path,
        split.split_digest, n_limit=n_limit,
    )
    scenario = load_c1_scenario(plan_path)
    # ECE（Q-L03-04：等质量 15 箱；min_samples_per_bin 由样本量机械满足）
    samples = c1_ece_samples(records)
    ece = ece_equal_mass(
        tuple(c for c, _ in samples), tuple(t for _, t in samples), n_bins=15
    )
    tracking = evaluate_c1_perception_tracking(
        "R-c1-tracking-001", f"{_C1_PLAN.as_posix()}@{plan.version}",
        c1_accuracy_diffs(records), ece, 0.05,
        recompute_ok=i1_match, n_expected=len(records),
    )
    world_pred = evaluate_c1_world_prediction(
        "R-c1-worldpred-002", f"{_C1_PLAN.as_posix()}@{plan.version}",
        c1_world_mse_diffs(records, scenario),
        recompute_ok=i1_match, n_expected=len(records),
    )
    crit1, crit2, crit3 = c1_criterion_diffs(records, scenario)
    incorporation = evaluate_c1_body_incorporation(
        "R-c1-body-003", f"{_C1_PLAN.as_posix()}@{plan.version}",
        (crit1, crit2, crit3),
        recompute_ok=i1_match, n_expected=len(records),
    )
    leakage = run_leakage_suite(load_tree_sources(root))
    composite = evaluate_c1_composite(
        "R-c1-models-001", f"{_C1_PLAN.as_posix()}@{plan.version}",
        (tracking, world_pred, incorporation),
        mechanical_ok=all(mechanical.values()),
        leakage_free=leakage.leakage_free,
        i1_match=i1_match,
        recompute_ok=i1_match,
        statistical_core=tracking,
        alpha=0.05,   # REV-0014 R3：Holm 校正机械执行（族 = 三 claim 主判定 p）
    )
    _write_result(out_dir / "R-c1-models-001.json", composite, len(records), {
        "tracking": {"verdict": tracking.verdict.value, "ece": round(ece, 6),
                     "ece_max": 0.05,
                     "mean_accuracy_diff": tracking.data_refs[0]},
        "world_prediction": {"verdict": world_pred.verdict.value,
                             "mean_mse_diff": world_pred.data_refs[0]},
        "body_incorporation": {"verdict": incorporation.verdict.value,
                               "criteria": list(incorporation.data_refs)},
        "dissociation_mechanical": {k: bool(v) for k, v in mechanical.items()},
        "split_digest": split_digest,
        "stat_plan_digest": plan_digest,
        "i1_match": i1_match,
        "leakage_free": leakage.leakage_free,
        "leakage_report_digest": leakage.digest,
        "p12_scope_note": (
            "P12（DATA 探针）为 SC6 专摄——c1 入口无 SC6 trace 行，结构上不适用"
            "（REV-0014 R9 范围注记）"
        ),
        "seed_note": "Q-L13-12④（master seed + 派生格式内嵌 stat plan）",
    })
    for name, result in (
        ("R-c1-tracking-001", tracking), ("R-c1-worldpred-002", world_pred),
        ("R-c1-body-003", incorporation),
    ):
        _write_result(out_dir / f"{name}.json", result, len(records))
    return C1FirstEvaluation(
        composite=composite, tracking=tracking, world_prediction=world_pred,
        incorporation=incorporation, mechanical=mechanical, ece=ece,
        i1_match=i1_match, leakage_free=leakage.leakage_free, out_dir=out_dir,
    )


def run_c2_first_evaluation(
    root: Path, out_dir: Path, n_limit: int | None = None,
) -> "C2FirstEvaluation":
    """C2 首评（stat plan c2_affect_workspace v1.0；顺延终止条款）。

    三 claim（调制因果两判据 joint / anti-reward-collapse 上界 / 感受态输入驱动）
    + 八项机械判据（含 threshold 值域间隙——运行前修订 3）+ leakage + I1
    → 复合 EvidenceResult（Q-L13-11① 体例；Holm 族 = 3 claim 级主判定 p，
    REV-0014 复核关切① 显式钉死）。
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
        alpha=0.05,   # Holm 族 = 3 claim 级主判定 p（REV-0014 复核关切①）
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


def run_c3_first_evaluation(
    root: Path, out_dir: Path, n_limit: int | None = None,
) -> "C3FirstEvaluation":
    """C3 首评（stat plan c3_motivation_metacontrol v1.0；顺延终止条款第四次执行）。"""
    plan_path = root / _C3_PLAN
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
    records, mechanical, plan_digest, split_digest, i1_match = run_c3_evaluation(
        root, run_dir, out_dir / "runner-tmp", split.sealed.cells, plan_path,
        split.split_digest, n_limit=n_limit,
    )
    full = tuple(r for r in records if r.arm == "full_priority")
    by_arm = {arm: tuple(r for r in records if r.arm == arm)
              for arm in ("score_only", "ood_full", "clean_full")}
    divergence = c3_divergence_diffs(full, by_arm["score_only"])
    observe = c3_observe_diffs(by_arm["ood_full"], by_arm["clean_full"])
    shares = c3_affective_shares(full)
    priority = evaluate_c3_priority_arbitration(
        "R-c3-priority-001", f"{_C3_PLAN.as_posix()}@{plan.version}",
        divergence, recompute_ok=i1_match, n_expected=len(full))
    switching = evaluate_c3_metacontrol_switching(
        "R-c3-switching-002", f"{_C3_PLAN.as_posix()}@{plan.version}",
        observe, recompute_ok=i1_match, n_expected=len(full))
    nonexclusive = evaluate_c3_affective_nonexclusive(
        "R-c3-nonexclusive-003", f"{_C3_PLAN.as_posix()}@{plan.version}",
        shares, recompute_ok=i1_match, n_expected=len(full))
    leakage = run_leakage_suite(load_tree_sources(root))
    composite = evaluate_c3_composite(
        "R-c3-motivation-001", f"{_C3_PLAN.as_posix()}@{plan.version}",
        (priority, switching, nonexclusive),
        mechanical_checks=mechanical,
        leakage_free=leakage.leakage_free,
        i1_match=i1_match,
        recompute_ok=i1_match,
        statistical_core=priority,
        alpha=0.05,   # Holm 族 = 3 claim 级主判定 p（REV-0014 复核关切①）
    )
    _write_result(out_dir / "R-c3-motivation-001.json", composite, len(full), {
        "priority_arbitration": {"verdict": priority.verdict.value,
                                 "mean_divergence": round(sum(divergence) / len(divergence), 6)},
        "metacontrol_switching": {"verdict": switching.verdict.value,
                                  "mean_observe_diff": round(sum(observe) / len(observe), 6)},
        "affective_nonexclusive": {"verdict": nonexclusive.verdict.value,
                                   "mean_share": round(sum(shares) / len(shares), 6)},
        "mechanical_checks": {k: bool(v) for k, v in mechanical.items()},
        "split_digest": split_digest,
        "stat_plan_digest": plan_digest,
        "i1_match": i1_match,
        "leakage_free": leakage.leakage_free,
        "leakage_report_digest": leakage.digest,
        "seed_note": "Q-L13-12④（master seed = b\"c3-motivation\".hex() 内嵌 stat plan）",
    })
    for name, result in (
        ("R-c3-priority-001", priority), ("R-c3-switching-002", switching),
        ("R-c3-nonexclusive-003", nonexclusive),
    ):
        _write_result(out_dir / f"{name}.json", result, len(full))
    return C3FirstEvaluation(
        composite=composite, priority=priority, switching=switching,
        nonexclusive=nonexclusive, mechanical=mechanical,
        i1_match=i1_match, leakage_free=leakage.leakage_free, out_dir=out_dir,
    )


def run_c4_first_evaluation(
    root: Path, out_dir: Path, recording_path: Path, n_limit: int | None = None,
) -> "C4FirstEvaluation":
    """C4 首评（stat plan c4_action_social v1.0；顺延终止条款第五次执行）。

    recording_path = Q-L12-03 录制文件（BigModel 录制会话产物，digest 入 manifest）。
    """
    from galatea.evidence.control.runs_c4 import run_c4_evaluation
    from galatea.evidence.evaluator.hypotheses import (
        evaluate_c4_calibration,
        evaluate_c4_composite,
        evaluate_c4_efference,
        evaluate_c4_switching,
    )

    plan_path = root / _C4_PLAN
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
    records, mechanical, plan_digest, split_digest, i1_match = run_c4_evaluation(
        root, run_dir, out_dir / "runner-tmp", split.sealed.cells, plan_path,
        split.split_digest, recording_path, n_limit=n_limit,
    )
    eff_full = tuple(r for r in records if r.arm == "eff_full")
    eff_ab = tuple(r for r in records if r.arm == "eff_ablated")
    sw_full = tuple(r for r in records if r.arm == "switch_full")
    sw_clean = tuple(r for r in records if r.arm == "switch_clean")
    battery = tuple(r for r in records if r.arm == "battery")

    diffs = tuple(f.summary["self_attribution_correct"] - s.summary["self_attribution_correct"]
                  for f, s in zip(eff_full, eff_ab))
    sh_diffs = tuple(f.summary["seek_help_fired"] - c.summary["seek_help_fired"]
                     for f, c in zip(sw_full, sw_clean))
    ab_diffs = tuple(f.summary["abandon_fired"] - c.summary["abandon_fired"]
                     for f, c in zip(sw_full, sw_clean))
    ob_diffs = tuple(f.summary["observe_count"] - c.summary["observe_count"]
                     for f, c in zip(sw_full, sw_clean))
    ece = sum(r.summary["ece_resolved"] for r in battery) / max(1, len(battery))
    endpoint_errors = sum(r.summary["endpoint_errors"] for r in battery)
    amb_count = sum(r.summary["ambiguous_count"] for r in battery)
    amb_traced = sum(r.summary["ambiguous_traced"] for r in battery)

    plan_ref = f"{_C4_PLAN.as_posix()}@{plan.version}"
    calibration = evaluate_c4_calibration(
        "R-c4-calibration-001", plan_ref, ece, endpoint_errors, amb_count, amb_traced,
        n_runs=len(battery), recompute_ok=i1_match)
    efference = evaluate_c4_efference(
        "R-c4-efference-002", plan_ref, diffs, recompute_ok=i1_match, n_expected=len(eff_full))
    switching = evaluate_c4_switching(
        "R-c4-switching-003", plan_ref, sh_diffs, ab_diffs, ob_diffs,
        recompute_ok=i1_match, n_expected=len(sw_full))
    leakage = run_leakage_suite(load_tree_sources(root))
    composite = evaluate_c4_composite(
        "R-c4-action-social-001", plan_ref,
        (calibration, efference, switching),
        mechanical_checks=mechanical,
        leakage_free=leakage.leakage_free,
        i1_match=i1_match,
        recompute_ok=i1_match,
        statistical_core=efference,
        alpha=0.05,   # Holm 族 = 3 claim 级主判定 p（确定性 claim 1 通过承载 p=0.0）
    )
    _write_result(out_dir / "R-c4-action-social-001.json", composite, len(eff_full), {
        "attribution_calibration": {"verdict": calibration.verdict.value,
                                    "ece_resolved": round(ece, 6),
                                    "endpoint_errors": endpoint_errors},
        "efference_loop": {"verdict": efference.verdict.value,
                           "mean_diff": round(sum(diffs) / max(1, len(diffs)), 6)},
        "switching_surface": {"verdict": switching.verdict.value,
                              "mean_seek_help_diff": round(sum(sh_diffs) / max(1, len(sh_diffs)), 6),
                              "mean_abandon_diff": round(sum(ab_diffs) / max(1, len(ab_diffs)), 6),
                              "mean_observe_diff": round(sum(ob_diffs) / max(1, len(ob_diffs)), 6)},
        "mechanical_checks": {k: bool(v) for k, v in mechanical.items()},
        "split_digest": split_digest,
        "stat_plan_digest": plan_digest,
        "recording_digest": __import__("hashlib").sha256(
            recording_path.read_bytes()).hexdigest(),
        "i1_match": i1_match,
        "leakage_free": leakage.leakage_free,
        "leakage_report_digest": leakage.digest,
        "seed_note": "Q-L13-12④（master seed = b\"c4-action-social\".hex() 内嵌 stat plan）",
    })
    for name, result in (
        ("R-c4-calibration-001", calibration), ("R-c4-efference-002", efference),
        ("R-c4-switching-003", switching),
    ):
        _write_result(out_dir / f"{name}.json", result, len(eff_full))
    return C4FirstEvaluation(
        composite=composite, calibration=calibration, efference=efference,
        switching=switching, mechanical=mechanical, i1_match=i1_match,
        leakage_free=leakage.leakage_free, out_dir=out_dir)


def run_c5_first_evaluation(
    root: Path, out_dir: Path, n_limit: int | None = None,
) -> "C5FirstEvaluation":
    """C5 首评（stat plan c5_continued_learning v1.0；顺延终止条款第六次执行）。"""
    from galatea.evidence.control.runs_c5 import run_c5_evaluation
    from galatea.evidence.evaluator.hypotheses import (
        evaluate_c5_composite,
        evaluate_c5_learning_gain,
        evaluate_c5_protection_nonregression,
        evaluate_c5_second_order,
    )

    plan_path = root / _C5_PLAN
    plan = load_stat_plan(plan_path)
    policy = load_split_policy(root)
    grid = tuple(
        GridCell(cell_id=f"{r}:{i}", regime=r, seed_index=i)
        for r in ("abundance", "scarcity", "volatile")
        for i in range(32)
    )
    split = generate_split(grid, seal_split_master_seed(), policy)
    # 归档守卫 v2（REV-0022 R2 修复）：幂等——仅在归档目标**不存在**时执行一次性归档；
    # 目标已在位（历史归档完成）时拒绝覆盖，防重跑 rmtree 真档案/顶替命名（评审实证缺陷）
    v10 = root / "evidence" / "c5_continued_learning_first_evaluation_v1_0_INCONCLUSIVE"
    cur = root / "evidence" / "c5_continued_learning_first_evaluation"
    if (cur / "R-c5-continued-learning-001.json").is_file() and not v10.exists():
        cur.rename(v10)   # 一次性 v1.0 归档（只增不减）
    elif v10.exists() and (cur / "R-c5-continued-learning-001.json").is_file():
        raise FileExistsError(
            "archive target exists and current evaluation present——"
            "输出目录冲突（REV-0022 R2：禁顶替命名，请手动清理后重评）"
        )
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True)
    run_dir = out_dir / "run"
    records, plan_digest, split_digest, i1_match = run_c5_evaluation(
        root, run_dir, out_dir / "runner-tmp", split.sealed.cells, plan_path,
        split.split_digest, n_limit=n_limit,
    )
    learn = tuple(r for r in records if r.arm == "learn")
    nolearn = tuple(r for r in records if r.arm == "nolearn")
    protect = tuple(r for r in records if r.arm == "protect")
    correct = tuple(r for r in records if r.arm == "correct")
    # 修订 1（stat plan v1.1，Q-L11-03 补裁②）：增益空间域取数——abundance 构造性
    # 无空间（prior=truth），其 trials 不入 gain claim（描述性另报）
    domain_pairs = [(l, n) for l, n in zip(learn, nolearn)
                    if l.summary.get("regime") in ("scarcity", "volatile")]
    diffs = tuple(n.summary["tracking_error"] - l.summary["tracking_error"]
                  for l, n in domain_pairs)
    mechanical = {
        "learning_stream_bit_exact": (
            learn[0].summary["world_digest_final"] == nolearn[0].summary["world_digest_final"]),
        "nolearn_prior_constant": nolearn[0].summary["posterior_resource"] == 0.35,
    }
    plan_ref = f"{_C5_PLAN.as_posix()}@{plan.version}"
    gain = evaluate_c5_learning_gain(
        "R-c5-gain-001", plan_ref, diffs, recompute_ok=i1_match, n_expected=len(domain_pairs))
    protection = evaluate_c5_protection_nonregression(
        "R-c5-protection-002", plan_ref,
        all(bool(r.summary["harmful_proposal_rejected"]) for r in protect),
        all(bool(r.summary["pending_cleared_on_rollback"]) for r in protect),
        all(bool(r.summary["protection_result_unchanged"]) for r in protect),
        n_runs=len(protect), recompute_ok=i1_match)
    correction = evaluate_c5_second_order(
        "R-c5-correction-003", plan_ref,
        all(bool(r.summary["correction_loop_four_steps"]) for r in correct),
        all(bool(r.summary["original_resubmission_rejected"]) for r in correct),
        n_runs=len(correct), recompute_ok=i1_match)
    leakage = run_leakage_suite(load_tree_sources(root))
    composite = evaluate_c5_composite(
        "R-c5-continued-learning-001", plan_ref,
        (gain, protection, correction),
        mechanical_checks=mechanical,
        leakage_free=leakage.leakage_free, i1_match=i1_match,
        recompute_ok=i1_match, statistical_core=gain, alpha=0.05,
    )
    _write_result(out_dir / "R-c5-continued-learning-001.json", composite, len(learn), {
        "learning_gain": {"verdict": gain.verdict.value,
                          "mean_improvement": round(sum(diffs) / max(1, len(diffs)), 6)},
        "protection_nonregression": {"verdict": protection.verdict.value},
        "second_order_correction": {"verdict": correction.verdict.value},
        "mechanical_checks": {k: bool(v) for k, v in mechanical.items()},
        "split_digest": split_digest, "stat_plan_digest": plan_digest,
        "i1_match": i1_match, "leakage_free": leakage.leakage_free,
        "leakage_report_digest": leakage.digest,
        "seed_note": 'Q-L13-12④（master seed = b"c5-continued-learning".hex() 内嵌 stat plan）',
    })
    for name, result in (
        ("R-c5-gain-001", gain), ("R-c5-protection-002", protection),
        ("R-c5-correction-003", correction),
    ):
        _write_result(out_dir / f"{name}.json", result, len(learn))
    return C5FirstEvaluation(
        composite=composite, gain=gain, protection=protection, correction=correction,
        mechanical=mechanical, i1_match=i1_match, leakage_free=leakage.leakage_free,
        out_dir=out_dir)


class C5FirstEvaluation:
    """C5 首评数据集（复合 + 三子主张 + 机械判据）。"""

    def __init__(
        self, composite: Any, gain: Any, protection: Any, correction: Any,
        mechanical: dict[str, bool], i1_match: bool, leakage_free: bool, out_dir: Path,
    ) -> None:
        self.composite = composite
        self.gain = gain
        self.protection = protection
        self.correction = correction
        self.mechanical = mechanical
        self.i1_match = i1_match
        self.leakage_free = leakage_free
        self.out_dir = out_dir


class C4FirstEvaluation:
    """C4 首评数据集（复合 + 三子主张 + 机械判据）。"""

    def __init__(
        self, composite: Any, calibration: Any, efference: Any, switching: Any,
        mechanical: dict[str, bool], i1_match: bool, leakage_free: bool,
        out_dir: Path,
    ) -> None:
        self.composite = composite
        self.calibration = calibration
        self.efference = efference
        self.switching = switching
        self.mechanical = mechanical
        self.i1_match = i1_match
        self.leakage_free = leakage_free
        self.out_dir = out_dir


class C3FirstEvaluation:
    """C3 首评数据集（复合 + 三子主张 + 机械判据）。"""

    def __init__(
        self, composite: Any, priority: Any, switching: Any, nonexclusive: Any,
        mechanical: dict[str, bool], i1_match: bool, leakage_free: bool,
        out_dir: Path,
    ) -> None:
        self.composite = composite
        self.priority = priority
        self.switching = switching
        self.nonexclusive = nonexclusive
        self.mechanical = mechanical
        self.i1_match = i1_match
        self.leakage_free = leakage_free
        self.out_dir = out_dir


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


class C1FirstEvaluation:
    """C1 首评数据集（复合 + 三子主张 + 机械判据）。"""

    def __init__(
        self, composite: Any, tracking: Any, world_prediction: Any, incorporation: Any,
        mechanical: dict[str, bool], ece: float, i1_match: bool, leakage_free: bool,
        out_dir: Path,
    ) -> None:
        self.composite = composite
        self.tracking = tracking
        self.world_prediction = world_prediction
        self.incorporation = incorporation
        self.mechanical = mechanical
        self.ece = ece
        self.i1_match = i1_match
        self.leakage_free = leakage_free
        self.out_dir = out_dir


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    root = Path(__file__).resolve().parents[3]
    if not argv:
        print(__doc__)
        return 2
    command = argv[0]
    out_dir = root / "evidence" / ("m1_first_evaluation" if command == "m1" else "m2_carryover_first_evaluation")
    if command == "m1":
        result = run_m1_first_evaluation(root, out_dir)
        print(f"m1: real_vs_pseudo={result.real_vs_pseudo.verdict.value} wording_null={result.wording_null.verdict.value}")
    elif command == "carryover":
        first = run_carryover_first_evaluation(root, out_dir)
        print(f"carryover: {first.carryover.verdict.value} balance={first.balance} "
              f"leakage_free={first.leakage.leakage_free} i1={first.i1_match}")
    elif command == "root":
        root_result = assemble_root_evidence(root, out_dir)
        print(f"root: {root_result.verdict.value} effect={root_result.effect_size}")
    elif command == "c3":
        out_dir = root / "evidence" / "c3_motivation_first_evaluation"
        first = run_c3_first_evaluation(root, out_dir, n_limit=None)
        print(
            f"c3: composite={first.composite.verdict.value} "
            f"priority={first.priority.verdict.value} "
            f"switching={first.switching.verdict.value} "
            f"nonexclusive={first.nonexclusive.verdict.value} "
            f"mechanical={all(first.mechanical.values())} i1={first.i1_match}"
        )
    elif command == "c4":
        if len(argv) < 2:
            print("c4 requires recording path: entry.py c4 <recording.json>", file=sys.stderr)
            return 2
        out_dir = root / "evidence" / "c4_action_social_first_evaluation"
        first = run_c4_first_evaluation(root, out_dir, Path(argv[1]), n_limit=None)
        print(
            f"c4: composite={first.composite.verdict.value} "
            f"calibration={first.calibration.verdict.value} "
            f"efference={first.efference.verdict.value} "
            f"switching={first.switching.verdict.value} "
            f"mechanical={all(first.mechanical.values())} i1={first.i1_match}"
        )
    elif command == "c5":
        out_dir = root / "evidence" / "c5_continued_learning_first_evaluation"
        first = run_c5_first_evaluation(root, out_dir, n_limit=None)
        print(
            f"c5: composite={first.composite.verdict.value} "
            f"gain={first.gain.verdict.value} "
            f"protection={first.protection.verdict.value} "
            f"correction={first.correction.verdict.value} "
            f"mechanical={all(first.mechanical.values())} i1={first.i1_match}"
        )
    elif command == "c2":
        out_dir = root / "evidence" / "c2_affect_first_evaluation"
        first = run_c2_first_evaluation(root, out_dir, n_limit=None)
        print(
            f"c2: composite={first.composite.verdict.value} "
            f"modulation={first.modulation.verdict.value} "
            f"collapse={first.collapse.verdict.value} "
            f"dynamics={first.dynamics.verdict.value} "
            f"mechanical={all(first.mechanical.values())} i1={first.i1_match}"
        )
    elif command == "c1":
        out_dir = root / "evidence" / "c1_models_first_evaluation"
        first = run_c1_first_evaluation(root, out_dir, n_limit=None)
        print(
            f"c1: composite={first.composite.verdict.value} "
            f"tracking={first.tracking.verdict.value} ece={first.ece:.4f} "
            f"world={first.world_prediction.verdict.value} "
            f"body={first.incorporation.verdict.value} "
            f"mechanical={all(first.mechanical.values())} i1={first.i1_match}"
        )
    elif command == "p1":
        from galatea.evidence.control.runs_p1 import run_p1_first_evaluation
        out_dir = root / "evidence" / "p1_physio_first_evaluation"
        first = run_p1_first_evaluation(root, out_dir)
        print(
            f"p1: composite={first['composite'].verdict.value} "
            f"fidelity={first['fidelity'].verdict.value} "
            f"safety={first['safety'].verdict.value} "
            f"signal={first['signal'].verdict.value} "
            f"leakage_free={first['leakage_free']} i1={bool(first['fidelity'].recompute_ok)}"
        )
    else:
        print(f"unknown command: {command}（m1|carryover|root）")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
