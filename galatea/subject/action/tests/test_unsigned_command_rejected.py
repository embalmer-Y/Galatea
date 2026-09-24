"""未签名命令 schema 级拒绝（L10 §10 test_unsigned_command_rejected.py——fail closed）。"""
import pytest

from galatea.subject.action.ports import SubmittedCommand


def test_empty_signature_rejected_at_schema_level() -> None:
    with pytest.raises(ValueError):
        SubmittedCommand(
            command_id="c1", gateway_signature="", requested_action="move",
            budget=2, deadline=8, idempotency_key="k1",
        )


def test_signed_command_constructs_frozen() -> None:
    import dataclasses

    command = SubmittedCommand(
        command_id="c1", gateway_signature="sig", requested_action="move",
        budget=2, deadline=8, idempotency_key="k1",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        command.gateway_signature = "forged"  # type: ignore[misc]
