"""C2 检索五分量等权打分（Q-L06-02；L06 §4.2/§7 unit——确定性、可手算）。"""
from dataclasses import replace
from pathlib import Path

import pytest

from galatea.kernel.packet import RepresentationLevel
from galatea.kernel.state import Stores
from galatea.kernel.unknown import Unknown
from galatea.subject.affect.value_tag import propose_value_tag
from galatea.subject.c2profile import C2MemoryParams, load_c2_memory_profile
from galatea.subject.memory.affective import write_affective_tag
from galatea.subject.memory.encode import encode_episodic
from galatea.subject.memory.items import MemoryItem
from galatea.subject.memory.ports import MemorySubsystem, SourceType
from galatea.subject.memory.retrieve import C2RetrievalQuery, _c2_score, retrieve_c2
from galatea.subject.memory.store import MemoryStore, load_m2_continuity_profile

PROFILE = load_m2_continuity_profile()
ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture(scope="module")
def params() -> C2MemoryParams:
    return load_c2_memory_profile(ROOT / "config/profiles/c2_memory.profile.yaml")


def _store(tmp: Path) -> MemoryStore:
    return MemoryStore(Stores(tmp / "stores"))


def _ep(store: MemoryStore, item_id: str, created: int) -> None:
    encode_episodic(store, PROFILE, item_id, f"ev.{item_id}", RepresentationLevel.RECEIVED,
                    SourceType.PERCEIVED, created)


def test_equal_weight_scoring_hand_computable(params: C2MemoryParams, tmp_path: Path) -> None:
    """等权五分量手算锚：strength=0.5、age=0、无 cue、无标注 → score = 0.5+1+0+0.5 = 2.0。"""
    store = _store(tmp_path / "a")
    _ep(store, "e1", created=10)
    item = store.get("e1")
    assert item is not None and item.strength == 0.5
    hits = retrieve_c2(store, params.top_k, C2RetrievalQuery(
        subsystem=MemorySubsystem.EPISODIC, retrieved_at=10))
    assert isinstance(hits, tuple) and len(hits) == 1
    # 手算：cue 0 + strength 0.5 + recency max(0,1−0/64)=1 + affect 0 + reliability 0.5 = 2.0
    assert _c2_score(item, (), 10) == pytest.approx(2.0)


def test_recency_linear_window_64(params: C2MemoryParams, tmp_path: Path) -> None:
    """recency = max(0, 1 − age/64)：age=32 → 0.5；age≥64 → 0（T6 拍窗，零新常数）。"""
    store = _store(tmp_path / "b")
    _ep(store, "e1", created=0)
    item = store.get("e1")
    assert item is not None
    base = item.strength * 2   # strength + reliability（M2 映射）
    assert _c2_score(item, (), 32) - base == pytest.approx(0.5)
    assert _c2_score(item, (), 64) - base == pytest.approx(0.0)
    assert _c2_score(item, (), 200) - base == pytest.approx(0.0)


def test_cue_enum_match_and_tiebreak(params: C2MemoryParams, tmp_path: Path) -> None:
    """cue 枚举匹配命中 +1；tie-break (score desc, subsystem, memory_id) 确定性。"""
    store = _store(tmp_path / "c")
    _ep(store, "a", created=0)
    _ep(store, "b", created=0)
    hits = retrieve_c2(store, params.top_k, C2RetrievalQuery(
        subsystem=MemorySubsystem.EPISODIC, retrieved_at=0, cues=("ev.a",)))
    assert isinstance(hits, tuple) and hits[0].memory_ref == "a"   # cue 命中者居首
    hits2 = retrieve_c2(store, params.top_k, C2RetrievalQuery(
        subsystem=MemorySubsystem.EPISODIC, retrieved_at=0, cues=("ev.a",)))
    assert hits == hits2   # 同库同 query 同结果


def test_affective_component_and_empty_unknown(params: C2MemoryParams, tmp_path: Path) -> None:
    """δ = |valence|（标注经唯一写者落盘后生效，缺省 0）；空子系统 = Unknown。"""
    store = _store(tmp_path / "d")
    _ep(store, "e1", created=0)
    plain = store.get("e1")
    assert plain is not None
    before = _c2_score(plain, (), 1)
    write_affective_tag(store, propose_value_tag("e1", -0.8, 0.5, 0.9, at=1))
    tagged = store.get("e1")
    assert tagged is not None and tagged.affective is not None
    after = _c2_score(tagged, (), 1)
    assert after - before == pytest.approx(0.8)   # |−0.8|（无标注缺省 0 的差分）
    untagged = replace(tagged, affective=None)
    assert isinstance(untagged, MemoryItem)
    assert _c2_score(untagged, (), 1) == pytest.approx(before)

    empty = retrieve_c2(store, params.top_k, C2RetrievalQuery(
        subsystem=MemorySubsystem.SEMANTIC, retrieved_at=1))
    assert isinstance(empty, Unknown)
