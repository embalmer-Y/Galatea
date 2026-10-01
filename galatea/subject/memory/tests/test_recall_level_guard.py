"""层级守卫（L06 §10 test_recall_level_guard.py；L06 §1：回忆恒 RECALLED，禁提升）。"""
import pytest

from galatea.kernel.packet import RepresentationLevel
from galatea.subject.memory.ports import (
    MemoryLevelViolation,
    MemorySubsystem,
    RecalledContent,
    SourceType,
    assert_recall_level,
)


def _recalled() -> RecalledContent:
    return RecalledContent(
        memory_ref="i1",
        subsystem=MemorySubsystem.EPISODIC,
        source_type=SourceType.SELF_GENERATED,
        content_ref="ev.1",
        reliability=0.5,
        retrieved_at=10,
    )


def test_recalled_level_immutable_recalled() -> None:
    content = _recalled()
    assert content.level is RepresentationLevel.RECALLED


def test_recalled_content_cannot_be_relabelled() -> None:
    """level 为 init=False 恒定字段：构造注入即 TypeError（不可指定）；冻结面禁止改写。"""
    with pytest.raises(TypeError):
        RecalledContent(
            memory_ref="i2",
            subsystem=MemorySubsystem.EPISODIC,
            source_type=SourceType.PERCEIVED,
            content_ref="ev.2",
            reliability=0.5,
            retrieved_at=10,
            level=RepresentationLevel.PERCEIVED,  # type: ignore[arg-type]  # init=False 不可注入
        )
    content = _recalled()
    with pytest.raises(Exception):   # frozen dataclass：任何原地改写被拒
        content.level = RepresentationLevel.PERCEIVED  # type: ignore[misc]


def test_assert_recall_level_rejects_promotion() -> None:
    """RECALLED 禁提升为知觉/事实（下游消费面守卫）。"""
    assert_recall_level(RepresentationLevel.RECALLED)  # 合法
    for level in (RepresentationLevel.PERCEIVED, RepresentationLevel.RECEIVED, RepresentationLevel.EXTERNAL_STATEMENT):
        with pytest.raises(MemoryLevelViolation):
            assert_recall_level(level)


def test_reliability_bounded() -> None:
    with pytest.raises(ValueError, match="reliability"):
        RecalledContent(
            memory_ref="i3",
            subsystem=MemorySubsystem.EPISODIC,
            source_type=SourceType.SELF_GENERATED,
            content_ref="ev.3",
            reliability=1.5,
            retrieved_at=10,
        )
