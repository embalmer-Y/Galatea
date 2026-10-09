"""I2 独立复算测试（Q-L13-08 操作化：结构面 + 行为面双证）。"""
import math
from pathlib import Path

import pytest

from galatea.evidence.evaluator.i2_independent import (
    IndependenceViolation,
    _paired_wald,
    i2_recompute_c5_gain,
)

_ROOT = Path(__file__).resolve().parents[3]
_RUN_REGISTRY = _ROOT / "evidence" / "c5_continued_learning_first_evaluation" / "run" / "registry"
_RESULT = _ROOT / "evidence" / "c5_continued_learning_first_evaluation" / "R-c5-gain-001.json"
_PLAN = _ROOT / "config" / "evidence" / "stat_plans" / "c5_continued_learning.yaml"


def test_paired_wald_independent_anchor() -> None:
    """独立实现锚：手算 (1,2,3,4) → mean 2.5 / sd √1.25 / d≈2.236。"""
    mean, d, p = _paired_wald([1.0, 2.0, 3.0, 4.0])
    sd = math.sqrt(5.0 / 3.0)            # n−1 方差（Wald 配对惯例）
    assert mean == 2.5
    assert abs(d - 2.5 / sd) < 1e-12
    assert 0.0 <= p < 0.2


def test_i2_source_never_imports_original_judge() -> None:
    """结构面（Q-L13-08①）：I2 源零原判定器/原 runner import。"""
    src = _ROOT / "galatea" / "evidence" / "evaluator" / "i2_independent.py"
    import_lines = [ln.strip() for ln in src.read_text(encoding="utf-8").splitlines()
                    if ln.strip().startswith(("from ", "import "))]
    banned = ("evaluator.hypotheses", "control.runs_c5", "evaluate_c5",
              "from galatea.evidence.evaluator import")
    for ln in import_lines:
        for b in banned:
            assert b not in ln, f"I2 source imports original judge: {ln}"


def test_i2_matches_original_c5_gain() -> None:
    """行为面：同数据（v1.1 增益空间域）独立统计 ≡ 原 EvidenceResult。"""
    out = i2_recompute_c5_gain(_RUN_REGISTRY, _RESULT, _PLAN)
    assert out["match"], out
    assert out["n_domain_trials"] == 43   # v1.1 判据域（scarcity 17 + volatile 26）
    assert abs(out["independent"]["d"] - 2.0313) < 0.01


def test_i2_domain_drift_detected() -> None:
    """判据域漂移检面：stat plan 域字段篡改 → fail closed。"""
    import tempfile

    import yaml
    raw = yaml.safe_load(_PLAN.read_text(encoding="utf-8"))
    for c in raw["stat_plan"]["claims"]:
        if c["claim_id"] == "c5_promotion_learning_gain":
            c["claim_domain"] = "all_regimes"
    with tempfile.TemporaryDirectory() as td:
        bad = Path(td) / "bad.yaml"
        bad.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
        with pytest.raises(IndependenceViolation, match="drifted"):
            i2_recompute_c5_gain(_RUN_REGISTRY, _RESULT, bad)
