from pathlib import Path

"""subject_memory.db 权限（L06 §10 test_memory_db_permission.py；L00 §3 三库分离）。

断言：episodes 表唯一写者 = memory（kernel _OWNERSHIP 机械校验）；非 memory
写者（orchestrator/recorder）open_writer 即 OwnershipViolation；容量上界冻结值生效。
"""
import pytest

from galatea.kernel.packet import RepresentationLevel
from galatea.kernel.state import OwnershipViolation, StoreName, Stores
from galatea.subject.memory.encode import encode_episodic
from galatea.subject.memory.ports import MemorySubsystem, SourceType
from galatea.subject.memory.store import MemoryStore, MemoryStoreViolation, load_m2_continuity_profile

PROFILE = load_m2_continuity_profile()


def test_memory_is_single_writer(tmp_path: Path) -> None:
    stores = Stores(tmp_path / "stores")
    store = MemoryStore(stores)   # 正常打开：owner=memory
    encode_episodic(store, PROFILE, "ep.1", "ev.1", RepresentationLevel.RECEIVED,
                    SourceType.SELF_GENERATED, 0)
    assert store.count(MemorySubsystem.EPISODIC) == 1
    stores.close()


def test_orchestrator_cannot_write_memory_db(tmp_path: Path) -> None:
    """L00 §3 禁止写入路径 orchestrator → subject memory（kernel 机械校验）。"""
    stores = Stores(tmp_path / "stores")
    with pytest.raises(OwnershipViolation, match="single writer"):
        stores.open_writer(
            StoreName.SUBJECT_MEMORY,
            "episodes",
            "orchestrator",
        )
    stores.close()


def test_episodic_capacity_frozen_bound(tmp_path: Path) -> None:
    """Q-G00-11：episodic_capacity=128 上界由构造侧强制（溢出策略 C2 裁决）。"""
    stores = Stores(tmp_path / "stores")
    store = MemoryStore(stores)
    assert PROFILE.memory_episodic_capacity == 128   # 冻结值锚
    for i in range(PROFILE.memory_episodic_capacity):
        encode_episodic(store, PROFILE, f"ep.{i:04d}", f"ev.{i}", RepresentationLevel.RECEIVED,
                        SourceType.SELF_GENERATED, i)
    with pytest.raises(MemoryStoreViolation, match="capacity"):
        encode_episodic(store, PROFILE, "ep.over", "ev.over", RepresentationLevel.RECEIVED,
                        SourceType.SELF_GENERATED, 999)
    stores.close()
