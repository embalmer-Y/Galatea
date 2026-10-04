"""质量估计（L02 §4.1/§4.2 quality.py；Q-G00-12④ C0 度量纲）。

C0 面：completeness（声明字段实收占比，[0,1]）+ corruption_flags（证据侧损坏标记转写）；
snr_est 占位（跨模态归一标度 Q-L02-04 归 C1）。越域值照常形成并标 OOD（不丢弃）。
"""
from galatea.kernel.unknown import Unknown
from galatea.subject.sensorium.unknowns import ood
from galatea.subject.sensorium.ports import QualityMetrics


def quality_for(present_fields: int, expected_fields: int, corruption_flags: tuple[str, ...]) -> QualityMetrics:
    """completeness = present/expected（expected>0；越界 fail-closed 由 QualityMetrics 守卫）。"""
    if expected_fields <= 0:
        raise ValueError("expected_fields must be positive")
    return QualityMetrics(
        completeness=min(1.0, present_fields / expected_fields),
        corruption_flags=corruption_flags,
    )


def ood_if_out_of_unit(value: float, evidence_refs: tuple[str, ...], virtual_time: int) -> "list[Unknown]":
    """单位区间外的水平值 → OOD 标记（照常形成，不推断不丢弃，L02 §6）。"""
    if 0.0 <= value <= 1.0:
        return []
    return [
        ood(
            evidence_refs,
            f"level value {value} outside [0,1]（原始信号越域：照常形成并标记）",
            virtual_time,
        )
    ]
