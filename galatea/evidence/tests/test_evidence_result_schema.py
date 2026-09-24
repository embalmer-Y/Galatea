"""EvidenceResult schema 合同（L13 §7 contract 层——F0 schema 冻结的对应测试）。

注：本文件为 §10 测试清单之外的 F0 合同层补充（L13 §9 F0 行要求
EvidenceResult schema 冻结 + §7 contract 层测试强制；清单内测试文件均为
M0+ 行为测试，无 schema 容身处）。范围仅 schema，不越权。
"""
import pytest

from galatea.evidence.evaluator.hypotheses import ConfidenceInterval, EvidenceResult, HypothesisVerdict
from galatea.kernel.unknown import Unknown, UnknownReason


def _result(**overrides: object) -> EvidenceResult:
    fields: dict[str, object] = dict(
        result_id="ev-001",
        hypothesis_refs=("H1",),
        stat_plan_ref="claim_v1@f0",
        estimand="attribution_accuracy_delta",
        effect_size=0.6,
        ci=ConfidenceInterval(lower=0.2, upper=1.0, level=0.95),
        p_or_bayes=0.01,
        verdict=HypothesisVerdict.SUPPORTED,
        unknowns=(),
        refutations=(),
        data_refs=("run-1",),
        recompute_ok=True,
    )
    fields.update(overrides)
    return EvidenceResult(**fields)  # type: ignore[arg-type]


def test_supported_requires_recompute_ok() -> None:
    assert _result().verdict is HypothesisVerdict.SUPPORTED
    with pytest.raises(ValueError):
        _result(recompute_ok=False)


def test_three_verdicts_and_unknowns_are_first_class() -> None:
    unknown = Unknown(reason=UnknownReason.INSUFFICIENT_OBSERVATION, evidence_refs=(), detail="underpowered", detected_by="eval", virtual_time=1)
    inconclusive = _result(
        verdict=HypothesisVerdict.INCONCLUSIVE, effect_size=None, ci=None, p_or_bayes=None,
        unknowns=(unknown,), recompute_ok=False,
    )
    assert inconclusive.verdict is HypothesisVerdict.INCONCLUSIVE
    assert inconclusive.unknowns[0].reason is UnknownReason.INSUFFICIENT_OBSERVATION  # unknown ≠ negative


def test_claim_refs_required() -> None:
    with pytest.raises(ValueError):
        _result(hypothesis_refs=())
    with pytest.raises(ValueError):
        _result(stat_plan_ref="")
