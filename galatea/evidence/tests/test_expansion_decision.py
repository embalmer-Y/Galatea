"""ExpansionDecision 签发纪律与门规则（L13 §2.2/HLD §10.2–10.3；Q-L13-03）。

断言：双签发者（仅消费根结果 digest，非对象）；ALLOW 前置 = REV 引用 + 无约束 +
绑定物齐备；HOLD/REWORK 机械映射；记录 digest 确定性。
"""
import pytest

from galatea.evidence.evaluator.hypotheses import ConfidenceInterval, EvidenceResult, HypothesisVerdict
from galatea.evidence.gate.expansion import (
    ExpansionDecision,
    ExpansionOutcome,
    StatPlanRefMissing,
    decide_from_root,
)


def _root(verdict: HypothesisVerdict) -> EvidenceResult:
    return EvidenceResult(
        result_id="R-root", hypothesis_refs=("r0_root_causal_auditability",),
        stat_plan_ref="config/evidence/stat_plans/r0_root.yaml@v1.0", estimand="e",
        effect_size=0.98 if verdict is HypothesisVerdict.SUPPORTED else None,
        ci=ConfidenceInterval(0.95, 1.0, 0.95) if verdict is HypothesisVerdict.SUPPORTED else None,
        p_or_bayes=1e-19 if verdict is HypothesisVerdict.SUPPORTED else None,
        verdict=verdict, unknowns=(), refutations=(), data_refs=(), recompute_ok=True,
    )


def test_gate_rule_mechanical_mapping() -> None:
    assert decide_from_root(_root(HypothesisVerdict.SUPPORTED)) is ExpansionOutcome.ALLOW_NEXT_STAGE
    assert (
        decide_from_root(_root(HypothesisVerdict.SUPPORTED), constraints=("C0 profile 待评审",))
        is ExpansionOutcome.HOLD
    )
    assert decide_from_root(_root(HypothesisVerdict.INCONCLUSIVE)) is ExpansionOutcome.HOLD
    assert decide_from_root(_root(HypothesisVerdict.REFUTED)) is ExpansionOutcome.REWORK


def _decision(decision: ExpansionOutcome, **overrides: object) -> ExpansionDecision:
    values: dict[str, object] = {
        "decision_id": "EXP-R0-001", "stage": "R0", "decision": decision,
        "root_evidence_digest": "ab" * 32,
        "basis_evidence_ids": ("R-root", "REV-0009"),
        "constraints": (), "bound_digests": (("r0_root_stat_plan", "cd" * 32),),
        "rev_review_ref": "", "independent_of": "evidence.evaluator.hypotheses",
        "reason": "unit",
    }
    values.update(overrides)
    return ExpansionDecision(**values)  # type: ignore[arg-type]


def test_allow_requires_rev_ref_and_unconstrained() -> None:
    with pytest.raises(StatPlanRefMissing):
        _decision(ExpansionOutcome.ALLOW_NEXT_STAGE)                       # 无 REV 引用
    with pytest.raises(StatPlanRefMissing):
        _decision(
            ExpansionOutcome.ALLOW_NEXT_STAGE, rev_review_ref="REV-0010",
            constraints=("C0 profile 未评审",),
        )
    allowed = _decision(ExpansionOutcome.ALLOW_NEXT_STAGE, rev_review_ref="REV-0010")
    assert allowed.digest


def test_binding_digests_required() -> None:
    with pytest.raises(StatPlanRefMissing):
        _decision(ExpansionOutcome.HOLD, bound_digests=())
    with pytest.raises(StatPlanRefMissing):
        _decision(ExpansionOutcome.HOLD, root_evidence_digest="")


def test_decision_record_deterministic_digest() -> None:
    a = _decision(ExpansionOutcome.HOLD, reason="R0 INCONCLUSIVE")
    b = _decision(ExpansionOutcome.HOLD, reason="R0 INCONCLUSIVE")
    assert a.digest == b.digest
    changed = _decision(ExpansionOutcome.HOLD, reason="R0 SUPPORTED with constraints")
    assert changed.digest != a.digest


def test_collect_binding_digests_covers_all_config_contracts() -> None:
    """绑定物收集器（REV-0010 R4 计算域成文）：config/** 全量、relpath 排序、文本 digest。"""
    from pathlib import Path as _P

    from galatea.evidence.gate.expansion import collect_binding_digests
    from galatea.kernel.digest import content_digest as _cd

    root = _P(__file__).resolve().parents[3]
    digests = collect_binding_digests(root)
    files = sorted(p.relative_to(root).as_posix() for p in (root / "config").rglob("*.y*ml"))
    assert [name for name, _ in digests] == files
    by_name = dict(digests)
    sample = root / files[0]
    assert by_name[files[0]] == _cd(sample.read_text(encoding="utf-8"))
    assert len(digests) >= 17   # R0 期 17 份（含 r0_root.yaml）
