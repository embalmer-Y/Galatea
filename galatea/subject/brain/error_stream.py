"""统一误差流（L04 §10 error_stream.py；HLD §15.3「L02 pred_error → 梯度最底层」承载）。

输入合同 = 主体平面形成帧唯一（Q-L04-12④ input_plane: subject_formed_frames_only）；
特征空间 = L02 flatten_frame 域的唯一复用（Q-L02-06：特征空间由形成层唯一决定，
禁评价侧自造特征工程）——本模块只做**模态槽位拼接**，零变换零阈值：

    [EXT_WINDOW 25 ｜ EXT_EVENTS 2 ｜ INTERO 4 ｜ PROPRIO 4]  = 35 维/拍

层级化纪律（Q-L09-08）：感觉层/知觉层/模型层误差三分立不合并——本流是脑核
（神经世界模型）的训练信号面，消费的是形成帧（SENSORY_FORMED 层），不读
L03/L04 分量，不替代任何既有误差面。

缺模态拍（对齐窗边界）→ 该拍跳过不构造（禁伪造零向量，C0 成规）；
事件帧缺席 → 事件槽零填充（事件缺席是事实而非未知）。
"""
from __future__ import annotations

from typing import Sequence

from galatea.subject.c1profile import EVENT_KINDS, INTERO_SCALARS, ORIENTATION_TOKENS
from galatea.subject.sensorium.ports import (
    ExtEventFeatures,
    ExtLocalObsFeatures,
    InteroSensations,
    ProprioFeatures,
    SensoryFrame,
)

#: 槽位布局（维度域由形成层唯一决定——各槽序 = flatten_frame 各模态展平序）
EXT_WINDOW_DIM = 25          # 5×5 窗行优先（Q-L01-01）
EXT_EVENT_DIM = len(EVENT_KINDS)
INTERO_DIM = len(INTERO_SCALARS)
PROPRIO_DIM = len(ORIENTATION_TOKENS)
INPUT_DIM = EXT_WINDOW_DIM + EXT_EVENT_DIM + INTERO_DIM + PROPRIO_DIM

#: energy_level 在拼接向量中的下标（INTERO 槽首标量；Q-L02-05⑤ 派生差分的基量）
ENERGY_LEVEL_INDEX = EXT_WINDOW_DIM + EXT_EVENT_DIM


class ErrorStreamViolation(ValueError):
    """统一误差流输入合同不符（重复模态帧/基模态缺席）——fail closed。"""


def build_stream_vector(frames: Sequence[SensoryFrame]) -> tuple[int, tuple[float, ...]]:
    """单拍形成帧 → 35 维输入向量（返回 (effective_time, vector)）。

    合同：基三模态（窗/内感受/本体）各恰一帧；事件帧零或一帧。违反 = 拒。
    """
    window: ExtLocalObsFeatures | None = None
    events: ExtEventFeatures | None = None
    intero: InteroSensations | None = None
    proprio: ProprioFeatures | None = None
    effective_time: int | None = None
    for frame in frames:
        if isinstance(frame.features, ExtLocalObsFeatures):
            if window is not None:
                raise ErrorStreamViolation(f"duplicate EXT window frame at {frame.effective_time}")
            window = frame.features
        elif isinstance(frame.features, ExtEventFeatures):
            if events is not None:
                raise ErrorStreamViolation(f"duplicate EXT event frame at {frame.effective_time}")
            events = frame.features
        elif isinstance(frame.features, InteroSensations):
            if intero is not None:
                raise ErrorStreamViolation(f"duplicate INTERO frame at {frame.effective_time}")
            intero = frame.features
        elif isinstance(frame.features, ProprioFeatures):
            if proprio is not None:
                raise ErrorStreamViolation(f"duplicate PROPRIO frame at {frame.effective_time}")
            proprio = frame.features
        else:
            raise ErrorStreamViolation(
                f"frame {frame.frame_id} has no unified error-stream slot"
                "（语言帧等非脑核输入面禁入——Q-L12-06① 同族）")
        effective_time = frame.effective_time
    if window is None or intero is None or proprio is None:
        raise ErrorStreamViolation(
            "base modality missing（对齐窗边界拍——跳过不构造，禁伪造零向量）")
    if effective_time is None:
        raise ErrorStreamViolation("no frames")

    vector = [0.0] * INPUT_DIM
    flat_window = [float(v) for row in window.window for v in row]
    if len(flat_window) != EXT_WINDOW_DIM:
        raise ErrorStreamViolation(
            f"window dim {len(flat_window)} != {EXT_WINDOW_DIM}（特征空间由形成层唯一决定）")
    vector[0:EXT_WINDOW_DIM] = flat_window
    if events is not None:
        for offset, kind in enumerate(EVENT_KINDS):
            vector[EXT_WINDOW_DIM + offset] = 1.0 if kind in events.events else 0.0
    intero_values: dict[str, float] = {
        "energy_level": intero.energy_level,
        "integrity_level": intero.integrity_level,
        "damage_event": 1.0 if intero.damage_event else 0.0,
        "energy_depleted": 1.0 if intero.energy_depleted else 0.0,
    }
    for offset, name in enumerate(INTERO_SCALARS):
        vector[EXT_WINDOW_DIM + EXT_EVENT_DIM + offset] = intero_values[name]
    for offset, token in enumerate(ORIENTATION_TOKENS):
        vector[EXT_WINDOW_DIM + EXT_EVENT_DIM + INTERO_DIM + offset] = (
            1.0 if proprio.orientation == token else 0.0)
    return effective_time, tuple(vector)
