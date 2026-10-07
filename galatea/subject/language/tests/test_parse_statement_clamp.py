"""R-PARSE statement confidence clamp（Q-L12-06②：上界 0.5 = Q-L03-02 believe_threshold 锚）。"""
import pytest

from galatea.subject.c4profile import load_c4_action_social_profile
from galatea.subject.language.parse import parse_language_frame
from galatea.subject.language.ports import LanguagePlaneViolation
from galatea.subject.language.replay import ReplayStore
from galatea.subject.sensorium.ports import LanguageFeatures

PROFILE = load_c4_action_social_profile()


def _replay(output: str) -> ReplayStore:
    store = ReplayStore()
    store.record("R-PARSE", {"text": "there is food north", "requester": "exp"},
                 output, "fixture-recording")
    return store


def _frame() -> LanguageFeatures:
    return LanguageFeatures(statement_text="there is food north", requester="exp",
                            statement_level="EXTERNAL_STATEMENT")


def test_statement_confidence_clamped_with_trace() -> None:
    parsed = parse_language_frame(_frame(), "ev-1", _replay('{"type": "statement", "confidence": 0.9}'), PROFILE)
    assert parsed.confidence == 0.5       # clamp 上界
    assert parsed.clamped is True          # 越界留痕（Q-L12-06②）


def test_statement_at_cap_not_clamped() -> None:
    parsed = parse_language_frame(_frame(), "ev-1", _replay('{"type": "statement", "confidence": 0.5}'), PROFILE)
    assert parsed.confidence == 0.5
    assert parsed.clamped is False


def test_request_confidence_unaffected() -> None:
    """request/instruction 分型不受 0.5 上界限（Q-L12-06③ 分型面不受限）。"""
    parsed = parse_language_frame(_frame(), "ev-1", _replay('{"type": "request", "confidence": 0.9}'), PROFILE)
    assert parsed.kind == "request"
    assert parsed.confidence == 0.9
    assert parsed.clamped is False


def test_out_of_vocabulary_kind_rejected() -> None:
    with pytest.raises(LanguagePlaneViolation, match="vocabulary"):
        parse_language_frame(_frame(), "ev-1", _replay('{"type": "gossip", "confidence": 0.3}'), PROFILE)


def test_malformed_output_rejected_no_degradation() -> None:
    """schema 校验失败即拒，不降级自由文本入库（L12 §4.1 原文）。"""
    with pytest.raises(LanguagePlaneViolation, match="schema violation"):
        parse_language_frame(_frame(), "ev-1", _replay('not json at all'), PROFILE)
