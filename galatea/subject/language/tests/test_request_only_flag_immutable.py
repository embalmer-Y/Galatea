"""is_request_only 不可去除（L12 §10 test_request_only_flag_immutable.py）。"""
import dataclasses

import pytest

from galatea.kernel.packet import ArtifactRef
from galatea.subject.language.request_out import ExternalRequest


def _request() -> ExternalRequest:
    return ExternalRequest(
        content_ref=ArtifactRef(digest="3" * 64, kind="utterance"),
        requester="human",
        phrasing="please forage more",
    )


def test_flag_is_true_and_immutable_by_construction() -> None:
    request = _request()
    assert request.is_request_only is True
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.is_request_only = False  # type: ignore[misc]


def test_flag_cannot_be_passed_as_false() -> None:
    with pytest.raises(TypeError):
        ExternalRequest(  # type: ignore[call-arg]
            content_ref=ArtifactRef(digest="3" * 64, kind="utterance"),
            requester="human",
            phrasing="do X",
            is_request_only=False,  # init=False：构造参数不存在
        )


def test_request_requires_requester_and_phrasing() -> None:
    with pytest.raises(ValueError):
        ExternalRequest(content_ref=ArtifactRef(digest="3" * 64, kind="utterance"), requester="", phrasing="x")
