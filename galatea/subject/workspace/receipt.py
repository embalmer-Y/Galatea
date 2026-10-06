"""WorkspaceReceipt（L07 §2.2/§10 receipt.py——证据侧回执聚合）。"""
from dataclasses import dataclass

__all__ = ["WorkspaceReceipt"]


@dataclass(frozen=True, slots=True)
class WorkspaceReceipt:
    """帧级回执（modulation 回执引用 + policy 引用 + RNG 流引用——确定性 none_c2）。"""

    frame_id: str
    cycle_id: int
    modulation_receipt_ids: tuple[str, ...]
    policy_ref: str
    rng_stream_ref: str = "none_c2"
