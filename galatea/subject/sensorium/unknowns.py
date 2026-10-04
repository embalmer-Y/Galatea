"""Sensorium typed unknown 产生点（L02 §6/§10 unknowns.py；统一走 L00 类型）。

纪律：任何失败不得改写为"主体没有感觉到"（L02 §6）；全部 Unknown 带 evidence_refs
与 detected_by；禁裸 None 充当不确定性（L00 §6.1）。
"""
from galatea.kernel.unknown import Unknown, UnknownReason

_DETECTOR = "sensorium"


def missing_signal(evidence_refs: tuple[str, ...], detail: str, virtual_time: int) -> Unknown:
    """模态信号缺失/窗内未到（L02 §6：部分对齐发布，禁补零）。"""
    return Unknown(
        reason=UnknownReason.MISSING_SIGNAL, evidence_refs=evidence_refs,
        detail=detail, detected_by=_DETECTOR, virtual_time=virtual_time,
    )


def insufficient_observation(evidence_refs: tuple[str, ...], detail: str, virtual_time: int) -> Unknown:
    """窗超时部分对齐/超回溯深度的迟到信号/首帧差分无前值。"""
    return Unknown(
        reason=UnknownReason.INSUFFICIENT_OBSERVATION, evidence_refs=evidence_refs,
        detail=detail, detected_by=_DETECTOR, virtual_time=virtual_time,
    )


def calibration_uncertain(evidence_refs: tuple[str, ...], detail: str, virtual_time: int) -> Unknown:
    """校准/质量退化面（snr 占位、迟到 revision 置信降级、通道损坏标记）。"""
    return Unknown(
        reason=UnknownReason.CALIBRATION_UNCERTAIN, evidence_refs=evidence_refs,
        detail=detail, detected_by=_DETECTOR, virtual_time=virtual_time,
    )


def ood(evidence_refs: tuple[str, ...], detail: str, virtual_time: int) -> Unknown:
    """原始信号特征越域（L02 §6：照常形成并标记，不推断、不丢弃）。"""
    return Unknown(
        reason=UnknownReason.OOD, evidence_refs=evidence_refs,
        detail=detail, detected_by=_DETECTOR, virtual_time=virtual_time,
    )
