"""统一误差流测试（Q-L02-06 特征空间唯一复用；模态槽位拼接合同）。"""
import pytest

from galatea.subject.brain.error_stream import (
    ENERGY_LEVEL_INDEX,
    INPUT_DIM,
    ErrorStreamViolation,
    build_stream_vector,
)
from galatea.subject.brain.tests.conftest import (
    base_frames,
    event_frame,
    intero_frame,
    proprio_frame,
    window_frame,
)
from galatea.subject.sensorium.pred_error import flatten_frame


def test_vector_layout_35_dims() -> None:
    """35 维槽位布局：[窗 25 | 事件 2 | 内感受 4 | 本体 4]。"""
    t, vector = build_stream_vector(base_frames(7, energy=0.62, center=0.9))
    assert t == 7
    assert len(vector) == INPUT_DIM  # 35
    assert vector[12] == pytest.approx(0.9)          # 窗中心格（行优先）
    assert all(v == 0.0 for v in vector[25:27])      # 事件槽零填充（缺席是事实）
    assert vector[ENERGY_LEVEL_INDEX] == pytest.approx(0.62)
    assert vector[31:35] == (1.0, 0.0, 0.0, 0.0)     # N 朝向 one-hot


def test_feature_space_matches_flatten() -> None:
    """槽位序与 L02 flatten_frame 各模态展平序逐位一致（唯一复用——零自造）。"""
    frames = base_frames(3, energy=0.42)
    _t, vector = build_stream_vector(frames)
    window = next(f for f in frames if f.modality.value == "EXT_LOCAL_OBS")
    intero = next(f for f in frames if f.modality.value == "INTERO")
    proprio = next(f for f in frames if f.modality.value == "PROPRIO")
    assert vector[0:25] == flatten_frame(window)
    assert vector[27:31] == flatten_frame(intero)
    assert vector[31:35] == flatten_frame(proprio)


def test_event_one_hot() -> None:
    """事件帧在场 → 事件槽 one-hot（EVENT_KINDS 序）。"""
    frames = [*base_frames(5), event_frame(5, ("energy_depleted",))]
    _t, vector = build_stream_vector(frames)
    assert vector[25] == 1.0 and vector[26] == 0.0


def test_duplicate_modality_rejected() -> None:
    """重复模态帧 = 拒（fail closed）。"""
    frames = [*base_frames(2), window_frame(2)]
    with pytest.raises(ErrorStreamViolation, match="duplicate"):
        build_stream_vector(frames)


def test_missing_base_modality_rejected() -> None:
    """基模态缺席（对齐边界拍/空帧组）= 拒——禁伪造零向量。"""
    with pytest.raises(ErrorStreamViolation, match="base modality missing"):
        build_stream_vector([intero_frame(1), proprio_frame(1)])
    with pytest.raises(ErrorStreamViolation, match="base modality missing"):
        build_stream_vector([])


def test_empty_frames_rejected() -> None:
    with pytest.raises(ErrorStreamViolation):
        build_stream_vector([event_frame(1, ())])   # 仅事件帧——基模态缺席
