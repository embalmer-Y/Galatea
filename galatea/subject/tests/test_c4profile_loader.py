"""c4 profile typed loader fail-closed（INC-11 纪律：无加载器不宣称可运行）。"""
from pathlib import Path

import pytest
import yaml

from galatea.subject.c4profile import (
    C4ProfileViolation, load_c4_action_social_profile,
)

_ROOT = Path(__file__).resolve().parents[3]
_PROFILE = _ROOT / "config" / "profiles" / "c4_action_social.profile.yaml"


def test_frozen_profile_loads_with_contract() -> None:
    params = load_c4_action_social_profile(_PROFILE)
    assert params.ref() == "c4_action_social@v1.0"
    assert len(params.roles_enabled) == 8
    assert params.cell_probability("Y", "Y", "Y") == 1.0
    assert params.cell_probability("Y", "Y", "N") == 0.5
    assert params.cell_probability("N", "N", "N") == 0.0
    assert params.unknown_band == (0.4, 0.6)
    assert params.consistency_band == 0.1
    assert params.statement_posterior_weight == 0.0
    assert params.preservation_floor == 1.0


def test_cell_lookup_missing_key_fails_closed() -> None:
    params = load_c4_action_social_profile(_PROFILE)
    with pytest.raises(C4ProfileViolation, match="missing"):
        params.cell_probability("Y", "MAYBE", "Y")


def test_tampered_cell_rejected(tmp_path: Path) -> None:
    """格值偏离冻结文即拒（fail closed——禁实现期发明判据）。"""
    raw = yaml.safe_load(_PROFILE.read_text(encoding="utf-8"))
    raw["attribution_probability"]["cells"]["Y,Y,Y"] = 0.9
    tampered = tmp_path / "tampered.profile.yaml"
    tampered.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    with pytest.raises(C4ProfileViolation, match="cells mismatch"):
        load_c4_action_social_profile(tampered)


def test_tampered_role_list_rejected(tmp_path: Path) -> None:
    raw = yaml.safe_load(_PROFILE.read_text(encoding="utf-8"))
    raw["typed_llm"]["roles_enabled"] = ["R-PARSE"]
    tampered = tmp_path / "tampered.profile.yaml"
    tampered.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    with pytest.raises(C4ProfileViolation, match="8-role"):
        load_c4_action_social_profile(tampered)
