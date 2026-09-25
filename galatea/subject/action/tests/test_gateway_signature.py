"""gateway 签名合同（L10 §10 test_gateway_signature.py）。"""
from galatea.subject.action.signature import derive_signing_key, sign, verify


def test_signing_key_derived_from_run_seed() -> None:
    """同 run 同钥；异 run 异钥（Q-T11 流纪律：无独立随机源）。"""
    assert derive_signing_key(b"seed-A") == derive_signing_key(b"seed-A")
    assert derive_signing_key(b"seed-A") != derive_signing_key(b"seed-B")


def test_sign_verify_roundtrip() -> None:
    key = derive_signing_key(b"seed-A")
    fields = dict(command_id="R:B:1", requested_action="move:N", budget=256, deadline=100, idempotency_key="k1")
    signature = sign(key, **fields)  # type: ignore[arg-type]
    assert verify(key, signature, **fields)  # type: ignore[arg-type]


def test_any_field_tamper_breaks_verification() -> None:
    key = derive_signing_key(b"seed-A")
    signature = sign(key, command_id="R:B:1", requested_action="move:N", budget=256, deadline=100, idempotency_key="k1")
    for tampered in (
        dict(command_id="R:B:2"),
        dict(requested_action="move:E"),
        dict(budget=128),
        dict(deadline=99),
        dict(idempotency_key="k2"),
    ):
        fields = dict(command_id="R:B:1", requested_action="move:N", budget=256, deadline=100, idempotency_key="k1") | tampered
        assert not verify(key, signature, **fields)  # type: ignore[arg-type]


def test_cross_run_signature_not_valid() -> None:
    """跨 run 的签名不可通过验证（密钥隔离）。"""
    fields = dict(command_id="R:B:1", requested_action="move:N", budget=256, deadline=100, idempotency_key="k1")
    sig_a = sign(derive_signing_key(b"seed-A"), **fields)  # type: ignore[arg-type]
    assert not verify(derive_signing_key(b"seed-B"), sig_a, **fields)  # type: ignore[arg-type]
