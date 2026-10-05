"""自我预测误差累积（L04 §4.5/§10 self_error.py；Q-L04-04 双时间尺度）。

维度 = 身体态向量（Q-L04-04）：energy/integrity/load 二阶差分 + 朝向变化 +
能力观测偏差——全部主体可见面（禁真值直通，承 P14）。情感评价维度留 C2
（本裁决不预支九维，Q-L04-04）。
EWMA 递推（ADR-G-0013 可复算探针规格同式）：s ← (1/τ)·v + (1−1/τ)·s，
首值 s = v₀，8 位舍入；τ=4（T3）/ τ=64（T6）——直接承 Q-L00-01 频率比，零新常数。
自我预测误差是 L09 metacontrol 与 L05 appraisal 的输入——不是惩罚、不是 reward。
"""
from dataclasses import dataclass

from galatea.subject.c1profile import C1Profile

ERROR_DIMENSIONS: tuple[str, ...] = (
    "energy_second_difference",
    "integrity_second_difference",
    "load_second_difference",
    "orientation_change",
    "capability_deviation",
)


@dataclass(frozen=True, slots=True)
class SelfPredictionError:
    """自我预测误差（L04 §4.1：magnitude, dims[], window）。"""

    magnitude: float
    dims: tuple[tuple[str, float, float], ...]   # (dim, s_fast, s_slow)
    window: tuple[int, int]                       # (first_cycle, last_cycle)


def _ewma(previous: float | None, value: float, tau: int) -> float:
    """EWMA 步进（首值 s = v₀；8 位舍入——探针规格，任何人可独立重演）。"""
    updated = value if previous is None else (1.0 / tau) * value + (1.0 - 1.0 / tau) * previous
    return round(updated, 8)


class SelfPredictionErrorAccumulator:
    """双时间尺度自我误差累积器（T3 快分量 / T6 慢分量挂点由调用方按拍驱动）。"""

    def __init__(self, profile: C1Profile) -> None:
        self._tau_fast = profile.models.tau_fast_cycles
        self._tau_slow = profile.models.tau_slow_cycles
        self._s_fast: dict[str, float | None] = {d: None for d in ERROR_DIMENSIONS}
        self._s_slow: dict[str, float | None] = {d: None for d in ERROR_DIMENSIONS}
        self._first_cycle: int | None = None
        self._last_cycle: int | None = None
        # 二阶差分历史（energy/integrity/load 各保留前两拍）
        self._history: dict[str, tuple[float, float]] = {d: (0.0, 0.0) for d in ERROR_DIMENSIONS[:3]}

    def _second_difference(self, dim: str, value: float) -> float:
        prev2, prev1 = self._history[dim]
        delta = value - prev1
        second = delta - (prev1 - prev2)
        self._history[dim] = (prev1, value)
        return second

    def update(
        self, cycle: int, energy: float, integrity: float, load: float,
        orientation_change: bool, capability_deviation: bool,
    ) -> SelfPredictionError:
        """单拍更新（二阶差分 → 双 EWMA → 汇总；确定性 float64）。"""
        values = {
            "energy_second_difference": self._second_difference("energy_second_difference", energy),
            "integrity_second_difference": self._second_difference("integrity_second_difference", integrity),
            "load_second_difference": self._second_difference("load_second_difference", load),
            "orientation_change": 1.0 if orientation_change else 0.0,
            "capability_deviation": 1.0 if capability_deviation else 0.0,
        }
        dims: list[tuple[str, float, float]] = []
        for dim in ERROR_DIMENSIONS:
            v = values[dim]
            s_fast = _ewma(self._s_fast[dim], v, self._tau_fast)
            s_slow = _ewma(self._s_slow[dim], v, self._tau_slow)
            self._s_fast[dim] = s_fast
            self._s_slow[dim] = s_slow
            dims.append((dim, s_fast, s_slow))
        if self._first_cycle is None:
            self._first_cycle = cycle
        first_cycle: int = self._first_cycle
        self._last_cycle = cycle
        last_cycle: int = self._last_cycle
        magnitude = round(sum(max(abs(f), abs(s)) for _, f, s in dims) / len(dims), 8)
        return SelfPredictionError(
            magnitude=magnitude, dims=tuple(dims),
            window=(first_cycle, last_cycle),
        )

    def snapshot(self) -> SelfPredictionError | None:
        """当前累积状态（未更新过 → None，禁伪造零误差）。"""
        if self._first_cycle is None or self._last_cycle is None:
            return None
        first_cycle: int = self._first_cycle
        last_cycle: int = self._last_cycle
        dims = tuple(
            (d, self._s_fast[d] or 0.0, self._s_slow[d] or 0.0) for d in ERROR_DIMENSIONS
        )
        magnitude = round(sum(max(abs(f), abs(s)) for _, f, s in dims) / len(dims), 8)
        return SelfPredictionError(
            magnitude=magnitude, dims=dims, window=(first_cycle, last_cycle)
        )
