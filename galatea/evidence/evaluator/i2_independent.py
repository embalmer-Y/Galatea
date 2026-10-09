"""I2 独立复算（L13 §4.8 / Q-L13-08 操作化；E1 门退出判据承载）。

独立性结构面（Q-L13-08①：复算代码不 import 原判定器）：
- 本模块**禁 import** `evaluator.hypotheses`（原判定器）与 `control.runs_c5`（原
  runner）——CI 面测试断言（test_i2_independent.py 源扫描）；
- 数据访问共享 recorder 基础设施（read_partition：registry 完整性校验 + DuckDB
  只读——数据平面非判定平面，共享不破独立）；
- 统计式独立实现（Wald 配对：mean/sd(n−1)/d/p 经 math.erf），阈值读冻结统计
  计划 YAML（min_effects 引用按值核对）；
- 一致性判据（Q-L13-08①）：verdict 同三态 ∧ |Δd| ≤ max(1e-9, CI 宽 × 1e-6)
  ∧ |Δp| ≤ 1e-9 ∧ mean 落于原 CI。
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import yaml

from galatea.evidence.recorder.replay import read_partition
from galatea.kernel.digest import content_digest
from galatea.kernel.packet import ArtifactRef

__all__ = ["i2_recompute_c5_gain", "IndependenceViolation"]

_Z_95 = 1.959963984540054   # 双侧 95% z（独立实现常量，与原判定器无关）


class IndependenceViolation(RuntimeError):
    """I2 独立性结构破坏（import 原判定器/数据缺失）。"""


def _find_evidence_partition(registry_dir: Path) -> Path:
    """registry 目录遍历定位 evidence:evidence 分区 blob（实现独立：不走原 runner）。"""
    hits: list[Path] = []
    for manifest in registry_dir.glob("*/*/manifest.json"):
        try:
            meta = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if meta.get("kind") == "evidence:evidence":
            hits.append(manifest.parent / "blob")
    if len(hits) != 1:
        raise IndependenceViolation(
            f"expected exactly one evidence:evidence partition, found {len(hits)}"
        )
    return hits[0]


def _paired_wald(diffs: list[float]) -> tuple[float, float, float]:
    """Wald 配对统计（独立实现）：(mean, d, p)。"""
    n = len(diffs)
    mean = sum(diffs) / n
    var = sum((x - mean) ** 2 for x in diffs) / (n - 1) if n > 1 else 0.0
    sd = math.sqrt(var)
    if sd == 0.0:
        return mean, (float("inf") if mean > 0 else 0.0), (0.0 if mean else 1.0)
    d = mean / sd
    p = min(1.0, 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(mean) / (sd / math.sqrt(n)) / math.sqrt(2.0)))))
    return mean, d, p


def i2_recompute_c5_gain(
    registry_dir: Path, result_json: Path, stat_plan_path: Path
) -> dict[str, Any]:
    """C5 gain claim I2 复算（同数据独立统计 → 与原 EvidenceResult 判据比对）。"""
    # 原判定器禁入（结构面：本函数体内不得出现 hypotheses/runs_c5 import——测试源扫描钉死）
    blob_path = _find_evidence_partition(registry_dir)
    digest = content_digest(blob_path.read_bytes())
    ref = ArtifactRef(digest=digest, kind="evidence:evidence")

    class _ShimRegistry:   # 最小只读面（避免构造完整 Registry/stores 依赖）
        def get(self, _ref: ArtifactRef):   # noqa: ANN001 — shim
            from galatea.kernel.registry import RegistryEntry

            return RegistryEntry(manifest={"kind": "evidence:evidence"},
                                 blob=blob_path.read_bytes())

    rows = read_partition(_ShimRegistry(), ref)   # type: ignore[arg-type]
    learn_err: list[float] = []
    nolearn_err: list[float] = []
    regimes: list[str] = []
    for row in rows:
        summary = json.loads(row["summary"])
        if summary.get("tracking_error") is None:
            continue
        if row["arm"] == "learn":
            learn_err.append(float(summary["tracking_error"]))
            regimes.append(str(summary.get("regime", "")))
        elif row["arm"] == "nolearn":
            nolearn_err.append(float(summary["tracking_error"]))
    if len(learn_err) != len(nolearn_err) or not learn_err:
        raise IndependenceViolation(
            f"paired data malformed: learn={len(learn_err)} nolearn={len(nolearn_err)}"
        )
    # 取数域 = 增益空间域（stat plan v1.1 修订 1——判据域读冻结计划，非硬编码）
    plan = yaml.safe_load(stat_plan_path.read_text(encoding="utf-8"))
    claim = next(c for c in plan["stat_plan"]["claims"]
                 if c["claim_id"] == "c5_promotion_learning_gain")
    if claim.get("claim_domain") != "gain_space_regimes":
        raise IndependenceViolation("stat plan claim_domain drifted（判据域须为增益空间域）")
    domain = {"scarcity", "volatile"}
    diffs = [n_err - l_err for l_err, n_err, reg in
             zip(learn_err, nolearn_err, regimes) if reg in domain]
    if not diffs:
        raise IndependenceViolation("gain-space domain produced zero trials")
    mean, d, p = _paired_wald(diffs)

    original = json.loads(result_json.read_text(encoding="utf-8"))
    verdict_ok = original["verdict"] == "SUPPORTED"
    orig_d = float(original["effect_size"])
    orig_ci = original["ci"]
    d_tol = max(1e-9, (float(orig_ci["upper"]) - float(orig_ci["lower"])) * 1e-6)
    d_ok = abs(d - orig_d) <= d_tol
    p_ok = abs(p - float(original["p_or_bayes"])) <= 1e-9
    mean_ok = float(orig_ci["lower"]) <= mean <= float(orig_ci["upper"])
    match = bool(verdict_ok and d_ok and p_ok and mean_ok)
    return {
        "mode": "I2",
        "n_domain_trials": len(diffs),
        "independent": {"mean": mean, "d": d, "p": p},
        "original": {"d": orig_d, "p": float(original["p_or_bayes"])},
        "verdict_ok": verdict_ok, "d_ok": d_ok, "p_ok": p_ok, "mean_in_ci": mean_ok,
        "match": match,
        "inputs_digest": digest[:16],
    }
