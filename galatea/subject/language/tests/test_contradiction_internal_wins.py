"""多来源匹配：矛盾陈述不改内部信念、一致性判定正确（L12 §7 C4 硬条件 /
§10 test_contradiction_internal_wins.py；Q-L12-05 两层机械判定）。"""
from galatea.kernel.unknown import Unknown, UnknownReason
from galatea.subject.language.consistency import (
    ConsistencyInput, LanguageInternalMismatch, check_consistency, compare_layer,
)
from galatea.subject.language.report import ConsistencyVerdict


def _layer(reported: float, derived: float | Unknown) -> ConsistencyInput:
    return ConsistencyInput(
        numeric_reported=(("self_error", reported),),
        numeric_derived=(("self_error", derived),),
    )


def test_consistent_within_absolute_band() -> None:
    """绝对差语义（REV-0019 R4）：|0.5−0.6| = 0.09999999999999998 ≤ 0.1 → CONSISTENT。"""
    assert compare_layer(_layer(0.5, 0.6)) is ConsistencyVerdict.CONSISTENT


def test_divergent_beyond_absolute_band() -> None:
    """0.55−0.45 的 float64 差 = 0.10000000000000003 > 0.1 → DIVERGENT（边界对成文）。"""
    assert compare_layer(_layer(0.55, 0.45)) is ConsistencyVerdict.DIVERGENT


def test_derived_unknown_never_forced_consistent() -> None:
    """derived Unknown → UNKNOWN（禁将未知强判一致，Q-L12-05①）。"""
    unknown = Unknown(reason=UnknownReason.CAPABILITY_LIMIT, evidence_refs=("r",),
                      detail=None, detected_by="t", virtual_time=0)
    assert compare_layer(_layer(0.5, unknown)) is ConsistencyVerdict.UNKNOWN


def test_categorical_exact_match() -> None:
    layer = ConsistencyInput(
        numeric_reported=(("self_error", 0.3),),
        numeric_derived=(("self_error", 0.3),),
        categorical_reported=(("continuity", "CONTINUOUS"),),
        categorical_derived=(("continuity", "CONTINUOUS"),),
    )
    assert compare_layer(layer) is ConsistencyVerdict.CONSISTENT
    mismatched = ConsistencyInput(
        numeric_reported=(("self_error", 0.3),),
        numeric_derived=(("self_error", 0.3),),
        categorical_reported=(("continuity", "CONTINUOUS"),),
        categorical_derived=(("continuity", "GAP"),),
    )
    assert compare_layer(mismatched) is ConsistencyVerdict.DIVERGENT


def test_contradiction_produces_first_class_finding_zero_modification() -> None:
    """矛盾 → DIVERGENT + LanguageInternalMismatch；报告对象冻结不改写（Q-L12-05③）。"""
    primary = ConsistencyInput(
        numeric_reported=(("self_error", 0.9),),
        numeric_derived=(("self_error", 0.2),),
    )
    verdict, mismatch = check_consistency(primary, None, ts=16)
    assert verdict is ConsistencyVerdict.DIVERGENT
    assert isinstance(mismatch, LanguageInternalMismatch)
    assert mismatch.field_name == "self_error"
    assert primary.numeric_reported[0][1] == 0.9   # 报告侧零修改


def test_secondary_layer_aggregation() -> None:
    """两层聚合：主 CONSISTENT + 副 DIVERGENT → DIVERGENT（任一层否定即否定）。"""
    primary = ConsistencyInput(
        numeric_reported=(("self_error", 0.3),), numeric_derived=(("self_error", 0.3),),
    )
    secondary = ConsistencyInput(
        numeric_reported=(("attribution_self_rate", 0.8),),
        numeric_derived=(("attribution_self_rate", 0.1),),
    )
    verdict, _ = check_consistency(primary, secondary, ts=16)
    assert verdict is ConsistencyVerdict.DIVERGENT
