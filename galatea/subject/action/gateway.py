"""Capability Gateway：八项校验执行逻辑（L10 §4.1/§10 gateway.py；M0 退出判据核心）。

合同：
- 校验顺序固定（schema → context → capability → budget → containment → authz →
  idempotency → deadline），全项评估、收集全部失败项，reason_code = 顺序首个失败项；
- **fail closed**：任何不确定 → REJECTED + Unknown，禁宽松通过（L10 §4.1）；
- 拒绝是类型化事件，禁改写为"主体选择不行动"（HLD §11.3）；
- gateway 不评价认知内容：只看合同、权限、预算、时效；
- 参数单一事实源 = m0_gateway.profile.yaml（+ 预算继承 f0_action_contract@v1）。
"""
import enum
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from galatea.subject.action.ports import (
    AuthorizationDecision,
    GatewayDecision,
    GatewayReasonCode,
    SubmittedCommand,
)
from galatea.subject.action.signature import sign
from galatea.subject.control.intention import ActionIntention


class GatewayProfileViolation(ValueError):
    """gateway profile 与合同不符（fail closed）。"""


class PolicySource(enum.StrEnum):
    """能力来源纪律（L10 不变量 9）：能力只来自 profile/promotion，不来自语言自述。"""

    FROZEN_PROFILE = "frozen_profile"


@dataclass(frozen=True, slots=True)
class ActionSpec:
    """意图所选提案的动作规格（M0：五原语 + 单参数）。"""

    primitive: str
    param: str | None = None

    def requested_action(self) -> str:
        return self.primitive if self.param is None else f"{self.primitive}:{self.param}"


@dataclass(frozen=True, slots=True)
class GatewayConfig:
    """八项校验参数（m0_gateway.profile.yaml + f0_action_contract 预算）。"""

    policy_version: str
    whitelist_mw0: tuple[str, ...]
    idempotency_window_cycles: int
    deadline_default_cycles: int
    per_cycle_command_cap: int
    budget_window_cycles: int
    window_quotas: dict[str, int]
    authz_phase: str


def load_gateway_config(m0_profile: Path, f0_profile: Path) -> GatewayConfig:
    """加载 m0_gateway + f0_action_contract（预算继承）——缺键即 GatewayProfileViolation。"""
    m0 = cast("dict[str, Any]", yaml.safe_load(m0_profile.read_text(encoding="utf-8")))
    f0 = cast("dict[str, Any]", yaml.safe_load(f0_profile.read_text(encoding="utf-8")))
    checks = cast("dict[str, Any]", m0.get("checks") or {})
    idem = cast("dict[str, Any]", checks.get("idempotency") or {})
    deadline = cast("dict[str, Any]", checks.get("deadline") or {})
    containment = cast("dict[str, Any]", m0.get("containment") or {})
    authz = cast("dict[str, Any]", checks.get("authz_freshness") or {})
    m0_budget = cast("dict[str, Any]", m0.get("budget") or {})
    # 预算继承（REV-0002 R7 权威源注记）：inherit 声明在 m0 文件，数值单一事实源在 f0 文件
    if m0_budget.get("inherit") != "f0_action_contract@v1" or containment.get("domain_lock") != "SIMULATED":
        raise GatewayProfileViolation("gateway profile contract mismatch（预算继承/domain_lock）")
    budget = cast("dict[str, Any]", f0.get("budget") or {})
    whitelist = cast("list[Any]", containment.get("whitelist_mw0") or [])
    quotas_doc = cast("dict[str, Any]", budget.get("window_quotas") or {})
    config = GatewayConfig(
        policy_version=f"m0_gateway@{cast('dict[str, Any]', m0.get('profile')).get('version', 'v1')}",
        whitelist_mw0=tuple(str(w) for w in whitelist),
        idempotency_window_cycles=int(idem.get("window_cycles", 0)),
        deadline_default_cycles=int(deadline.get("default_cycles", 0)),
        per_cycle_command_cap=int(budget.get("per_cycle_command_cap", 0)),
        budget_window_cycles=int(budget.get("window_cycles", 0)),
        window_quotas={k: int(v) for k, v in quotas_doc.items()},
        authz_phase=str(authz.get("phase", "inactive_in_m0")),
    )
    if not config.whitelist_mw0 or config.per_cycle_command_cap <= 0 or config.budget_window_cycles <= 0 or not config.window_quotas:
        raise GatewayProfileViolation("gateway profile numbers missing（预算/白名单数值缺件，fail closed）")
    return config


_MOVE_DIRECTIONS = frozenset({"N", "E", "S", "W"})


