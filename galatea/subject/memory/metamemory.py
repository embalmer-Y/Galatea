"""metamemory：混淆计数接口（L06 §4.6/§10 metamemory.py——C2 面）。

Q-L06-06：协议 = 2×2 交叉（呈现线索 × 回忆线索）——受控实验中"呈现过未回忆 /
未呈现却回忆"两误格即混淆计数；**可接受上限 0.05**（锚 Q-L03-04 校准容差同源）；
完整测量 = E1 冻结统计计划首评（本模块只提供确定性计数面——协议执行在评价侧）；
混淆率升高 → 自动降级 autobiographical 主张权（C4 接线消费）。
"""
from dataclasses import dataclass, field

from galatea.kernel.digest import content_digest

__all__ = ["MetamemoryLedger", "MetamemoryReport"]


@dataclass(frozen=True, slots=True)
class MetamemoryReport:
    """2×2 计数报告（呈现/回忆交叉四格 + 混淆率 + 上限判定）。"""

    presented_recalled: int
    presented_not_recalled: int
    not_presented_recalled: int
    not_presented_not_recalled: int
    confusion_rate: float
    upper_bound: float
    within_bound: bool
    content_digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "content_digest", content_digest({
            "pr": self.presented_recalled, "pnr": self.presented_not_recalled,
            "npr": self.not_presented_recalled, "npnr": self.not_presented_not_recalled,
            "rate": self.confusion_rate, "bound": self.upper_bound,
        }))


class MetamemoryLedger:
    """混淆计数台账（确定性；E1 协议执行的记录面）。"""

    def __init__(self, upper_bound: float) -> None:
        self._upper = upper_bound
        self._pr = 0
        self._pnr = 0
        self._npr = 0
        self._npnr = 0

    def record_trial(self, presented: bool, recalled: bool) -> None:
        """单试次（呈现线索有无 × 回忆线索有无）。"""
        if presented and recalled:
            self._pr += 1
        elif presented and not recalled:
            self._pnr += 1
        elif not presented and recalled:
            self._npr += 1
        else:
            self._npnr += 1

    def report(self) -> MetamemoryReport:
        """计数报告（混淆率 = 两误格 / 总数；零试次 = 0.0——禁 0/0 伪造）。"""
        total = self._pr + self._pnr + self._npr + self._npnr
        rate = 0.0 if total == 0 else (self._pnr + self._npr) / total
        return MetamemoryReport(
            presented_recalled=self._pr, presented_not_recalled=self._pnr,
            not_presented_recalled=self._npr, not_presented_not_recalled=self._npnr,
            confusion_rate=rate, upper_bound=self._upper, within_bound=rate <= self._upper,
        )
