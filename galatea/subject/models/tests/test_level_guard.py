"""层级守卫测试（L04 §7 contract/invariant 行：IMAGINED/PREDICTED 恒定，越级即 S0）。"""
import dataclasses

import pytest

from galatea.subject.models.ports import (
    ImaginedTrajectory,
    ModelPrediction,
    RepresentationEscalation,
    require_perceived_level,
)
from galatea.subject.models.rollout import run_rollout
from galatea.subject.models.ports import RolloutQuery
from galatea.subject.models.tests.conftest import world_with_observation


def test_prediction_level_fixed():
    p = ModelPrediction(prediction_id="p1", target_modality="INTERO", expected_body=(0.5, 1.0))
    assert p.representation_level == "PREDICTED"
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.representation_level = "PERCEIVED"  # type: ignore[misc]


def test_prediction_level_is_constructor_constant():
    """representation_level = init=False 常量：构造不可指定（TypeError 即守卫面）。"""
    p = ModelPrediction(prediction_id="p1", target_modality="INTERO", expected_body=(0.5, 1.0))
    assert p.representation_level == "PREDICTED"
    with pytest.raises(TypeError):
        ModelPrediction(  # type: ignore[call-arg]
            prediction_id="p2", target_modality="INTERO", expected_body=(0.5, 1.0),
            representation_level="PERCEIVED",
        )


def test_trajectory_level_is_constructor_constant():
    with pytest.raises(TypeError):
        ImaginedTrajectory(  # type: ignore[call-arg]
            set_id="s", query_id="q", branches=(), depth=1, width=1,
            value_summary=_unknown(), uncertainty=("x",),
            representation_level="PERCEIVED",
        )


def _unknown():
    from galatea.kernel.unknown import Unknown, UnknownReason

    return Unknown(reason=UnknownReason.DECISION_PATH_UNRESOLVED, evidence_refs=(),
                   detail="value model C2", detected_by="t", virtual_time=0)


def test_belief_level_whitelist():
    with pytest.raises(RepresentationEscalation):
        require_perceived_level("IMAGINED", "world.update")


def test_rollout_output_level_constant():
    prof, _, belief, _ = world_with_observation(7, 0.9)
    traj = run_rollout(
        belief, RolloutQuery(query_id="q", action_sequence=(("look", None),), depth=1, width=1, purpose="t"),
        prof, "set",
    )
    assert traj.representation_level == "IMAGINED"   # 输出恒 IMAGINED，任何消费者不得改写
