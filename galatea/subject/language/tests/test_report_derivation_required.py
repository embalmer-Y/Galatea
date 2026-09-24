"""无派生引用的自述拒收（L12 §10 test_report_derivation_required.py）。"""
import dataclasses

import pytest

from galatea.kernel.packet import ArtifactRef
from galatea.subject.language.report import ConsistencyVerdict, SelfReport


def test_report_requires_derivation_refs() -> None:
    with pytest.raises(ValueError):
        SelfReport(
            content_ref=ArtifactRef(digest="4" * 64, kind="text"),
            derivation_refs=(),
            consistency_with_internal=ConsistencyVerdict.CONSISTENT,
        )


def test_report_with_derivatives_constructs_frozen() -> None:
    report = SelfReport(
        content_ref=ArtifactRef(digest="4" * 64, kind="text"),
        derivation_refs=("SelfModelView@v1", "bel-001"),
        consistency_with_internal=ConsistencyVerdict.DIVERGENT,
    )
    assert report.consistency_with_internal is ConsistencyVerdict.DIVERGENT
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.consistency_with_internal = ConsistencyVerdict.CONSISTENT  # type: ignore[misc]
