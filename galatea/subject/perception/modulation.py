"""调制回执与白名单（L03 §4.5/§10 modulation.py）。

C1 无调制源（L05 归 C2）——任何调制尝试即拒（ModulationRejected），回执留痕。
白名单（C2 生效时适用，L03 §4.5）：允许改 = 精度权重 w_m / believe_threshold /
竞争窗口长度；禁止改 = 输入特征、置信度标度、层级、历史信念。
"""
from dataclasses import dataclass
from enum import StrEnum


class ModulationRejected(ValueError):
    """调制面在 C1 不存在（L05 归 C2）——拒绝并留痕。"""


class ModulationField(StrEnum):
    """调制字段白名单（L03 §4.5；C1 全部不可用——无调制源）。"""

    PRECISION_WEIGHTS = "precision_weights"
    BELIEVE_THRESHOLD = "believe_threshold"
    COMPETITION_WINDOW = "competition_window"


FORBIDDEN_FIELDS = ("input_features", "confidence_scale", "representation_level", "history")


@dataclass(frozen=True, slots=True)
class ModulationReceipt:
    """调制回执（C2 因果调制证据之一；C1 仅拒绝面回执）。"""

    field: str
    accepted: bool
    reason: str


def apply_modulation(field: str, value: object) -> ModulationReceipt:
    """C1 调制入口：恒拒（无调制源）；白名单外字段额外记违规理由。"""
    if field in FORBIDDEN_FIELDS:
        return ModulationReceipt(field=field, accepted=False, reason=f"forbidden field {field!r}（L03 §4.5）")
    if field not in (m.value for m in ModulationField):
        return ModulationReceipt(field=field, accepted=False, reason=f"unknown modulation field {field!r}")
    raise ModulationRejected(
        f"modulation source does not exist at C1（L05 归 C2）；field={field!r} value={value!r} 拒绝留痕"
    )
