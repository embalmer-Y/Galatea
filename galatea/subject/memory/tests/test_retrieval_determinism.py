"""检索确定性（L06 §10 test_retrieval_determinism.py；Q-G00-11 冻结参数）。"""
import tempfile
from pathlib import Path

from galatea.kernel.packet import RepresentationLevel
from galatea.kernel.state import Stores
from galatea.kernel.unknown import Unknown
from galatea.subject.memory.encode import encode_episodic, encode_working
from galatea.subject.memory.ports import MemorySubsystem, SourceType
from galatea.subject.memory.retrieve import RetrievalQuery, retrieve
from galatea.subject.memory.store import MemoryStore, load_m2_continuity_profile

PROFILE = load_m2_continuity_profile()


def _store(tmp: Path) -> MemoryStore:
    return MemoryStore(Stores(tmp / "stores"))


def test_same_store_same_query_identical_results(tmp_path: Path) -> None:
    store = _store(tmp_path / "a")
    for i in range(6):
        encode_episodic(store, PROFILE, f"ep.{i}", f"ev.{i}", RepresentationLevel.RECEIVED,
                        SourceType.SELF_GENERATED, i)
    q = RetrievalQuery(MemorySubsystem.EPISODIC, 100)
    a = retrieve(store, PROFILE, q)
    b = retrieve(store, PROFILE, q)
    assert a == b
    assert not isinstance(a, Unknown)
    assert len(a) == PROFILE.retrieval_top_k  # 预算 = retrieval_top_k（Q-G00-11）


def test_tiebreak_by_item_id_ascending(tmp_path: Path) -> None:
    """同强度 tie 按 item_id 升序（禁容器序依赖，L00 §8）。"""
    store = _store(tmp_path / "b")
    for i in ("d", "b", "a", "c"):
        encode_episodic(store, PROFILE, f"ep.{i}", f"ev.{i}", RepresentationLevel.RECEIVED,
                        SourceType.SELF_GENERATED, 0)
    result = retrieve(store, PROFILE, RetrievalQuery(MemorySubsystem.EPISODIC, 10))
    assert not isinstance(result, Unknown)
    assert [r.memory_ref for r in result] == ["ep.a", "ep.b", "ep.c", "ep.d"]


def test_empty_subsystem_returns_typed_unknown(tmp_path: Path) -> None:
    """空命中 = Unknown（L06 §10：禁静默空列表冒充命中）。"""
    store = _store(tmp_path / "c")
    result = retrieve(store, PROFILE, RetrievalQuery(MemorySubsystem.EPISODIC, 0))
    assert isinstance(result, Unknown)
    assert result.reason.value == "INSUFFICIENT_OBSERVATION"


def test_working_and_episodic_isolated(tmp_path: Path) -> None:
    store = _store(tmp_path / "d")
    encode_episodic(store, PROFILE, "ep.1", "ev.1", RepresentationLevel.RECEIVED, SourceType.SELF_GENERATED, 0)
    encode_working(store, PROFILE, "w.1", "frame.1", RepresentationLevel.RECEIVED, SourceType.PERCEIVED, 0)
    epi = retrieve(store, PROFILE, RetrievalQuery(MemorySubsystem.EPISODIC, 5))
    work = retrieve(store, PROFILE, RetrievalQuery(MemorySubsystem.WORKING, 5))
    assert not isinstance(epi, Unknown) and not isinstance(work, Unknown)
    assert [r.memory_ref for r in epi] == ["ep.1"]
    assert [r.memory_ref for r in work] == ["w.1"]
