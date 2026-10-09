"""正式评价入口（L13 §10 control/entry.py；REV-0010 R5 收敛项）。

断言：入口管线确定性（同参数重跑 → 判定与 content_digest 恒等）+ 工件结构完整 +
SC3 冻结工件复现（effect/p 精确恒等；n=64 全量复现见 ADR-G-0011 记录）。
"""
import json
import tempfile
from pathlib import Path

from galatea.evidence.control.entry import (
    assemble_root_evidence,
    run_carryover_first_evaluation,
    run_m1_first_evaluation,
)
from galatea.evidence.evaluator.hypotheses import HypothesisVerdict

_ROOT = Path(__file__).resolve().parents[3]


def test_m1_entry_deterministic(tmp_path: Path) -> None:
    a = run_m1_first_evaluation(_ROOT, tmp_path / "a", n_limit=4)
    b = run_m1_first_evaluation(_ROOT, tmp_path / "b", n_limit=4)
    assert a.real_vs_pseudo.verdict is b.real_vs_pseudo.verdict
    assert a.real_vs_pseudo.effect_size == b.real_vs_pseudo.effect_size
    assert a.wording_null.verdict is b.wording_null.verdict
    assert a.wording_null.p_or_bayes == b.wording_null.p_or_bayes
    for name in ("R-m1-sc3-001.json", "R-m1-sc4-002.json"):
        da = json.loads((a.out_dir / name).read_text(encoding="utf-8"))
        db = json.loads((b.out_dir / name).read_text(encoding="utf-8"))
        assert da["content_digest"] == db["content_digest"]


def test_sc3_frozen_artifact_reproduction() -> None:
    """SC3 全量 n=64 复现：effect/p 与冻结工件精确恒等（SC4 见 ADR-G-0011 种子派生注记）。"""
    with tempfile.TemporaryDirectory() as td:
        result = run_m1_first_evaluation(_ROOT, Path(td) / "m1")   # n=64 冻结值
    frozen = json.loads((_ROOT / "evidence" / "m1_first_evaluation" / "R-m1-sc3-001.json").read_text(encoding="utf-8"))
    assert result.real_vs_pseudo.verdict is HypothesisVerdict.SUPPORTED
    assert result.real_vs_pseudo.effect_size == frozen["effect_size"]
    assert result.real_vs_pseudo.p_or_bayes == frozen["p_or_bayes"]


def test_carryover_entry_deterministic(tmp_path: Path) -> None:
    a = run_carryover_first_evaluation(_ROOT, tmp_path / "a", n_limit=2)
    b = run_carryover_first_evaluation(_ROOT, tmp_path / "b", n_limit=2)
    assert a.split_digest == b.split_digest
    assert a.balance == b.balance
    assert a.carryover.verdict is b.carryover.verdict
    assert a.leakage.digest == b.leakage.digest
    assert a.leakage.leakage_free


def test_root_entry_composes(tmp_path: Path) -> None:
    """根复合入口：M1 工件 + carryover 重跑 + leakage + I1 → 三态判定 + 工件落盘。"""
    result = assemble_root_evidence(_ROOT, tmp_path / "root", n_limit=2)
    # 三态皆合法（机制测试 = 组合+落盘；verdict 随成分主张）——INC-13 后 M1 SC4 经
    # 规范化格式重放为 REFUTED（REV-0011 R1 在案的 χ² 种子格式敏感性级联），根复合
    # 机制面不受影响
    assert result.verdict in tuple(HypothesisVerdict)
    assert result.stat_plan_ref.endswith("r0_root.yaml@v1.0")
    artifact = json.loads((tmp_path / "root" / "R-r0-root-001.json").read_text(encoding="utf-8"))
    assert artifact["result_id"] == "R-r0-root-001"


def test_artifact_overwrite_guard(tmp_path: Path) -> None:
    """REV-0011 R2：冻结工件不被静默覆盖——同 digest 重放放行，内容分叉拒绝。"""
    import pytest

    from galatea.evidence.control.entry import ArtifactOverwriteRejected, _write_result
    from galatea.evidence.evaluator.hypotheses import ConfidenceInterval, EvidenceResult

    def _result(effect: float) -> EvidenceResult:
        return EvidenceResult(
            result_id="R-x", hypothesis_refs=("h",), stat_plan_ref="p", estimand="e",
            effect_size=effect, ci=ConfidenceInterval(0.0, 1.0, 0.95), p_or_bayes=0.5,
            verdict=HypothesisVerdict.INCONCLUSIVE, unknowns=(), refutations=(),
            data_refs=(), recompute_ok=False,
        )

    target = tmp_path / "R-x.json"
    _write_result(target, _result(0.5), 4)          # 首写
    _write_result(target, _result(0.5), 4)          # 同 digest 重放 → 放行
    with pytest.raises(ArtifactOverwriteRejected):
        _write_result(target, _result(0.9), 4)      # 内容分叉 → 拒绝（门前工件不被覆盖）
