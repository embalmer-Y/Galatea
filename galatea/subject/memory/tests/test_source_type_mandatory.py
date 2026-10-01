"""来源类型强制（L06 §10 test_source_type_mandatory.py）。

断言：MemoryItem 必带 source_type（枚举六类冻结，构造缺省即 TypeError）；
六类全部可构造；UNKNOWN 来源允许编码但在连续性主张消费侧受限（L06 §2.2）。
"""
import pytest

from galatea.kernel.packet import RepresentationLevel
from galatea.subject.memory.items import MemoryItem
from galatea.subject.memory.ports import MemorySubsystem, SourceType


def _item(source: SourceType) -> MemoryItem:
    return MemoryItem(
        item_id="i1",
        subsystem=MemorySubsystem.EPISODIC,
        source_type=source,
        content_ref="ev.1",
        representation_level=RepresentationLevel.RECEIVED,
        strength=0.5,
        created_cycle=0,
        last_access_cycle=0,
    )


def test_source_type_is_mandatory_field() -> None:
    with pytest.raises(TypeError):
        MemoryItem(  # type: ignore[call-arg]
            item_id="i1",
            subsystem=MemorySubsystem.EPISODIC,
            content_ref="ev.1",
            representation_level=RepresentationLevel.RECEIVED,
            strength=0.5,
            created_cycle=0,
            last_access_cycle=0,
        )


def test_all_six_source_types_constructible() -> None:
    assert len(SourceType) == 6
    for source in SourceType:
        assert _item(source).source_type is source


def test_unknown_source_semantics_recorded() -> None:
    """UNKNOWN 来源可编码，但 L06 §2.2 禁其用于连续性主张/归属证据——枚举值语义钉死。"""
    assert _item(SourceType.UNKNOWN).source_type is SourceType.UNKNOWN
    assert SourceType.LANGUAGE_INPUT.value == "LANGUAGE_INPUT"   # D-13 执法面引用
