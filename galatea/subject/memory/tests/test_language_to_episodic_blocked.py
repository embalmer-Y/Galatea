from pathlib import Path

"""语言→episodic 经历字段禁写（L06 §10 test_language_to_episodic_blocked.py；D-13）。"""
import pytest

from galatea.kernel.packet import RepresentationLevel
from galatea.kernel.state import Stores
from galatea.subject.memory.encode import encode_episodic
from galatea.subject.memory.ports import MemorySubsystem, SourceType
from galatea.subject.memory.store import MemoryStore, MemoryStoreViolation, load_m2_continuity_profile

PROFILE = load_m2_continuity_profile()


def test_language_input_cannot_encode_episodic(tmp_path: Path) -> None:
    """D-13：语言不能写 episodic 经历（encode 面即拒，非事后清洗）。"""
    stores = Stores(tmp_path / "stores")
    store = MemoryStore(stores)
    with pytest.raises(MemoryStoreViolation, match="LANGUAGE_INPUT"):
        encode_episodic(store, PROFILE, "ep.lang", "stmt.text", RepresentationLevel.EXTERNAL_STATEMENT,
                        SourceType.LANGUAGE_INPUT, 0)
    assert store.count(MemorySubsystem.EPISODIC) == 0
    stores.close()


def test_language_content_may_live_outside_experience(tmp_path: Path) -> None:
    """语言内容经非经历子系统承载不在本切片范围（working 允许——L06 §2.1 mem.encode_working 随源层级）。"""
    from galatea.subject.memory.encode import encode_working

    stores = Stores(tmp_path / "stores")
    store = MemoryStore(stores)
    item = encode_working(store, PROFILE, "w.lang", "stmt.text", RepresentationLevel.EXTERNAL_STATEMENT,
                          SourceType.LANGUAGE_INPUT, 0)
    assert item.source_type is SourceType.LANGUAGE_INPUT   # 来源类型如实标注（不冒充经历）
    stores.close()
