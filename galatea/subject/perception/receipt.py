"""PerceptionReceipt（L03 §2.2 perc.receipt/§10 receipt.py；EVIDENCE_ONLY 审计面）。"""
from dataclasses import dataclass

from galatea.kernel.digest import content_digest


class ReceiptIncomplete(ValueError):
    """回执完整性违规（belief 无回执/回执缺源帧引用）——fail closed。"""


@dataclass(frozen=True, slots=True)
class PerceptionReceipt:
    """知觉回执（L03 §2.2：belief_id, source_frames, cues, modulation_recs, ood_flags, calibration_version）。"""

    belief_id: str
    source_frames: tuple[str, ...]
    cues: tuple[str, ...]
    modulation_receipts: tuple[str, ...]
    ood_flags: tuple[str, ...]
    calibration_version: str
    cycle_id: int

    def __post_init__(self) -> None:
        if not self.belief_id or not self.calibration_version:
            raise ReceiptIncomplete("belief_id and calibration_version required")
        if not self.source_frames and not self.cues:
            raise ReceiptIncomplete(
                f"receipt for {self.belief_id} has no source frames/cues（禁匿名知觉，L03 §8 不变量 2）"
            )

    def digest(self) -> str:
        return content_digest({
            "belief_id": self.belief_id,
            "source_frames": list(self.source_frames),
            "cues": list(self.cues),
            "modulation_receipts": list(self.modulation_receipts),
            "ood_flags": list(self.ood_flags),
            "calibration_version": self.calibration_version,
            "cycle_id": self.cycle_id,
        })


def build_receipt(
    belief_id: str, source_frames: tuple[str, ...], calibration_version: str,
    cycle_id: int, cues: tuple[str, ...] = (), ood_flags: tuple[str, ...] = (),
) -> PerceptionReceipt:
    """回执构建（源帧缺失即 ReceiptIncomplete——fail closed）。"""
    return PerceptionReceipt(
        belief_id=belief_id, source_frames=source_frames, cues=cues,
        modulation_receipts=(), ood_flags=ood_flags,
        calibration_version=calibration_version, cycle_id=cycle_id,
    )


def audit_receipts(
    beliefs: tuple[str, ...], receipts: tuple[PerceptionReceipt, ...],
) -> None:
    """证据侧审计：belief−receipt 集合差即违规（消融检出面：移除回执必须可检）。"""
    belief_ids = set(beliefs)
    receipt_ids = {r.belief_id for r in receipts}
    if belief_ids != receipt_ids:
        raise ReceiptIncomplete(
            f"perception receipt audit failed: beliefs−receipts={sorted(belief_ids - receipt_ids)} "
            f"receipts−beliefs={sorted(receipt_ids - belief_ids)}"
        )
