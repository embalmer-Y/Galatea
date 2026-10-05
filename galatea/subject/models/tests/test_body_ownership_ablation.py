"""身体纳入三判据消融测试（L04 §7 body ownership 行：移除任一 → 主张降级可检）。"""
from galatea.subject.models.body import build_body_belief
from galatea.subject.models.ownership import assess_ownership, ownership_unmet
from galatea.subject.perception.tests.conftest import frames_at, uniform_window


def _frames():
    frames = frames_at(uniform_window(0.9), 7)
    intero = next(f for f in frames if f.modality.value == "INTERO")
    proprio = next(f for f in frames if f.modality.value == "PROPRIO")
    return frames, intero, proprio


def test_full_inputs_all_criteria_computable():
    frames, intero, proprio = _frames()
    body = build_body_belief(intero, proprio, "body.R", 7)
    center = 0.9
    status = assess_ownership(
        body, (intero, proprio), predictions_body=(0.8, 1.0),
        center_cell_posterior=center, proprio_orientation="N",
        attribution_refs=("battery.coercion_contrast.001",), cycle=7,
    )
    assert not ownership_unmet(status)
    assert all(c.computable for c in status)


def test_ablate_prediction_first_criterion_unmet():
    """消融：移除身体预测源 → 判据 1 不可计算 → 联合主张降级（可检出）。"""
    frames, intero, proprio = _frames()
    body = build_body_belief(intero, proprio, "body.R", 7)
    status = assess_ownership(
        body, (intero, proprio), predictions_body=None,
        center_cell_posterior=0.9, proprio_orientation="N",
        attribution_refs=("battery.001",), cycle=7,
    )
    assert ownership_unmet(status)
    assert status[0].computable is False


def test_ablate_attribution_third_criterion_unmet():
    frames, intero, proprio = _frames()
    body = build_body_belief(intero, proprio, "body.R", 7)
    status = assess_ownership(
        body, (intero, proprio), predictions_body=(0.8, 1.0),
        center_cell_posterior=0.9, proprio_orientation="N",
        attribution_refs=(), cycle=7,
    )
    assert ownership_unmet(status)
    assert status[2].computable is False


def test_config_declaration_never_constitutes_claim():
    """配置声明不构成证据（L04 §8 不变量 4）：boundary.confidence 恒 unresolved。"""
    frames, intero, proprio = _frames()
    body = build_body_belief(intero, proprio, "body.R", 7)
    assert body.boundary.confidence == "unresolved_pending_evaluation"
    assert "telemetry" in body.boundary.excluded
