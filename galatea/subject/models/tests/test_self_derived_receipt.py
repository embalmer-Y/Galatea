"""自我模型派生视图测试（L04 §7 self as derived 行：每字段有回执，否则 Unknown）。"""
import pytest

from galatea.subject.models.self_model import SelfModel
from galatea.subject.models.self_error import SelfPredictionErrorAccumulator
from galatea.subject.c1profile import load_c1_profile


def test_all_sourced_fields_have_receipts():
    model = SelfModel(lineage_ref="l00.lineage.R", run_id="R")
    view = model.update(
        cycle=64, checkpoint_ref="ckpt.64",
        source_priors=(("INTERO", 0.9),), source_prior_refs=("pb.EVENT.7.integrity_damage_event",),
        goals_view=(), self_error=None,
    )
    received = {name for name, _ in view.derivation_receipts}
    assert "continuity" in received
    assert "source_priors" in received
    assert "current_goals_view" in received
    # self_error 缺源 → Unknown（禁编造）
    from galatea.kernel.unknown import Unknown

    assert isinstance(view.self_prediction_error, Unknown)


def test_missing_receipt_rejected_mechanically():
    """无回执的非 Unknown 字段 = 构造即拒（机械保证"自我报告只是派生视图"）。"""
    from galatea.subject.models.self_model import (
        BoundaryConfidence,
        ContinuityState,
        SelfModelView,
    )

    with pytest.raises(ValueError, match="derivation receipt"):
        SelfModelView(
            view_id="smv.bad", cycle_id=1,
            continuity=ContinuityState(lineage_ref="l", checkpoint_ref="c", gaps=()),
            source_priors=(("INTERO", 0.5),),
            memory_perception_boundary=BoundaryConfidence(discriminable=True, basis="asserted"),
            current_goals_view=(),
            self_prediction_error=None,   # 非法类型（None 禁）——receipt 检查先触发
            derivation_receipts=(("continuity", ("l",)),),
        )


def test_source_priors_derived_from_judgements():
    """来源先验 = 观测判定统计（派生面）；零观测 → 整字段 Unknown（禁编造）。"""
    model = SelfModel(lineage_ref="l", run_id="R")
    view = model.update(cycle=1, checkpoint_ref="c", source_priors=None,
                        source_prior_refs=(), goals_view=None, self_error=None)
    from galatea.kernel.unknown import Unknown

    assert isinstance(view.source_priors, Unknown)


def test_ewma_matches_probe_spec():
    """EWMA 递推与 ADR-G-0013 探针规格同式（8 位舍入；手算复核）。"""
    profile = load_c1_profile()
    acc = SelfPredictionErrorAccumulator(profile)
    err = acc.update(0, energy=0.1, integrity=0.0, load=0.0,
                     orientation_change=False, capability_deviation=False)
    # 首值 s = v₀（8 位舍入）：首拍二阶差分 = 0.1 − (0−0) = 0.1
    dims = dict((d, f) for d, f, _ in err.dims)
    assert dims["energy_second_difference"] == round(0.1, 8)
    err2 = acc.update(4, energy=0.1, integrity=0.0, load=0.0,
                      orientation_change=False, capability_deviation=False)
    # 第二拍：delta = 0，二阶差分 = 0 − (0.1 − 0) = −0.1；EWMA = ¼(−0.1) + ¾(0.1) = 0.05
    dims2 = dict((d, f) for d, f, _ in err2.dims)
    assert dims2["energy_second_difference"] == 0.05


def test_ewma_divergence_fast_vs_slow():
    """变输入下双尺度分叉（探针规格的方向性：fast 跟随、slow 滞后）。"""
    profile = load_c1_profile()
    acc = SelfPredictionErrorAccumulator(profile)
    max_gap = 0.0
    for cycle in range(0, 512, 4):
        high = (cycle // 4) % 2 == 0
        err = acc.update(cycle, energy=1.0 if high else 0.0, integrity=0.0, load=0.0,
                         orientation_change=high, capability_deviation=False)
        fast = dict((d, f) for d, f, _ in err.dims)["orientation_change"]
        slow = dict((d, s) for d, _, s in err.dims)["orientation_change"]
        max_gap = max(max_gap, abs(fast - slow))
    assert max_gap > 0.3      # 方波输入 → 双尺度明确分叉（探针 0.09 vs 0.79 同型）
