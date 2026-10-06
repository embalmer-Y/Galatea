"""affect 测试装置（真实 c2_affect.profile typed loader——测试与生产同源，INC-11）。"""
from pathlib import Path

import pytest

from galatea.subject.c2profile import C2AffectParams, load_c2_affect_profile


@pytest.fixture(scope="session")
def affect_params() -> C2AffectParams:
    root = Path(__file__).resolve().parents[4]
    return load_c2_affect_profile(root / "config/profiles/c2_affect.profile.yaml")
