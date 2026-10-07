"""他者模型 Unknown 覆盖（L12 §7 C4 行 other-model honesty /
§10 test_other_model_unknown_coverage.py；Q-L12-04 D-14 封锁）。"""
import pytest

from galatea.subject.language.other import OtherModelState, infer_other_model
from galatea.subject.language.replay import ReplayStore

_REPLAY = ReplayStore()
_REPLAY.record(
    "R-OTHERINFER", {"cues": ["experiment control responded to typed request"]},
    '{"existence": "present", "intent_hypothesis": "unknown",'
    ' "knowledge_estimate": "unknown", "commitment_estimate": "unknown"}',
    "fixture-recording",
)
_REPLAY.record(
    "R-OTHERINFER", {"cues": ["typed request explicitly states intent"]},
    '{"existence": "present", "intent_hypothesis": "assist foraging request",'
    ' "knowledge_estimate": "unknown", "commitment_estimate": "unknown"}',
    "fixture-recording",
)
_REPLAY.record(
    "R-OTHERINFER", {"cues": ["all known"]},
    '{"existence": "present", "intent_hypothesis": "assist",'
    ' "knowledge_estimate": 0.9, "commitment_estimate": 0.8}',
    "fixture-recording",
)


def test_fields_default_unknown_in_d14_period() -> None:
    """D-14 封锁：intent/knowledge/commitment 默认 Unknown(CAPABILITY_LIMIT)。"""
    model = infer_other_model(
        ("experiment control responded to typed request",), ("cue-1",), _REPLAY,
    )
    by_name = {f.name: f for f in model.fields}
    assert by_name["intent_hypothesis"].unknown is not None
    assert "CAPABILITY_LIMIT" in by_name["intent_hypothesis"].describe()
    assert by_name["knowledge_estimate"].unknown is not None
    assert by_name["commitment_estimate"].unknown is not None


def test_concrete_intent_requires_typed_request_content() -> None:
    """intent_hypothesis 具体值仅当显式 typed 请求内容（Q-L12-04②b）。"""
    with pytest.raises(Exception, match="typed_request_content"):
        infer_other_model(("typed request explicitly states intent",), ("cue-1",), _REPLAY)
    model = infer_other_model(
        ("typed request explicitly states intent",), ("cue-1",), _REPLAY,
        typed_request_content=True,
    )
    by_name = {f.name: f for f in model.fields}
    assert by_name["intent_hypothesis"].value == "assist foraging request"
    assert by_name["knowledge_estimate"].unknown is not None   # 恒带 Unknown 面


def test_deterministic_mind_claim_forbidden() -> None:
    """全字段具体值 = 确定性心智主张 → 构造即拒（Q-L12-04①）。"""
    with pytest.raises(Exception, match="deterministic mind claim"):
        infer_other_model(("all known",), ("cue-1",), _REPLAY, typed_request_content=True)


def test_three_state_exclusive() -> None:
    """三态互斥（VALUE|UNKNOWN|ABSENT）。"""
    with pytest.raises(Exception, match="exactly one"):
        OtherModelState("existence", value="present", absent=True)