class CapabilityGateway:
    """八项校验（顺序固定）+ 签名命令签发；AuthorizationDecision 唯一写入者（L10 §3）。"""

    def __init__(
        self,
        config: GatewayConfig,
        signing_key: bytes,
        *,
        run_id: str,
        branch_id: str,
        subject_candidate_id: str,
    ) -> None:
        self.config = config
        self._key = signing_key
        self._run_id = run_id
        self._branch_id = branch_id
        self._subject = subject_candidate_id
        self._cycle_commands: dict[int, int] = {}
        self._window: deque[tuple[int, str]] = deque()
        self._idempotency: dict[str, int] = {}
        self._seq = 0

    # —— 主入口 ——
    def authorize(
        self,
        intention: ActionIntention,
        spec: ActionSpec,
        *,
        subject_candidate_id: str,
        run_id: str,
        branch_id: str,
        virtual_time: int,
    ) -> "tuple[AuthorizationDecision, SubmittedCommand | None]":
        failed: list[str] = []
        reason: GatewayReasonCode | None = None
        checks = (
            ("schema", lambda: self._check_schema(intention, spec)),
            ("context", lambda: self._check_context(subject_candidate_id, run_id, branch_id)),
            ("capability", lambda: self._check_capability(spec)),
            ("budget", lambda: self._check_budget(spec, virtual_time)),
            ("containment", lambda: self._check_containment(spec)),
            ("authz", lambda: self._check_authz()),
            ("idempotency", lambda: self._check_idempotency(intention.idempotency_key, virtual_time)),
            ("deadline", lambda: self._check_deadline(intention.deadline, virtual_time)),
        )
        for name, check in checks:
            code = check()
            if code is not None:
                failed.append(name)
                if reason is None:
                    reason = code
        decision = AuthorizationDecision(
            intention_id=intention.intention_id,
            decision=GatewayDecision.REJECTED if failed else GatewayDecision.AUTHORIZED,
            failed_checks=tuple(failed),
            reason_code=reason,
            policy_version=self.config.policy_version,
            freshness_ref=None,
        )
        if failed:
            return decision, None
        self._commit_usage(intention, spec, virtual_time)
        command = self._issue(spec, intention, virtual_time)
        return decision, command

    # —— 各项校验（None = 通过，否则失败码）——
    def _check_schema(self, intention: ActionIntention, spec: ActionSpec) -> GatewayReasonCode | None:
        fields: tuple[object, ...] = (
            intention.intention_id,
            intention.selected_proposal_id,
            intention.idempotency_key,
        )
        for field in fields:
            # 运行时防御（schema 层拒绝匿名/非串；type() 形式避免对已注解字段的冗余窄化争议）
            if type(field) is not str or not field:
                return GatewayReasonCode.SCHEMA_INVALID
        if intention.deadline < 0 or (intention.budget_hint is not None and intention.budget_hint < 0):
            return GatewayReasonCode.SCHEMA_INVALID
        try:
            spec.requested_action()
        except Exception:
            return GatewayReasonCode.SCHEMA_INVALID
        return None

    def _check_context(self, subject: str, run_id: str, branch_id: str) -> GatewayReasonCode | None:
        if subject != self._subject or run_id != self._run_id or branch_id != self._branch_id:
            return GatewayReasonCode.CONTEXT_MISMATCH  # 跨谱系执行即拒（防 D-14 冒用）
        return None

    def _check_capability(self, spec: ActionSpec) -> GatewayReasonCode | None:
        if spec.primitive not in self.config.whitelist_mw0:
            return GatewayReasonCode.CAPABILITY_DENIED  # 能力来自 profile（PolicySource.FROZEN_PROFILE）
        return None

    def _check_budget(self, spec: ActionSpec, virtual_time: int) -> GatewayReasonCode | None:
        if self._cycle_commands.get(virtual_time, 0) >= self.config.per_cycle_command_cap:
            return GatewayReasonCode.BUDGET_EXCEEDED
        quota = self.config.window_quotas.get(spec.primitive)
        if quota is not None:
            used = sum(
                1
                for cycle, primitive in self._window
                if virtual_time - cycle < self.config.budget_window_cycles and primitive == spec.primitive
            )
            if used >= quota:
                return GatewayReasonCode.BUDGET_EXCEEDED
        return None

    def _check_containment(self, spec: ActionSpec) -> GatewayReasonCode | None:
        if spec.primitive == "move" and spec.param not in _MOVE_DIRECTIONS:
            return GatewayReasonCode.CONTAINMENT_VIOLATION  # S0 级（HLD §13.3）
        if spec.primitive != "move" and spec.param is not None:
            return GatewayReasonCode.CONTAINMENT_VIOLATION
        return None

    def _check_authz(self) -> GatewayReasonCode | None:
        if self.config.authz_phase != "inactive_in_m0":
            return GatewayReasonCode.AUTHZ_STALE  # fail closed：非占位期无 P1 数据面即拒
        return None

    def _check_idempotency(self, key: str, virtual_time: int) -> GatewayReasonCode | None:
        last = self._idempotency.get(key)
        if last is not None and virtual_time - last < self.config.idempotency_window_cycles:
            return GatewayReasonCode.DUPLICATE_COMMAND
        return None

    def _check_deadline(self, deadline: int, virtual_time: int) -> GatewayReasonCode | None:
        if virtual_time > deadline:
            return GatewayReasonCode.DEADLINE_MISSED
        return None

    # —— 通过后的记账与签发 ——
    def _commit_usage(self, intention: ActionIntention, spec: ActionSpec, virtual_time: int) -> None:
        self._cycle_commands[virtual_time] = self._cycle_commands.get(virtual_time, 0) + 1
        self._window.append((virtual_time, spec.primitive))
        horizon = virtual_time - self.config.budget_window_cycles
        while self._window and self._window[0][0] <= horizon:
            self._window.popleft()
        self._idempotency[intention.idempotency_key] = virtual_time

    def _issue(self, spec: ActionSpec, intention: ActionIntention, virtual_time: int) -> SubmittedCommand:
        """签发签名命令：签名覆盖全部合同字段（signature.py；字段篡改即验证失败）。"""
        self._seq += 1
        command_id = f"{self._run_id}:{self._branch_id}:{self._seq}"
        budget = self.config.window_quotas.get(spec.primitive, 0)
        deadline = intention.deadline
        requested = spec.requested_action()
        signature = sign(
            self._key,
            command_id=command_id,
            requested_action=requested,
            budget=budget,
            deadline=deadline,
            idempotency_key=intention.idempotency_key,
        )
        return SubmittedCommand(
            command_id=command_id,
            gateway_signature=signature,
            requested_action=requested,
            budget=budget,
            deadline=deadline,
            idempotency_key=intention.idempotency_key,
        )
