"""subject_memory.db 连接与 m2 profile 加载（L06 §3/§10 store.py——M2 最小切片）。

纪律：subject_memory.db 由本档独占写（Q-T05 三库分离；kernel _OWNERSHIP 预注册
(SUBJECT_MEMORY, episodes) → 写者 "memory"）；orchestrator/recorder 无写路径
（kernel 单写者机械校验承载）；M2 期单表 episodes（条目 JSON 序列化 + 列式索引）。
"""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from galatea.kernel.packet import RepresentationLevel
from galatea.kernel.state import StoreName, Stores
from galatea.subject.memory.items import ConsolidationState, MemoryItem
from galatea.subject.memory.ports import MemorySubsystem, SourceType

__all__ = ["MemoryStore", "MemoryStoreViolation", "M2ContinuityProfile", "load_m2_continuity_profile"]


class MemoryStoreViolation(ValueError):
    """记忆库操作违例（容量溢出/未知条目/DDL 失败）——fail closed。"""


class MemoryStore:
    """主体记忆库（唯一写者；M2 切片：working/episodic 单表 episodes）。

    每 trial 独立 Stores 实例（隔离事件序列）；close() 由调用方管理
    （kernel Stores.close，Windows 句柄锁前提）。
    """

    def __init__(self, stores: Stores) -> None:
        self._stores = stores
        self._writer = stores.open_writer(StoreName.SUBJECT_MEMORY, "episodes", "memory")
        self._writer.execute(
            "CREATE TABLE IF NOT EXISTS episodes ("
            "item_id TEXT PRIMARY KEY, subsystem TEXT, source_type TEXT, strength REAL, "
            "created_cycle INTEGER, last_access_cycle INTEGER, state TEXT, payload TEXT)"
        )

    def close(self) -> None:
        self._stores.close()

    def put(self, item: MemoryItem) -> None:
        payload = {
            "content_ref": item.content_ref,
            "representation_level": item.representation_level.value,
            "lineage_refs": list(item.lineage_refs),
            "access_count": item.access_count,
            "affective": (
                None if item.affective is None else {
                    "memory_ref": item.affective.memory_ref,
                    "valence": item.affective.valence,
                    "arousal": item.affective.arousal,
                    "persistence": item.affective.persistence,
                    "proposed_at": item.affective.proposed_at,
                }
            ),
        }
        with self._writer.transaction():
            self._writer.execute(
                "INSERT OR REPLACE INTO episodes (item_id, subsystem, source_type, strength, "
                "created_cycle, last_access_cycle, state, payload) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    item.item_id, item.subsystem.value, item.source_type.value, item.strength,
                    item.created_cycle, item.last_access_cycle, item.consolidation_state.value,
                    json.dumps(payload, sort_keys=True, separators=(",", ":")),
                ),
            )

    def get(self, item_id: str) -> MemoryItem | None:
        rows = self._stores.read(
            StoreName.SUBJECT_MEMORY,
            "SELECT item_id, subsystem, source_type, strength, created_cycle, last_access_cycle, "
            "state, payload FROM episodes WHERE item_id = ?",
            (item_id,),
        )
        return _row_to_item(rows[0]) if rows else None

    def list_subsystem(self, subsystem: MemorySubsystem, include_forgotten: bool = False) -> tuple[MemoryItem, ...]:
        """子系统条目（默认排除非活跃态：FORGOTTEN + ARCHIVED——降级即退出活跃检索集，
        Q-L06-01② 溢出降级语义；include_forgotten=True 返回全部含 tombstone。
        M2 路径无 ARCHIVED 条目——行为与冻结语义恒等）。"""
        rows = self._stores.read(
            StoreName.SUBJECT_MEMORY,
            "SELECT item_id, subsystem, source_type, strength, created_cycle, last_access_cycle, "
            "state, payload FROM episodes WHERE subsystem = ? ORDER BY item_id",
            (subsystem.value,),
        )
        inactive = (ConsolidationState.FORGOTTEN, ConsolidationState.ARCHIVED)
        items = [i for i in (_row_to_item(r) for r in rows)
                 if include_forgotten or i.consolidation_state not in inactive]
        return tuple(items)

    def clear_working_episodic(self) -> int:
        """重置语义（m2_continuity.profile sc5.reset：清空 working/episodic 内容，保留谱系/登记）。

        返回清除条目数。谱系锚（checkpoint 记录在 subject_state.kernel_checkpoints）不在本库——天然保留。
        """
        with self._writer.transaction():
            before = cast(int, self._stores.read(StoreName.SUBJECT_MEMORY, "SELECT COUNT(*) FROM episodes")[0][0])
            self._writer.execute("DELETE FROM episodes WHERE subsystem IN ('working', 'episodic')")
        return int(before)

    def count(self, subsystem: MemorySubsystem) -> int:
        rows = self._stores.read(
            StoreName.SUBJECT_MEMORY, "SELECT COUNT(*) FROM episodes WHERE subsystem = ?", (subsystem.value,)
        )
        return int(cast(int, rows[0][0]))


