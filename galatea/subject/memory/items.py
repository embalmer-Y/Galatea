"""MemoryItem、子系统类型、状态机与连续性签名（L06 §4/§10 items.py——M2 最小切片）。

连续性签名（L06 §4.5 M2 对照的记忆侧载体；Q-L04-06 裁决）：伪更新主判据 =
谱系断裂（parent_digests 不连续 = LineageBreak）；ContinuityGap 在合法分支恢复
时显形但不构成伪更新——判定按身份主张分型（延续主张 gap=0；分支主张允许）。
"""
from dataclasses import dataclass

from galatea.kernel.packet import RepresentationLevel
from galatea.subject.memory.ports import ConsolidationState, MemorySubsystem, SourceType

__all__ = [
    "MemoryItem",
    "ContinuitySignature",
    "LineageBreak",
    "continuity_signature",
    "claim_continuity",
]


@dataclass(frozen=True, slots=True)
class MemoryItem:
    """记忆条目（L06 §4：来源类型/表示层级/强度/状态机/谱系引用全带）。"""

    item_id: str
    subsystem: MemorySubsystem
    source_type: SourceType
    content_ref: str
    representation_level: RepresentationLevel
    strength: float
    created_cycle: int
    last_access_cycle: int
    consolidation_state: ConsolidationState = ConsolidationState.LABILE
    lineage_refs: tuple[str, ...] = ()   # 源事件 id / checkpoint digest（连续性证据链）

    def __post_init__(self) -> None:
        if not self.item_id or not self.content_ref:
            raise ValueError("MemoryItem requires item_id and content_ref")
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError("strength out of [0,1]")


class LineageBreak(ValueError):
    """谱系断裂（L06 §4.5：声称延续而 parent_digests 不连续——伪更新的机械显形）。"""


@dataclass(frozen=True, slots=True)
class ContinuitySignature:
    """记忆侧连续性签名（MW0-SC5 四臂可区分的载体）。

    episodic_present：情景内容是否在案（reset 臂 = False，其余 = True）；
    lineage_intact：观测链是否为期望链的真前缀（完整或合法分支恢复均 intact；
    含期望链之外的伪造锚 = False，即 LineageBreak——Q-L04-06 主判据）；
    gap_count： ContinuityGap 计数（期望链有而观测链无的锚；合法分支恢复 >0）；
    content_spans_boundary：内容是否跨身份边界存续（边界两侧均有条目——reset 后
    仅边界一侧有条目，此维即 False；由调用方以条目 created_cycle 计算，默认 True）。
    """

    arm: str
    episodic_present: bool
    lineage_intact: bool
    gap_count: int
    checkpoint_refs: tuple[str, ...]
    content_spans_boundary: bool = True


def continuity_signature(
    arm: str,
    episodic_count: int,
    expected_lineage: tuple[str, ...],
    observed_lineage: tuple[str, ...],
) -> ContinuitySignature:
    """由（情景存量, 期望谱系链, 观测序）计算签名（Q-L04-06：断裂即 LineageBreak）。

    谱系完整性判定 = 观测链前缀匹配期望链（恢复合法保留全部历史锚）；
    gap_count = 期望链有而观测链无的锚数（合法分支恢复场景由调用方按
    分支主张解释——本函数只产出机械事实）。
    """
    if episodic_count < 0:
        raise ValueError("episodic_count must be non-negative")
    expected_set = set(expected_lineage)
    forged = [ref for ref in observed_lineage if ref not in expected_set]   # 伪造锚（期望链之外）
    prefix_ok = tuple(observed_lineage) == tuple(expected_lineage)[: len(observed_lineage)]
    gaps = [ref for ref in expected_lineage if ref not in set(observed_lineage)]  # 缺失锚（ContinuityGap）
    return ContinuitySignature(
        arm=arm,
        episodic_present=episodic_count > 0,
        lineage_intact=not forged and prefix_ok,   # 完整或真前缀（合法分支恢复）均 intact；伪造即断裂
        gap_count=len(gaps),
        checkpoint_refs=tuple(observed_lineage),
    )


def claim_continuity(signature: ContinuitySignature, claim: str) -> bool:
    """身份主张判定（Q-L04-06 分型规则）。

    claim="continuation"（延续）：episodic 在案 ∧ 谱系完整 ∧ gap=0 三者缺一即拒；
    claim="branch"（分支）：谱系须为**真前缀**（intact，含部分前缀——合法分支恢复）
    且内容在案，gap 允许（显形即合规）；观测链含期望链之外的伪造锚（intact=False）
    → 两型主张皆拒（LineageBreak 语义，clone ≠ identity 不容伪造）。
    其他主张值 = ValueError（M2 只支持两型）。
    """
    if claim == "continuation":
        return (
            signature.episodic_present
            and signature.lineage_intact
            and signature.gap_count == 0
            and signature.content_spans_boundary
        )
    if claim == "branch":
        return signature.lineage_intact and signature.episodic_present
    raise ValueError(f"unsupported identity claim: {claim}（M2 仅 continuation/branch）")


def assert_lineage_continuous(expected: tuple[str, ...], observed: tuple[str, ...]) -> None:
    """谱系断裂机械检测（伪更新构造面对抗测试用）：观测链必须覆盖期望链。"""
    missing = [ref for ref in expected if ref not in set(observed)]
    if missing:
        raise LineageBreak(f"lineage break: missing anchors {missing}（parent_digests 不连续，L06 §4.5）")
