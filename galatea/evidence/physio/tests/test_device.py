"""设备登记/BodyGraph 测试（设备新增双授权 fail-closed；digest 随设备集变动；被动期零执行器）。"""
import pytest

from galatea.evidence.physio.authz import AuthzEnvelope, AuthorizationLedger
from galatea.evidence.physio.device import DeviceRegistry, DeviceRegistryViolation

_ROOTS = frozenset({"owner_2026_10_10"})


def _ledger_with_device_authz() -> AuthorizationLedger:
    ledger = AuthorizationLedger(approver_roots=_ROOTS)
    ledger.issue(AuthzEnvelope(
        authz_id="dep-1", authz_class="deployment_authorization", version=1,
        target_ref="host:192.168.2.91", granted_scope="p1_passive", granted_at_cycle=0,
        valid_period_cycles=0, approver_ref="owner_2026_10_10", auth_chain_digest="root",
        revoke_path="owner_message", reauth_path="new_version_envelope",
        monitoring_binding="manifest",
    ))
    ledger.issue(AuthzEnvelope(
        authz_id="fa-host_telemetry", authz_class="functional_ability", version=1,
        target_ref="device:host_telemetry", granted_scope="readonly_telemetry+l2_calibration",
        granted_at_cycle=0, valid_period_cycles=0, approver_ref="owner_2026_10_10",
        auth_chain_digest="root", revoke_path="owner_message",
        reauth_path="new_version_envelope", monitoring_binding="manifest",
    ))
    return ledger


def _registry(ledger: AuthorizationLedger) -> DeviceRegistry:
    return DeviceRegistry(ledger, deployment_authz_id="dep-1")


def test_device_add_requires_both_fresh_authorizations() -> None:
    ledger = _ledger_with_device_authz()
    registry = _registry(ledger)
    entry = registry.add("host_telemetry", "telemetry_host",
                         ("calibrate_sensors", "selfcheck"), 0, "sensor")
    assert entry.source_ref == "fa-host_telemetry"
    with pytest.raises(DeviceRegistryViolation, match="functional_ability.*UNKNOWN_AUTHZ"):
        registry.add("ghost_device", "telemetry_host", (), 1, "sensor")   # 无信封 fail-closed
    ledger.issue(AuthzEnvelope(
        authz_id="fa-second_device", authz_class="functional_ability", version=1,
        target_ref="device:second_device", granted_scope="readonly_telemetry",
        granted_at_cycle=0, valid_period_cycles=0, approver_ref="owner_2026_10_10",
        auth_chain_digest="root", revoke_path="owner_message",
        reauth_path="new_version_envelope", monitoring_binding="manifest",
    ))
    ledger.revoke("fa-second_device", 10, "interface_isolated")
    with pytest.raises(DeviceRegistryViolation, match="functional_ability.*REVOKED"):
        registry.add("second_device", "telemetry_host", (), 11, "sensor")  # 撤销后拒


def test_body_graph_digest_changes_with_device_set() -> None:
    ledger = _ledger_with_device_authz()
    registry = _registry(ledger)
    digest_empty = registry.body_graph_digest()
    registry.add("host_telemetry", "telemetry_host", ("calibrate_sensors",), 0, "sensor")
    digest_one = registry.body_graph_digest()
    assert digest_empty != digest_one
    ledger.issue(AuthzEnvelope(
        authz_id="fa-camera", authz_class="functional_ability", version=1,
        target_ref="device:camera", granted_scope="readonly_frames", granted_at_cycle=0,
        valid_period_cycles=0, approver_ref="owner_2026_10_10", auth_chain_digest="root",
        revoke_path="owner_message", reauth_path="new_version_envelope",
        monitoring_binding="manifest",
    ))
    registry.add("camera", "tessera_node", ("observe",), 5, "sensor")
    assert registry.body_graph_digest() != digest_one       # 设备集变即变（L4+ 锚）
    assert registry.actuator_count() == 0                    # 被动期零执行器
    assert [d.device_id for d in registry.devices()] == ["camera", "host_telemetry"]


def test_duplicate_device_rejected() -> None:
    ledger = _ledger_with_device_authz()
    registry = _registry(ledger)
    registry.add("host_telemetry", "telemetry_host", (), 0, "sensor")
    with pytest.raises(DeviceRegistryViolation, match="already registered"):
        registry.add("host_telemetry", "telemetry_host", (), 1, "sensor")
