"""遗忘控制：衰减谱/访问增强/tombstone/容量溢出降级（Q-L06-01/03；L06 §4.3/§4.5）。"""
from pathlib import Path

import pytest

from galatea.kernel.packet import RepresentationLevel
from galatea.kernel.state import Stores
from galatea.subject.c2profile import C2MemoryParams, load_c2_memory_profile
from galatea.subject.memory.encode import encode_episodic
from galatea.subject.memory.forget import (
    ProtectionViolation,
    boost_on_access,
    decay_pass,
    enforce_overflow,
    forget_item,
)
from galatea.subject.memory.items import ConsolidationState, MemoryItem
from galatea.subject.memory.ports import MemorySubsystem, SourceType
from galatea.subject.memory.store import MemoryStore

ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture(scope="module")
def params() -> C2MemoryParams:
    return load_c2_memory_profile(ROOT / "config/profiles/c2_memory.profile.yaml")


def _store(tmp: Path) -> MemoryStore:
    return MemoryStore(Stores(tmp / "stores"))


def _ep(store: MemoryStore, item_id: str, created: int = 0) -> None:
    store.put(MemoryItem(
        item_id=item_id, subsystem=MemorySubsystem.EPISODIC, source_type=SourceType.PERCEIVED,
        content_ref=f"ev.{item_id}", representation_level=RepresentationLevel.RECEIVED,
        strength=1.0, created_cycle=created, last_access_cycle=created,
    ))


def test_decay_tau_ladder_per_t6(params: C2MemoryParams, tmp_path: Path) -> None:
    """衰减 = strength×(1−1/τ_sub) 每 T6 拍：episodic τ=256 → 1×255/256 逐位。"""
    store = _store(tmp_path / "a")
    _ep(store, "e1")
    tau = params.tau_sub[MemorySubsystem.EPISODIC]
    assert tau == 256
    receipt = decay_pass(store, params, tick_cycle=64)
    assert receipt.decayed_count == 1
    item = store.get("e1")
    assert item is not None
    assert item.strength == pytest.approx(1.0 * 255.0 / 256.0)


def test_protected_exempt_and_forgotten_skipped(params: C2MemoryParams, tmp_path: Path) -> None:
    """PROTECTED 不衰减（保护集语义）；FORGOTTEN 不再衰减（tombstone 稳定）。"""
    store = _store(tmp_path / "b")
    store.put(MemoryItem(
        item_id="prot", subsystem=MemorySubsystem.EPISODIC, source_type=SourceType.PERCEIVED,
        content_ref="ev.prot", representation_level=RepresentationLevel.RECEIVED,
        strength=0.8, created_cycle=0, last_access_cycle=0,
        consolidation_state=ConsolidationState.PROTECTED,
    ))
    receipt = decay_pass(store, params, tick_cycle=64)
    assert receipt.protected_skipped == 1 and receipt.decayed_count == 0
    with pytest.raises(ProtectionViolation):
        forget_item(store, "prot", reason="policy")


def test_forget_tombstone_kept_and_excluded(params: C2MemoryParams, tmp_path: Path) -> None:
    """显式遗忘 = FORGOTTEN + tombstone 留痕（行保留可审计，默认检索排除——非删除）。"""
    store = _store(tmp_path / "c")
    _ep(store, "e1")
    forgotten = forget_item(store, "e1", reason="policy_test")
    assert forgotten.consolidation_state is ConsolidationState.FORGOTTEN
    assert "tombstone:policy_test" in forgotten.lineage_refs
    assert store.list_subsystem(MemorySubsystem.EPISODIC) == ()                    # 默认排除
    kept = store.list_subsystem(MemorySubsystem.EPISODIC, include_forgotten=True)
    assert len(kept) == 1                                                          # 行保留（非删除）
    assert forget_item(store, "e1", reason="again").consolidation_state \
        is ConsolidationState.FORGOTTEN                                            # 幂等


def test_access_boost_capped(params: C2MemoryParams, tmp_path: Path) -> None:
    """访问增强 +0.125 上界 1.0（Q-L04-10 先例）；access_count/last_access 更新。"""
    store = _store(tmp_path / "d")
    _ep(store, "e1")
    _ep(store, "e2")
    store.put(MemoryItem(
        item_id="e2", subsystem=MemorySubsystem.EPISODIC, source_type=SourceType.PERCEIVED,
        content_ref="ev.e2", representation_level=RepresentationLevel.RECEIVED,
        strength=0.95, created_cycle=0, last_access_cycle=0,
    ))
    boost_on_access(store, params, ("e1",), cycle=10)
    item = store.get("e1")
    assert item is not None
    assert item.strength == 1.0   # 1.0 + 0.125 → clip 上界 1.0（Q-L06-03③ 上界=域上界）
    # 上界：e2 0.95 + 0.125 → 1.0（clip）
    boost_on_access(store, params, ("e2",), cycle=11)
    item2 = store.get("e2")
    assert item2 is not None and item2.strength == 1.0 and item2.access_count == 1


def test_overflow_demotes_oldest_labile(params: C2MemoryParams, tmp_path: Path) -> None:
    """溢出 = 最旧 LABILE → ARCHIVED（(last_access, item_id) 升序确定性；禁删除）。"""
    store = _store(tmp_path / "e")
    # prospective 容量 64——用小容量的 working（16）驱动溢出
    for i in range(params.capacities[MemorySubsystem.WORKING] + 2):
        store.put(MemoryItem(
            item_id=f"w.{i:03d}", subsystem=MemorySubsystem.WORKING,
            source_type=SourceType.PERCEIVED, content_ref=f"wk.{i}",
            representation_level=RepresentationLevel.RECEIVED,
            strength=0.5, created_cycle=i, last_access_cycle=i,
        ))
    demoted = enforce_overflow(store, params)
    assert len(demoted) == 2 and demoted == ("w.000", "w.001")   # 最旧先降（确定性全序）
    d0 = store.get("w.000")
    assert d0 is not None and d0.consolidation_state is ConsolidationState.ARCHIVED
    kept = store.list_subsystem(MemorySubsystem.WORKING)
    assert len(kept) == params.capacities[MemorySubsystem.WORKING]                   # 容量恢复（非删除）
    assert "demote:overflow" in d0.lineage_refs


def test_overflow_protected_unresolvable(params: C2MemoryParams, tmp_path: Path) -> None:
    """溢出不可经降级 PROTECTED 解决 → ProtectionViolation（L06 §4.5 S2）。"""
    store = _store(tmp_path / "f")
    for i in range(params.capacities[MemorySubsystem.WORKING] + 1):
        store.put(MemoryItem(
            item_id=f"w.{i:03d}", subsystem=MemorySubsystem.WORKING,
            source_type=SourceType.PERCEIVED, content_ref=f"wk.{i}",
            representation_level=RepresentationLevel.RECEIVED,
            strength=0.5, created_cycle=i, last_access_cycle=i,
            consolidation_state=ConsolidationState.PROTECTED,
        ))
    with pytest.raises(ProtectionViolation):
        enforce_overflow(store, params)
