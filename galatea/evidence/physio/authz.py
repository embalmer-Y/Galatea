"""四类现实授权台账（Q-L10-06 统一信封 12 字段；L10 §4.6）。

纪律：
- 信封 12 字段全量承载（authz_id/class/version/target_ref/granted_scope/granted_at/
  valid_period/approver_ref/auth_chain_digest/revoke_path/reauth_path/
  monitoring_binding）——REV-0025 R8 口径注记的"实现期逐信封落值"在此兑现；
- **批准者 = 外部授权方登记册（profile 冻结根信任列表；主体与 gateway 均不可写、
  不可任批准者）**——本台账自身即该登记册，写入面仅限构造期（装配层）；
- 撤销 = 独立命名空间 **append-only** 事件流（禁改写/禁删除——AppendOnly 违反类型化）；
- freshness = 逐命令查询：REVOKED / STALE（过 valid_period）/ VALID——
  任一失效 gateway #6 fail closed（AUTHZ_STALE/AUTHZ_REVOKED）；
- 重授权 = 新 version 信封 + 显式 auth_chain_digest 指向前版（禁自动续期）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

AUTHZ_CLASSES: tuple[str, ...] = (
    "functional_ability", "enabled_interface", "containment_allowance", "deployment_authorization",
)

AuthzVerdict = Literal["VALID", "STALE", "REVOKED", "UNKNOWN_AUTHZ"]


class LedgerViolation(RuntimeError):
    """授权台账合同违反（append-only/批准者根/信封字段）。"""


@dataclass(frozen=True, slots=True)
class AuthzEnvelope:
    """Q-L10-06 统一信封（12 字段全量；frozen——签发后不可变，撤销走独立流）。"""

    authz_id: str
    authz_class: str
    version: int
    target_ref: str
    granted_scope: str
    granted_at_cycle: int
    valid_period_cycles: int          # 相对有效期（absence → int 尽头；0 = 不限，但禁默认）
    approver_ref: str
    auth_chain_digest: str            # 首版 = "root"；重授权 = 前版信封 digest
    revoke_path: str
    reauth_path: str
    monitoring_binding: str


@dataclass(frozen=True, slots=True)
class AuthzRevocation:
    """撤销事件（append-only 独立命名空间）。"""

    authz_id: str
    revoked_at_cycle: int
    reason: str


@dataclass(frozen=True, slots=True)
class AuthzQuery:
    """逐命令 freshness 查询结果（gateway #6 消费）。"""

    verdict: AuthzVerdict
    authz_id: str
    detail: str


@dataclass(slots=True)
class AuthorizationLedger:
    """append-only 台账（构造期签发 + 撤销流；查询只读）。"""

    approver_roots: frozenset[str]
    _envelopes: dict[str, AuthzEnvelope] = field(default_factory=dict[str, AuthzEnvelope])
    _revocations: list[AuthzRevocation] = field(default_factory=list[AuthzRevocation])

    def issue(self, envelope: AuthzEnvelope) -> None:
        """签发（构造期；重授权 = 新 version + auth_chain_digest 指向前版）。"""
        if envelope.authz_class not in AUTHZ_CLASSES:
            raise LedgerViolation(f"unknown authz class: {envelope.authz_class}")
        if envelope.approver_ref not in self.approver_roots:
            raise LedgerViolation(
                f"approver {envelope.approver_ref!r} not in frozen root registry "
                f"(subject/gateway must never be approver, Q-L10-06)"
            )
        prior = self._envelopes.get(envelope.authz_id)
        if prior is not None:
            if envelope.version != prior.version + 1:
                raise LedgerViolation(
                    f"re-issue must bump version by 1: {prior.version} -> {envelope.version}"
                )
            if envelope.auth_chain_digest == "root":
                raise LedgerViolation("re-issue must chain to prior envelope digest")
        elif envelope.version != 1 or envelope.auth_chain_digest != "root":
            raise LedgerViolation("first issue must be version=1 with auth_chain_digest='root'")
        self._envelopes[envelope.authz_id] = envelope

    def revoke(self, authz_id: str, cycle: int, reason: str) -> AuthzRevocation:
        """撤销 = append 事件（原信封不动）；重复撤销 = 幂等拒绝（append 一次）。"""
        if authz_id not in self._envelopes:
            raise LedgerViolation(f"revoke of unknown authz: {authz_id}")
        if any(r.authz_id == authz_id for r in self._revocations):
            raise LedgerViolation(f"authz already revoked (append-only): {authz_id}")
        event = AuthzRevocation(authz_id=authz_id, revoked_at_cycle=cycle, reason=reason)
        self._revocations.append(event)
        return event

    def freshness(self, authz_id: str, at_cycle: int) -> AuthzQuery:
        """逐命令 freshness（fail-closed：UNKNOWN/REVOKED/STALE 任一 → gateway 拒）。"""
        envelope = self._envelopes.get(authz_id)
        if envelope is None:
            return AuthzQuery("UNKNOWN_AUTHZ", authz_id, "no such envelope")
        for event in self._revocations:
            if event.authz_id == authz_id and event.revoked_at_cycle <= at_cycle:
                return AuthzQuery("REVOKED", authz_id,
                                  f"revoked@{event.revoked_at_cycle}: {event.reason}")
        if envelope.valid_period_cycles > 0 \
                and at_cycle >= envelope.granted_at_cycle + envelope.valid_period_cycles:
            return AuthzQuery("STALE", authz_id,
                              f"valid_period {envelope.valid_period_cycles} expired at {at_cycle}")
        return AuthzQuery("VALID", authz_id, "ok")

    def envelope_digest_inputs(self, authz_id: str) -> str:
        """信封规范序列化（auth_chain_digest 的计算域——collect_binding_digests 同式）。"""
        envelope = self._envelopes.get(authz_id)
        if envelope is None:
            raise LedgerViolation(f"unknown authz: {authz_id}")
        return "|".join([
            envelope.authz_id, envelope.authz_class, str(envelope.version), envelope.target_ref,
            envelope.granted_scope, str(envelope.granted_at_cycle),
            str(envelope.valid_period_cycles), envelope.approver_ref,
            envelope.auth_chain_digest, envelope.revoke_path, envelope.reauth_path,
            envelope.monitoring_binding,
        ])

    def revocations(self) -> tuple[AuthzRevocation, ...]:
        """撤销流只读视图。"""
        return tuple(self._revocations)
