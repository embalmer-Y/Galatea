"""workspace 测试装置（真实 c2_workspace.profile typed loader——测试与生产同源，INC-11）。"""
from pathlib import Path

import pytest

from galatea.subject.c2profile import C2WorkspaceParams, load_c2_workspace_profile

ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture(scope="module")
def ws_params() -> C2WorkspaceParams:
    return load_c2_workspace_profile(ROOT / "config/profiles/c2_workspace.profile.yaml")
