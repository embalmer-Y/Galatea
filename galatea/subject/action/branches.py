"""execution_branches[] 与 requested≠effective 分歧分类（L10 §4.2/§10 branches.py）。

ADR-G-0005 R5 移交件（M1）。纪律：requested ≠ effective 是**一等结构**——
blocked/fault/coercion/sham 干预在此显形，禁合并（L10 §8 不变量 6）；效果域
MW0 期恒 SIMULATED（domain 强制见构造校验）；coercion 前缀（"coerced:"，L01
dynamics 约定）必须归类 COERCED，错标即拒（禁把外因洗成自产的前置面）。
"""
import enum
from dataclasses import dataclass

from galatea.kernel.unknown import Unknown
from galatea.subject.action.ports import ExecutionDomain

__all__ = [
    "CausalRole",
    "DivergenceKind",
    "RequestedEffectiveDivergence",
    "ExecutionBranch",
    "build_branch",
    "divergence_from_effective",
]


class CausalRole(enum.StrEnum):
    """来源因果角色（L10 §4.2 sources[]：module|device + causal_role）。"""

    SOLE = "SOLE"
    JOINT = "JOINT"
    EXTERNAL = "EXTERNAL"
    UNKNOWN = "UNKNOWN"


class DivergenceKind(enum.StrEnum):
    """requested vs effective 分歧五+一类（L10 §4.2）。"""

    NONE = "NONE"
    BLOCKED = "BLOCKED"          # 命令未执行（拒绝/未到达）
    SUBSTITUTED = "SUBSTITUTED"  # 效果被替换（sham：dry-run 报成功、世界不变）
    COERCED = "COERCED"          # 外因强制（coerced: 前缀；归属必须走外因分支）
    FAULT = "FAULT"              # 故障（投递丢弃/异常）
    UNKNOWN = "UNKNOWN"


_COERCED_PREFIX = "coerced:"


@dataclass(frozen=True, slots=True)
class RequestedEffectiveDivergence:
    """分歧记录（kind + 量级；magnitude 语义由干预 signature 侧定义）。"""

    kind: DivergenceKind
    magnitude: float | None = None

    def __post_init__(self) -> None:
        if self.magnitude is not None and self.kind is DivergenceKind.NONE:
            raise ValueError("NONE divergence carries no magnitude（禁为无分歧编造量级）")


@dataclass(frozen=True, slots=True)
class ExecutionBranch:
    """执行分支（L10 §4.2：requested/effective、域、来源、授权引用、效果、分歧）。"""

    branch_id: str
    requested_action: str
    effective_action: str | Unknown
    domain: ExecutionDomain
    sources: tuple[tuple[str, CausalRole], ...]
    effects: tuple[str, ...]              # L01 EffectFact 引用（EVIDENCE_ONLY，仅 Recorder/Evaluator 可读）
    divergence: RequestedEffectiveDivergence
    authorization_refs: tuple[str, ...] = ()   # P1 四类授权；MW0 期为 profile 引用

    def __post_init__(self) -> None:
        if not self.branch_id:
            raise ValueError("ExecutionBranch requires branch_id")
        if not self.requested_action:
            raise ValueError("ExecutionBranch requires requested_action")
        if self.domain is ExecutionDomain.PHYSICAL:
            raise ValueError(
                "PHYSICAL domain requires P1（四类授权全齐）；MW0/C 期恒 SIMULATED/NONE（L10 §4.2）"
            )
        # coercion 禁合并（L10 §8 不变量 6 + HLD §8）：effective 带 coerced: 前缀而 kind≠COERCED 即拒
        effective = self.effective_action
        if isinstance(effective, str) and effective.startswith(_COERCED_PREFIX):
            if self.divergence.kind is not DivergenceKind.COERCED:
                raise ValueError("coerced: effective must classify COERCED（禁外因洗白，L10 §4.2）")
        if self.divergence.kind is DivergenceKind.NONE and isinstance(effective, str):
            if effective != self.requested_action:
                raise ValueError(
                    f"NONE divergence requires requested == effective: {self.requested_action!r} vs {effective!r}"
                )


def divergence_from_effective(requested: str, effective: str | None) -> DivergenceKind:
    """由世界侧结算文本分类分歧（dynamics.py 约定：coercion 前缀 "coerced:"）。

    effective=None（命令未执行——拒绝/未到达）→ UNKNOWN：BLOCKED 与 FAULT 的
    区分需干预侧知识（五类干预 signature），由调用方以显式 kind 覆盖。
    """
    if effective is None:
        return DivergenceKind.UNKNOWN
    if effective == requested:
        return DivergenceKind.NONE
    if effective.startswith(_COERCED_PREFIX):
        return DivergenceKind.COERCED
    return DivergenceKind.SUBSTITUTED


def build_branch(
    branch_id: str,
    requested_action: str,
    effective_action: str | Unknown,
    domain: ExecutionDomain,
    sources: tuple[tuple[str, CausalRole], ...],
    effects: tuple[str, ...],
    divergence_kind: DivergenceKind | None = None,
    magnitude: float | None = None,
    authorization_refs: tuple[str, ...] = (),
) -> ExecutionBranch:
    """构造执行分支；divergence_kind 缺省时由 effective 文本自动分类（显式覆盖优先）。"""
    kind = divergence_kind if divergence_kind is not None else divergence_from_effective(
        requested_action, effective_action if isinstance(effective_action, str) else None
    )
    return ExecutionBranch(
        branch_id=branch_id,
        requested_action=requested_action,
        effective_action=effective_action,
        domain=domain,
        sources=sources,
        effects=effects,
        divergence=RequestedEffectiveDivergence(kind=kind, magnitude=magnitude),
        authorization_refs=authorization_refs,
    )
