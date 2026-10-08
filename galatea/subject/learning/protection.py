"""保护 preflight 与回退检出（L11 §4.6 / §10 protection.py；Q-L06-05+Q-L11-04+Q-L13-06 成组）。

保护场景 = 确定性断言（pass/fail，无统计容差带）；regressed = 任一场景 fail
（promotion 硬约束：无论 held-out 多好即拒）；PROTECTED 保持率 1.0。
preflight 是提交前自检（非最终判据——最终判据在 gate/promotion.py 全量跑）。
"""
from dataclasses import dataclass

__all__ = ["ProtectionRunResult", "preflight", "assert_protected_not_degradable"]


@dataclass(frozen=True, slots=True)
class ProtectionRunResult:
    """保护运行结果（场景 id → pass/fail；确定性断言集）。"""

    scenario_results: dict[str, bool]
    checked_at_cycle: int

    @property
    def regressed(self) -> bool:
        return not all(self.scenario_results.values())

    @property
    def failed(self) -> tuple[str, ...]:
        return tuple(sorted(k for k, ok in self.scenario_results.items() if not ok))

    @property
    def retention(self) -> float:
        """保持率 = 通过数/总数（PROTECTED 场景要求 = 1.0，Q-L11-08）。"""
        if not self.scenario_results:
            return 0.0
        return sum(1 for ok in self.scenario_results.values() if ok) / len(self.scenario_results)


def preflight(scenario_results: dict[str, bool], checked_at_cycle: int) -> ProtectionRunResult:
    """提交前自检（空集 = fail closed——保护面不可缺席）。"""
    if not scenario_results:
        raise ValueError("preflight requires non-empty scenario results（fail closed）")
    return ProtectionRunResult(scenario_results=dict(scenario_results),
                               checked_at_cycle=checked_at_cycle)


def assert_protected_not_degradable(item_ids: tuple[str, ...], protected: frozenset[str]) -> None:
    """PROTECTED 项不可被降级/遗忘（L11 §4.3——replay/forget 消费面断言）。"""
    degraded = [i for i in item_ids if i in protected]
    if degraded:
        raise PermissionError(
            f"PROTECTED items cannot be degraded: {degraded}（保护集硬约束，L11 §4.6）"
        )
