"""调制回执与白名单（L03 §4.5/§10 modulation.py；C1 恒拒 → C2 接收面开启）。

白名单（L03 §4.5）：允许改 = 精度权重 w_m / believe_threshold / 竞争窗口长度；
禁止改 = 输入特征、置信度标度、层级、历史信念。

C2 面（Q-L02-02/Q-L05-03③ 派生）：**believe_threshold 接受有界调制**——
界 = 0.5 ± band = [0.4, 0.6]（Q-L03-02 最大熵阈 0.5 + 迟滞带 0.1，零新常数）；
越界 = clip + bound_check=CLIPPED（正常路径非错误；requested/applied 成对呈现，
evaluator 只采信 applied——Q-L02-02②）。precision_weights/competition_window
无 C2 调制源（affect 只发 gain/believe_threshold/salience 三类）——仍拒。
"""
from dataclasses import dataclass


class ModulationRejected(ValueError):
    """无调制源的字段被调制（C1 全字段 / C2 非本档源字段）——拒绝并留痕。"""


class ModulationField:
    """调制字段白名单（L03 §4.5 冻结枚举值）。"""

    PRECISION_WEIGHTS = "precision_weights"
    BELIEVE_THRESHOLD = "believe_threshold"
    COMPETITION_WINDOW = "competition_window"


#: 禁改字段（L03 §4.5）
FORBIDDEN_FIELDS = ("input_features", "confidence_scale", "representation_level", "history")

#: believe_threshold 调制界 = 0.5 ± band（Q-L03-02 + Q-L05-03③）
BELIEVE_THRESHOLD_BOUND: tuple[float, float] = (0.4, 0.6)


@dataclass(frozen=True, slots=True)
class ModulationReceipt:
    """调制回执（C2 因果调制证据之一；accepted=False 即拒绝留痕）。"""

    field: str
    accepted: bool
    reason: str
    requested_value: "float | None" = None
    applied_value: "float | None" = None
    bound_check: str = ""            # IN_BOUND | CLIPPED | ""（拒绝面）


def apply_modulation(field: str, value: object) -> ModulationReceipt:
    """C2 调制入口：believe_threshold 有界接受；其余白名单字段无源恒拒；
    白名单外/禁改字段拒绝留痕（不抛——禁改面恒 False 回执）。"""
    if field in FORBIDDEN_FIELDS:
        return ModulationReceipt(
            field=field, accepted=False,
            reason=f"forbidden field {field!r}（L03 §4.5 恒禁改）",
        )
    if field not in (ModulationField.PRECISION_WEIGHTS, ModulationField.BELIEVE_THRESHOLD,
                     ModulationField.COMPETITION_WINDOW):
        return ModulationReceipt(field=field, accepted=False, reason=f"unknown modulation field {field!r}")
    if field == ModulationField.BELIEVE_THRESHOLD:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return ModulationReceipt(
                field=field, accepted=False,
                reason=f"believe_threshold requires numeric value, got {type(value).__name__}",
            )
        requested = float(value)
        lo, hi = BELIEVE_THRESHOLD_BOUND
        applied = min(max(requested, lo), hi)
        bound_check = "IN_BOUND" if applied == requested else "CLIPPED"
        return ModulationReceipt(
            field=field, accepted=True,
            reason=f"bounded believe_threshold modulation（Q-L02-02②：evaluator 采信 applied）",
            requested_value=requested, applied_value=applied, bound_check=bound_check,
        )
    raise ModulationRejected(
        f"no modulation source for {field!r} at C2（affect 只发 gain/believe_threshold/salience）；"
        f"value={value!r} 拒绝留痕"
    )
