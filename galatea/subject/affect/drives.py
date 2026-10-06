"""驱力状态、稳态误差与告警（L05 §4.5/§10 drives.py，C2 实现期）。

Q-L05-02：set-point = 冻结满值（energy/integrity = 1.0、load = 0——m0 派生）；
e_d = set_point − x_d 单侧（≥0）；w_d 1:1:1。

告警分级（Q-L01-08 L05 侧补裁，2026-10-06，成文于 Q-L05-02 A 区行内）：
severity = e_d 纯阈值比较三级——LOW(> band=0.1) / HIGH(≥ 0.5) / CRITICAL(≥ 0.8)；
三阈全部锚定既有冻结常数（Q-L05-03③ band / Q-L03-02 最大熵点 0.5 /
Q-L05-05① 伦理分位 0.8），零新自由参数。告警交 L09/L08（C3），**不**触发动作。
"""
from dataclasses import dataclass
from enum import StrEnum

from galatea.subject.affect.ports import DriveKind

__all__ = ["AlertSeverity", "DriveReading", "HomeostaticAlert", "severity_of"]


class AlertSeverity(StrEnum):
    """告警三级（Q-L01-08 L05 侧补裁）。"""

    LOW = "LOW"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


#: 分级阈值（锚定冻结常数：band / 最大熵点 / 伦理分位——见模块 docstring）
SEVERITY_HIGH = 0.5
SEVERITY_CRITICAL = 0.8


def severity_of(error: float, band: float) -> AlertSeverity | None:
    """误差 → 告警级（带内 = None：band 之下为正常波动，不告警）。"""
    if error >= SEVERITY_CRITICAL:
        return AlertSeverity.CRITICAL
    if error >= SEVERITY_HIGH:
        return AlertSeverity.HIGH
    if error > band:
        return AlertSeverity.LOW
    return None


@dataclass(frozen=True, slots=True)
class DriveReading:
    """单驱力读数（belief 值 + set-point + 误差）。"""

    kind: DriveKind
    value: float
    set_point: float
    error: float


@dataclass(frozen=True, slots=True)
class HomeostaticAlert:
    """viability 告警（L05 §2.2 aff.alert；交 L09/L08，不直接触发动作）。"""

    drive: DriveKind
    severity: AlertSeverity
    error: float
    threshold_ref: str
    trend: float            # 误差变化（本拍 − 上拍；正 = 恶化）

    def __post_init__(self) -> None:
        if self.error < 0.0:
            raise ValueError("homeostatic error must be >= 0（单侧定义 Q-L05-02②）")
