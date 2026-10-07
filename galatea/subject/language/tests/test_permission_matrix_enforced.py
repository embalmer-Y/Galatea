"""权限矩阵强制（L12 §10 test_permission_matrix_enforced.py；Q-L12-02 双维粒度）。"""
import pytest

from galatea.subject.language.permission import check_write
from galatea.subject.language.ports import LanguageOutPort, UnauthorizedWrite
from galatea.subject.language.roles import RoleKind


def test_role_writes_its_own_port() -> None:
    check_write(RoleKind.R_PARSE, LanguageOutPort.PARSED_REQUEST, "TypedFields")
    check_write(RoleKind.R_REPORT, LanguageOutPort.SELF_REPORT, "SelfReport")
    check_write(RoleKind.R_SEEKHELP, LanguageOutPort.UTTERANCE, "Utterance")


def test_role_cannot_write_foreign_port() -> None:
    with pytest.raises(UnauthorizedWrite, match="parsed_request"):
        check_write(RoleKind.R_REPORT, LanguageOutPort.PARSED_REQUEST, "TypedFields")
    with pytest.raises(UnauthorizedWrite, match="other_model"):
        check_write(RoleKind.R_TRANSLATE, LanguageOutPort.OTHER_MODEL, "OtherModel")


def test_forbidden_targets_rejected_regardless_of_role() -> None:
    """禁写面恒优先（S0 级目标 = WORLD_TRUTH/OWNED_GOAL/CAPABILITY）。"""
    for target in ("WORLD_TRUTH", "OWNED_GOAL", "CAPABILITY", "EPISODIC_EXPERIENCE", "EVIDENCE"):
        with pytest.raises(UnauthorizedWrite, match=f"LLM_TO_{target}"):
            check_write(RoleKind.R_PARSE, target, "anything")  # type: ignore[arg-type]


def test_citation_roles_reject_free_text_content() -> None:
    """require_evidence_citation 角色禁自由文本内容类型（L12 §4.2）。"""
    for role in (RoleKind.R_SEEKHELP, RoleKind.R_NORMEXTRACT, RoleKind.R_CHECKCONSIST, RoleKind.R_TRANSLATE):
        with pytest.raises(UnauthorizedWrite, match="citation"):
            check_write(role, get_out_port(role), "FreeText")


def get_out_port(role: RoleKind) -> LanguageOutPort:
    from galatea.subject.language.roles import get_role
    return get_role(role).out_port
