"""广播投递与读取回执（L07 §4.2/§10 broadcast.py）。

广播是**投递**（非确认协议——禁重试禁重发，Q-L07-03③）；每读者必回 ReadReceipt
（含读前/读后状态摘要 digest + effect_declared）；超时 = N2 = 2 cycles
（Q-L07-03①——下一竞争拍未收即 ReceiptMissing，该读者不计入 separated_modules，
帧本身不可变不受影响）；**缺回执的广播不得用于任何"全局访问"主张**。
"""
from dataclasses import dataclass

__all__ = ["ReadReceipt", "ReceiptMissingRecord", "broadcast_targets", "settle_receipts"]


@dataclass(frozen=True, slots=True)
class ReadReceipt:
    """读取回执（L07 §2.1：读者 + 读前后状态 digest + 效果声明）。"""

    frame_id: str
    reader_module: str
    read_at: int
    pre_state_digest: str
    post_state_digest: str
    effect_declared: bool

    def __post_init__(self) -> None:
        if not self.reader_module:
            raise ValueError("anonymous reader rejected")
        if self.pre_state_digest == self.post_state_digest and self.effect_declared:
            raise ValueError(
                "effect_declared requires digest change（pre==post 而宣称效果 = 不实回执，拒收）"
            )


@dataclass(frozen=True, slots=True)
class ReceiptMissingRecord:
    """缺回执留痕（指标计数 + 该帧访问主张作废——不改帧）。"""

    frame_id: str
    reader_module: str
    deadline_cycle: int


def broadcast_targets(frame_id: str, readers: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    """投递清单（(frame_id, reader) 序对——确定性 = readers 序）。"""
    if len(set(readers)) != len(readers):
        raise ValueError("duplicate readers in broadcast list")
    return tuple((frame_id, r) for r in readers)


def settle_receipts(
    frame_cycle: int,
    frame_ttl: int,
    readers: tuple[str, ...],
    receipts: tuple[ReadReceipt, ...],
    timeout_cycles: int,
    now_cycle: int,
    frame_id: str,
) -> tuple[tuple[ReadReceipt, ...], tuple[ReceiptMissingRecord, ...]]:
    """回执结算（deadline = 广播拍 + 超时 N2；超时未收 = ReceiptMissing）。"""
    got = {r.reader_module: r for r in receipts if r.frame_id == frame_id}
    on_time: list[ReadReceipt] = []
    missing: list[ReceiptMissingRecord] = []
    deadline = frame_cycle + timeout_cycles
    del frame_ttl  # 帧生命期语义由 frame.expired_at 承载（本函数只结算回执）
    for reader in readers:
        rec = got.get(reader)
        if rec is not None and rec.read_at <= deadline:
            on_time.append(rec)
        elif now_cycle >= deadline:
            missing.append(ReceiptMissingRecord(
                frame_id=frame_id, reader_module=reader, deadline_cycle=deadline,
            ))
    return tuple(on_time), tuple(missing)
