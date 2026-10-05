"""ModelUpdateReceipt（L04 §2.2 model.receipt/§10 receipt.py；EVIDENCE_ONLY 审计面）。"""
from dataclasses import dataclass, field

from galatea.kernel.digest import content_digest


class ModelReceiptIncomplete(ValueError):
    """模型更新回执完整性违规（inputs 缺失/无版本）——fail closed。"""


@dataclass(frozen=True, slots=True)
class ModelUpdateReceipt:
    """模型更新回执（L04 §2.2：belief_id, inputs[], update_rule_version, modulation_recs[], unknowns[]）。"""

    model: str                      # world | body | self
    belief_id: str
    inputs: tuple[str, ...]
    update_rule_version: str
    modulation_receipts: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    cycle_id: int = 0
    extra: tuple[tuple[str, str], ...] = field(default=())

    def __post_init__(self) -> None:
        if not self.belief_id or not self.update_rule_version or not self.inputs:
            raise ModelReceiptIncomplete(
                "model update receipt requires belief_id, update_rule_version, inputs"
            )

    def digest(self) -> str:
        return content_digest({
            "model": self.model,
            "belief_id": self.belief_id,
            "inputs": list(self.inputs),
            "update_rule_version": self.update_rule_version,
            "cycle_id": self.cycle_id,
        })
