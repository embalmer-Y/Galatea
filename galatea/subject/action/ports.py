"""行动链九型对象图与端口合同（L10 §2/§10 ports.py；f0_action_contract.profile.yaml 冻结）。

认识链铁律（L10 §2 纪律）：intention ≠ execution ≠ receipt ≠ attribution；
ExecutionFact 对主体平面物理不可见（EVIDENCE_ONLY，ClassVar 标记 + M0 import-linter）；
gateway 是现实效果唯一合法通道，fail closed（ReasonCode 九型 = 冻结 profile）。
F0 范围 = schema 合同；八项校验执行逻辑（gateway.py）归 M0。
"""
from dataclasses import dataclass, field
from enum import StrEnum

from galatea.kernel.packet import AccessScope, ArtifactRef
from galatea.kernel.unknown import Unknown

__all__ = [
    "GatewayReasonCode",
    "GatewayDecision",
    "AuthorizationDecision",
    "SubmittedCommand",
    "ExecutionFact",
    "ReceivedExecutionReceipt",
    "ReceivedOutcome",
    "EfferenceCopy",
    "AttributionKind",
    "AgencyAttribution",
    "SettlementKind",
    "GoalSettlement",
]


class GatewayReasonCode(StrEnum):
    """八项校验失败码（f0_action_contract.profile.yaml gateway_checks；fail closed）。"""

    SCHEMA_INVALID = "SCHEMA_INVALID"
    CONTEXT_MISMATCH = "CONTEXT_MISMATCH"
    CAPABILITY_DENIED = "CAPABILITY_DENIED"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    CONTAINMENT_VIOLATION = "CONTAINMENT_VIOLATION"  # S0（HLD §13.3）
    AUTHZ_STALE = "AUTHZ_STALE"
    AUTHZ_REVOKED = "AUTHZ_REVOKED"
    DUPLICATE_COMMAND = "DUPLICATE_COMMAND"
    DEADLINE_MISSED = "DEADLINE_MISSED"


class GatewayDecision(StrEnum):
    """授权判定三态（L10 §2.2 act.authz_decision）。"""

    AUTHORIZED = "AUTHORIZED"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    """gateway 独占写（L10 §3：唯一写入者 = Capability Gateway）。"""

    intention_id: str
    decision: GatewayDecision
    failed_checks: tuple[str, ...]
    reason_code: GatewayReasonCode | None
    policy_version: str
    freshness_ref: str | None


@dataclass(frozen=True, slots=True)
class SubmittedCommand:
    """gateway 签名命令（L01 world.apply 只接受 gateway 签名；未签名 schema 级即拒）。"""

    command_id: str
    gateway_signature: str
    requested_action: str
    budget: int
    deadline: int
    idempotency_key: str
    authorization_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.gateway_signature:
            raise ValueError("unsigned command rejected at schema level（fail closed，L10 §4.1）")


class ExecutionDomain(StrEnum):
    """效果域（L10 §4.2 execution_branches[].domain；MW0 恒 SIMULATED）。"""

    NONE = "NONE"
    SIMULATED = "SIMULATED"
    DIGITAL = "DIGITAL"
    PHYSICAL = "PHYSICAL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ExecutionFact:
    """执行事实——独立环境/PhysIO Bridge 产生，主体平面不可见（L10 §3 禁止读写双方）。"""

    command_id: str
    requested_effect: str
    effective_effect: str
    domain: ExecutionDomain
    effects: tuple[ArtifactRef, ...]
    independent_source: str
    access_scope: AccessScope = field(
        default=AccessScope.EVIDENCE_ONLY, init=False
    )  # 平面恒定且构造不可指定（REV-0003 R4；M0 import-linter 强制命名空间隔离）

    def __post_init__(self) -> None:
        if self.access_scope is not AccessScope.EVIDENCE_ONLY:
            raise ValueError("ExecutionFact is EVIDENCE_ONLY by contract（主体平面不可见，L10 §3）")


@dataclass(frozen=True, slots=True)
class ReceivedExecutionReceipt:
    """主体可见回执（RECEIVED 层级；L01 Adapter 出口，不可改写）。"""

    command_ref: str
    receipt_kind: str
    status: str
    ts: int

    def __post_init__(self) -> None:
        if not self.command_ref or not self.receipt_kind:
            raise ValueError("receipt requires command_ref and receipt_kind")


@dataclass(frozen=True, slots=True)
class ReceivedOutcome:
    """形成后结果引用（RECEIVED；经 L02 形成，非隐藏真值 Y）。"""

    outcome_ref: ArtifactRef
    received_at: int


@dataclass(frozen=True, slots=True)
class EfferenceCopy:
    """传出副本（L10 §4.3：提交命令同步产生，必早于效果到达）。"""

    intention_id: str
    motor_command_copy: str
    predicted_consequence_ref: ArtifactRef | None


# 术语注记（REV-0003 R9①）：EfferenceCopy = 传出副本（运动指令副本，非"傅里叶"）。


class AttributionKind(StrEnum):
    """归属六类（L10 §4.4；coercion 永不得归自产——硬规则在代码分支 + 测试断言）。"""

    SELF_PRODUCED = "SELF_PRODUCED"
    AUTHORIZED = "AUTHORIZED"
    REFLEX = "REFLEX"
    FAULT = "FAULT"
    COERCED = "COERCED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class AgencyAttribution:
    """归属（只用主体可见证据：visible_only 恒 True；可保持 UNKNOWN）。"""

    action_window: tuple[int, int]
    attribution_kind: AttributionKind
    probability: float | Unknown
    evidence_refs: tuple[str, ...]
    visible_only: bool  # 构造校验恒 True
    unknowns: tuple[Unknown, ...] = ()

    def __post_init__(self) -> None:
        if self.visible_only is not True:
            raise ValueError("attribution must use visible-only evidence（L10 §4.4）")
        # coercion 永不得归自产（HLD §8 硬规则）：六类互斥的单值上恒真；
        # 行为级强制（归属系统永不产出 COERCED→SELF 改写）由 coercion_guard.py（M1）承载。


class SettlementKind(StrEnum):
    """结算五态（L10 §4.5：UNKNOWN 是合法结算，禁把 unresolved 归为 FAILED）。"""

    ACHIEVED = "ACHIEVED"
    FAILED = "FAILED"
    ABANDONED = "ABANDONED"
    SUPERSEDED = "SUPERSEDED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class GoalSettlement:
    """目标结算（→ L08）。"""

    goal_ref: str
    outcome_kind: SettlementKind
    attribution_ref: str | None
    evidence_refs: tuple[str, ...]
