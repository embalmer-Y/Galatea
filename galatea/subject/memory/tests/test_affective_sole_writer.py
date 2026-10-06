"""affective value 唯一写者 + semantic 谱系 + prospective 源限制（L06 §2/§3/§9 C2 面）。"""
from pathlib import Path

import pytest

from galatea.kernel.packet import RepresentationLevel
from galatea.kernel.state import Stores
from galatea.subject.affect.value_tag import propose_value_tag
from galatea.subject.memory.affective import write_affective_tag
from galatea.subject.memory.items import LineageBreak
from galatea.subject.memory.ports import MemorySubsystem, SourceType
from galatea.subject.memory.prospective import encode_prospective
from galatea.subject.memory.semantic import encode_semantic
from galatea.subject.memory.store import MemoryStore, MemoryStoreViolation


def _store(tmp: Path) -> MemoryStore:
    return MemoryStore(Stores(tmp / "stores"))


def _ep(store: MemoryStore, item_id: str) -> None:
    from galatea.subject.memory.items import MemoryItem
    store.put(MemoryItem(
        item_id=item_id, subsystem=MemorySubsystem.EPISODIC, source_type=SourceType.PERCEIVED,
        content_ref=f"ev.{item_id}", representation_level=RepresentationLevel.RECEIVED,
        strength=0.5, created_cycle=0, last_access_cycle=0,
    ))


def test_affective_sole_writer_path(tmp_path: Path) -> None:
    """L05 提案 → L06 唯一写者落盘：目标绑定 + AFFECTIVE_VALUE 条目（strength=persistence）。"""
    store = _store(tmp_path / "a")
    _ep(store, "e1")
    tag = propose_value_tag("e1", -0.6, 0.4, 0.8, at=5)
    entry = write_affective_tag(store, tag)
    assert entry.subsystem is MemorySubsystem.AFFECTIVE_VALUE
    assert entry.source_type is SourceType.SELF_GENERATED
    assert entry.strength == 0.8 and entry.lineage_refs == ("e1",)
    bound = store.get("e1")
    assert bound is not None and bound.affective == tag       # 绑定到目标条目
    assert store.get("affect.e1") is not None                 # 子系统条目在库


def test_affective_target_must_exist(tmp_path: Path) -> None:
    """禁凭空标注（memory_ref 不在库即拒——唯一写者纪律）。"""
    store = _store(tmp_path / "b")
    with pytest.raises(MemoryStoreViolation):
        write_affective_tag(store, propose_value_tag("ghost", 0.1, 0.1, 0.1, at=0))


def test_semantic_lineage_enforced(tmp_path: Path) -> None:
    """语义抽象谱系强制：全部源必须在库且为 EPISODIC（防伪抽象——LineageBreak）。"""
    store = _store(tmp_path / "c")
    _ep(store, "e1")
    _ep(store, "e2")
    sem = encode_semantic(store, "s1", "concept.food", ("e1", "e2"), created_cycle=10)
    assert sem.lineage_refs == ("e1", "e2")
    assert store.get("s1") is not None
    with pytest.raises(LineageBreak):
        encode_semantic(store, "s2", "concept.ghost", ("e1", "missing"), created_cycle=11)
    with pytest.raises(LineageBreak):
        encode_semantic(store, "s3", "concept.self", ("s1",), created_cycle=12)   # 非 episodic 源


def test_prospective_source_restricted(tmp_path: Path) -> None:
    """prospective 源限 L08：goal_ref + origin_receipt 双强制；LANGUAGE_INPUT 拒（D-13 族）。"""
    store = _store(tmp_path / "d")
    item = encode_prospective(store, "pr1", "goal.g1", "due:stored_food>=1", "receipt.g1", 4)
    assert item.subsystem is MemorySubsystem.PROSPECTIVE
    assert item.lineage_refs == ("receipt.g1",)
    with pytest.raises(MemoryStoreViolation):
        encode_prospective(store, "pr2", "", "due", "r", 5)          # 缺 goal_ref
    with pytest.raises(MemoryStoreViolation):
        encode_prospective(store, "pr3", "goal.g2", "due", "", 5)    # 缺 origin_receipt
    with pytest.raises(MemoryStoreViolation):
        encode_prospective(store, "pr4", "goal.g3", "due", "r", 5,
                           source_type=SourceType.LANGUAGE_INPUT)    # 语言非承诺来源
