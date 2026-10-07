"""语言面回执（L12 §3 角色调用台账 / §10 receipt.py；subject_state.language.calls 承载）。

每角色调用必留：角色/输入 digest/输出 digest/端口/结果——台账 digest 入
checkpoint（连续性纪律）与 EvidenceResult（评价侧审计）。
"""
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from galatea.subject.language.roles import RoleKind

__all__ = ["LanguageReceipt", "language_receipt"]


@dataclass(frozen=True, slots=True)
class LanguageReceipt:
    """角色调用台账行（调用/结果/权限检查/预算——L12 §3 对象图）。"""

    role: str
    input_digest: str
    output_digest: str
    out_port: str
    accepted: bool
    detail: str
    ts: int

    def __post_init__(self) -> None:
        if not self.role or not self.out_port:
            raise ValueError("LanguageReceipt requires role and out_port")


def language_receipt(
    role: RoleKind, input_payload: dict[str, Any], output_text: str, out_port: str,
    *, accepted: bool, detail: str, ts: int,
) -> LanguageReceipt:
    """台账行构造（digest = 规范化 JSON sha256，与回放寻址同式）。"""
    in_dig = hashlib.sha256(
        json.dumps(input_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    out_dig = hashlib.sha256(output_text.encode("utf-8")).hexdigest()
    return LanguageReceipt(
        role=role.value, input_digest=in_dig, output_digest=out_dig,
        out_port=out_port, accepted=accepted, detail=detail, ts=ts,
    )
