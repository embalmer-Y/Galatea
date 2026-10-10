"""PhysIO 能力面（Q-L10-12：capability_set = profile 冻结枚举 + 域隔离）。

gateway 校验 #4 扩展的 PhysIO 侧承载：动作必须在 p1 profile 冻结枚举内；
MW0 原语域隔离在枚举之外再兜一层（双保险——枚举污染也不跨域）。
"""
from __future__ import annotations

from dataclasses import dataclass

from galatea.env.physio.lstate import MW0_PRIMITIVES
from galatea.env.physio.ports import P1PhysioProfile


@dataclass(frozen=True, slots=True)
class CapabilityDecision:
    allowed: bool
    reason: str


def check_capability(action: str, profile: P1PhysioProfile) -> CapabilityDecision:
    """profile 冻结枚举 + 域隔离双检（顺序固定：域隔离先行——即使枚举被污染也不跨域）。"""
    if action in MW0_PRIMITIVES:
        return CapabilityDecision(
            allowed=False,
            reason="DOMAIN_ISOLATION: MW0 primitives unavailable in physical domain (Q-L10-12④)",
        )
    if action not in profile.capability_actions:
        return CapabilityDecision(
            allowed=False,
            reason=f"NOT_IN_FROZEN_CAPABILITY_SET: {action!r} ∉ {profile.capability_actions}",
        )
    return CapabilityDecision(allowed=True, reason="OK")
