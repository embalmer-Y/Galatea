"""四类授权台账测试（Q-L10-06 信封 12 字段/append-only 撤销/freshness fail-closed/批准者根）。"""
import pytest

from galatea.evidence.physio.authz import (
    AuthzEnvelope,
    AuthorizationLedger,
    LedgerViolation,
)


def _envelope(authz_id: str = "dep-1", authz_class: str = "deployment_authorization",
              version: int = 1, chain: str = "root", granted_at: int = 0,
              period: int = 0, approver: str = "owner_2026_10_10") -> AuthzEnvelope:
    return AuthzEnvelope(
        authz_id=authz_id, authz_class=authz_class, version=version,
        target_ref="host:192.168.2.91", granted_scope="p1_passive",
        granted_at_cycle=granted_at, valid_period_cycles=period,
        approver_ref=approver, auth_chain_digest=chain,
        revoke_path="owner_message", reauth_path="new_version_envelope",
        monitoring_binding="manifest",
    )


def test_issue_requires_frozen_approver_root() -> None:
    ledger = AuthorizationLedger(approver_roots=frozenset({"owner_2026_10_10"}))
    with pytest.raises(LedgerViolation, match="not in frozen root"):
        ledger.issue(_envelope(approver="self_granted"))      # 主体/网关不可任批准者
    ledger.issue(_envelope())
    assert ledger.freshness("dep-1", 100).verdict == "VALID"


def test_first_issue_must_be_v1_root_chain() -> None:
    ledger = AuthorizationLedger(approver_roots=frozenset({"owner_2026_10_10"}))
    with pytest.raises(LedgerViolation, match="version=1"):
        ledger.issue(_envelope(version=2, chain="root"))
    with pytest.raises(LedgerViolation, match="chain"):
        ledger.issue(_envelope(version=1, chain="dep-0"))


def test_reissue_version_chain_no_auto_renewal() -> None:
    ledger = AuthorizationLedger(approver_roots=frozenset({"owner_2026_10_10"}))
    ledger.issue(_envelope())
    with pytest.raises(LedgerViolation, match="bump version"):
        ledger.issue(_envelope(version=1, chain="whatever"))   # 同版重发禁
    with pytest.raises(LedgerViolation, match="chain to prior"):
        ledger.issue(_envelope(version=2, chain="root"))       # 重授权须链前版
    ledger.issue(_envelope(version=2, chain="chained:dep-1:v1"))
    assert ledger.freshness("dep-1", 5).verdict == "VALID"


def test_revocation_append_only_and_freshness() -> None:
    ledger = AuthorizationLedger(approver_roots=frozenset({"owner_2026_10_10"}))
    ledger.issue(_envelope())
    ledger.revoke("dep-1", 10, "owner_message")
    assert ledger.freshness("dep-1", 9).verdict == "VALID"      # 撤销不追溯
    assert ledger.freshness("dep-1", 10).verdict == "REVOKED"
    assert ledger.freshness("dep-1", 99).verdict == "REVOKED"
    with pytest.raises(LedgerViolation, match="append-only"):
        ledger.revoke("dep-1", 11, "again")                     # 一次撤销
    with pytest.raises(LedgerViolation, match="unknown"):
        ledger.revoke("ghost", 1, "x")
    assert len(ledger.revocations()) == 1


def test_stale_valid_period_fail_closed() -> None:
    ledger = AuthorizationLedger(approver_roots=frozenset({"owner_2026_10_10"}))
    ledger.issue(_envelope(granted_at=0, period=64))
    assert ledger.freshness("dep-1", 63).verdict == "VALID"
    assert ledger.freshness("dep-1", 64).verdict == "STALE"     # gateway #6 fail closed
    assert ledger.freshness("unknown", 1).verdict == "UNKNOWN_AUTHZ"


def test_unknown_class_rejected() -> None:
    ledger = AuthorizationLedger(approver_roots=frozenset({"owner_2026_10_10"}))
    with pytest.raises(LedgerViolation, match="authz class"):
        ledger.issue(_envelope(authz_class="super_ability"))
