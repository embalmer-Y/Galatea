"""无引用量化主张拒收（L12 §10 test_uncited_claim_rejected.py；L12 §4.4 原文）。"""
import pytest

from galatea.subject.language.utter import Utterance, UncitedClaimRejected, translate_utterance
from galatea.subject.language.replay import ReplayStore

REPLAY = ReplayStore()


def test_quantitative_claim_without_citation_rejected() -> None:
    with pytest.raises(UncitedClaimRejected, match="quantitative"):
        Utterance(text="resource level is 0.73 now", cited_evidence=(), role="R-TRANSLATE")


def test_cited_quantitative_claim_accepted() -> None:
    utt = Utterance(text="resource level is 0.73 now", cited_evidence=("bel-1",), role="R-TRANSLATE")
    assert utt.cited_evidence == ("bel-1",)


def test_non_numeric_text_without_citation_accepted() -> None:
    Utterance(text="the north path seems blocked", cited_evidence=(), role="R-CLARIFY")


def test_translate_requires_citation_at_construction() -> None:
    with pytest.raises(UncitedClaimRejected, match="must_cite_evidence"):
        translate_utterance({"target": "help"}, (), REPLAY)
