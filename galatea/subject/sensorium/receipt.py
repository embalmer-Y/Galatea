"""FormationReceipt 构造与发布（L02 §2.2/§10 receipt.py；证据侧 EVIDENCE_ONLY）。

纪律：每帧必有回执；回执字段完整（缺字段 = ReceiptIncomplete，形成判为不成立）；
回执 digest 与帧 digest 双绑定（可审计：帧改写 → digest 失配检出）。
"""
from dataclasses import dataclass

from galatea.kernel.digest import content_digest
from galatea.kernel.unknown import Unknown
from galatea.subject.sensorium.ports import GainReceipt, QualityMetrics, SensoryFrame


class ReceiptIncomplete(ValueError):
    """回执必备字段缺失（L02 §7 contract：FormationReceipt 必备字段完整）。"""


@dataclass(frozen=True, slots=True)
class FormationReceipt:
    """形成回执（frame_id/source_received_ids/calibration_version/alignment_offset/
    quality/gain_applied/unknowns 全量；L02 §2.2 evd 契约位）。"""

    frame_id: str
    frame_digest: str
    source_received_ids: tuple[str, ...]
    calibration_version: str
    alignment_offset: int
    quality: QualityMetrics
    gain_applied: float
    gain_receipt: GainReceipt
    unknowns: tuple[Unknown, ...]
    revision_of: str | None
    digest: str = ""

    def __post_init__(self) -> None:
        missing = [
            name for name, value in (
                ("frame_id", self.frame_id), ("frame_digest", self.frame_digest),
                ("source_received_ids", self.source_received_ids),
                ("calibration_version", self.calibration_version),
                ("gain_applied", self.gain_applied), ("gain_receipt", self.gain_receipt),
            ) if not value
        ]
        if missing:
            raise ReceiptIncomplete(f"receipt for {self.frame_id!r}: missing {missing}")
        if self.gain_receipt.frame_id != self.frame_id:
            raise ReceiptIncomplete(
                f"receipt gain binding mismatch: {self.gain_receipt.frame_id!r} != {self.frame_id!r}"
            )
        if not self.digest:
            object.__setattr__(self, "digest", content_digest(
                {
                    "frame_id": self.frame_id, "frame_digest": self.frame_digest,
                    "source_received_ids": list(self.source_received_ids),
                    "calibration_version": self.calibration_version,
                    "alignment_offset": self.alignment_offset,
                    "gain_applied": self.gain_applied,
                    "unknowns": [{"reason": u.reason.value, "detail": u.detail} for u in self.unknowns],
                    "revision_of": self.revision_of,
                }
            ))


def build_receipt(frame: SensoryFrame, gain_receipt: GainReceipt) -> FormationReceipt:
    """帧 → 回执（一一对应；audit 面断言无帧无回执、无回执无帧）。"""
    return FormationReceipt(
        frame_id=frame.frame_id,
        frame_digest=frame.content_digest,
        source_received_ids=frame.source_received_ids,
        calibration_version=frame.calibration_version,
        alignment_offset=frame.alignment_offset,
        quality=frame.quality,
        gain_applied=frame.gain.applied_factor,
        gain_receipt=gain_receipt,
        unknowns=frame.uncertainty,
        revision_of=frame.revision_of,
    )
