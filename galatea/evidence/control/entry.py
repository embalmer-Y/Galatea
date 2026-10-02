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
from galatea.evidence.evaluator.hypotheses import (
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
    else:
        print(f"unknown command: {command}（m1|carryover|root）")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
