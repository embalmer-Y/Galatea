"""gateway 命令签名（L10 §10 signature.py——world.apply 只接受 gateway 签名，L01 §2.2）。

合同：确定性 MAC = HMAC-SHA256(密钥 = HKDF(run_seed, "gateway/signature")，
消息 = 命令合同字段的 canonical digest)。密钥从 run_seed 派生（Q-T11 流纪律，
无独立随机源）；验证 = 重算 + 常量时间比较（hmac.compare_digest）。
签名只证"命令出自本 gateway 实例且字段未被篡改"，不承载授权语义（授权在八项校验）。
"""
import hashlib
import hmac

from galatea.kernel.digest import content_digest
from galatea.kernel.rng import hkdf_sha256

_SALT = b"galatea/gateway/signature/v1"


def derive_signing_key(run_seed: bytes) -> bytes:
    """从 run_seed 派生签名密钥（同 run 同钥；跨 run 隔离）。"""
    return hkdf_sha256(ikm=run_seed, salt=_SALT, info=b"command-signature")


def _message(
    command_id: str,
    requested_action: str,
    budget: int,
    deadline: int,
    idempotency_key: str,
    authorization_refs: tuple[str, ...],
) -> bytes:
    digest = content_digest(
        {
            "command_id": command_id,
            "requested_action": requested_action,
            "budget": budget,
            "deadline": deadline,
            "idempotency_key": idempotency_key,
            "authorization_refs": list(authorization_refs),
        }
    )
    return digest.encode("ascii")


def sign(
    key: bytes,
    *,
    command_id: str,
    requested_action: str,
    budget: int,
    deadline: int,
    idempotency_key: str,
    authorization_refs: tuple[str, ...] = (),
) -> str:
    """生成命令签名（十六进制）。"""
    return hmac.new(
        key,
        _message(command_id, requested_action, budget, deadline, idempotency_key, authorization_refs),
        hashlib.sha256,
    ).hexdigest()


def verify(
    key: bytes,
    signature: str,
    *,
    command_id: str,
    requested_action: str,
    budget: int,
    deadline: int,
    idempotency_key: str,
    authorization_refs: tuple[str, ...] = (),
) -> bool:
    """校验命令签名：重算 + 常量时间比较；任何字段改动即 False。"""
    expected = sign(
        key,
        command_id=command_id,
        requested_action=requested_action,
        budget=budget,
        deadline=deadline,
        idempotency_key=idempotency_key,
        authorization_refs=authorization_refs,
    )
    return hmac.compare_digest(expected, signature)