def _row_to_item(row: tuple[Any, ...]) -> MemoryItem:
    from galatea.subject.affect.value_tag import AffectiveValueTag

    payload = json.loads(cast(str, row[7]))
    aff_raw = payload.get("affective")   # M2 旧行无键 → None（向后兼容，SC6 I1 复算不受扰）
    return MemoryItem(
        item_id=cast(str, row[0]),
        subsystem=MemorySubsystem(cast(str, row[1])),
        source_type=SourceType(cast(str, row[2])),
        content_ref=payload["content_ref"],
        representation_level=RepresentationLevel(payload["representation_level"]),
        strength=float(row[3]),
        created_cycle=int(row[4]),
        last_access_cycle=int(row[5]),
        consolidation_state=ConsolidationState(cast(str, row[6])),
        lineage_refs=tuple(payload["lineage_refs"]),
        affective=None if aff_raw is None else AffectiveValueTag(
            memory_ref=cast(str, aff_raw["memory_ref"]),
            valence=float(aff_raw["valence"]),
            arousal=float(aff_raw["arousal"]),
            persistence=float(aff_raw["persistence"]),
            proposed_at=int(aff_raw["proposed_at"]),
        ),
        access_count=int(payload.get("access_count", 0)),
    )


@dataclass(frozen=True, slots=True)
class M2ContinuityProfile:
    """m2_continuity.profile.yaml 的 typed 视图（全部字段溯源冻结 profile）。"""

    policy_version: str
    checkpoint_periodic_cycles: int
    memory_episodic_capacity: int
    memory_working_capacity: int
    strength_initial: float
    decay_factor_per_t6: float
    retrieval_top_k: int
    episode_cycles: int
    sc5_arms: tuple[str, ...]
    continuation_claim_max_gaps: int


def _require(obj: dict[str, Any], key: str) -> Any:
    if key not in obj:
        raise MemoryStoreViolation(f"m2 profile missing key: {key}")
    return obj[key]


def load_m2_continuity_profile(path: Path | None = None) -> M2ContinuityProfile:
    """加载 m2_continuity.profile（缺键/类型错即 MemoryStoreViolation，fail closed；INC-11 教训：
    冻结物必须经 typed loader 验证——本函数即 REV-0008 R1 承诺的加载器）。"""
    p = path if path is not None else Path(__file__).resolve().parents[3] / "config" / "profiles" / "m2_continuity.profile.yaml"
    if not p.is_file():
        raise MemoryStoreViolation(f"m2 profile not found: {p}")
    raw = cast(dict[str, Any], yaml.safe_load(p.read_text(encoding="utf-8")))
    header = cast(dict[str, Any], _require(raw, "profile"))
    ckpt = cast(dict[str, Any], _require(raw, "checkpoint"))
    mem = cast(dict[str, Any], _require(raw, "memory_min"))
    sc5 = cast(dict[str, Any], _require(raw, "sc5"))
    gap_policy = cast(dict[str, Any], _require(sc5, "continuation_gap_policy"))
    return M2ContinuityProfile(
        policy_version=f"{_require(header, 'id')}@{_require(header, 'version')}",
        checkpoint_periodic_cycles=cast(int, _require(ckpt, "periodic_cycles")),
        memory_episodic_capacity=cast(int, _require(mem, "episodic_capacity")),
        memory_working_capacity=cast(int, _require(mem, "working_capacity")),
        strength_initial=float(_require(mem, "strength_initial")),
        decay_factor_per_t6=float(_require(mem, "decay_factor_per_t6")),
        retrieval_top_k=cast(int, _require(mem, "retrieval_top_k")),
        episode_cycles=cast(int, _require(sc5, "episode_cycles")),
        sc5_arms=tuple(cast(list[str], _require(sc5, "arms"))),
        continuation_claim_max_gaps=cast(int, _require(gap_policy, "continuation_claim_max_gaps")),
    )
