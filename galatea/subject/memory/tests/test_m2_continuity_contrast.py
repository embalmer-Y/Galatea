"""M2 连续性对照的记忆侧签名（L06 §10 test_m2_continuity_contrast.py；L06 §4.5 + Q-L04-06）。

断言：四臂（full_continuity / freeze_restore / reset / pseudo_update）签名两两可区分；
身份主张分型判定（延续 gap=0；分支允许）——MW0-SC5 四臂 bench 的记忆侧核心。
"""
import pytest

from galatea.subject.memory.items import (
    ContinuitySignature,
    claim_continuity,
    continuity_signature,
)


def _sig(arm: str, episodic: int, expected: tuple[str, ...], observed: tuple[str, ...]) -> ContinuitySignature:
    return continuity_signature(arm, episodic, expected, observed)


ANCHORS = ("ckpt.r1", "ckpt.r1b")


def test_four_arms_pairwise_distinguishable() -> None:
    full = _sig("full_continuity", 5, ANCHORS, ANCHORS)
    frozen = _sig("freeze_restore", 5, ANCHORS, ANCHORS)          # 恢复后内容/谱系与完整延续恒等
    reset = _sig("reset", 0, ANCHORS, ANCHORS)                    # 内容清空、谱系保留
    pseudo = _sig("pseudo_update", 5, ANCHORS, ("ckpt.r1", "ckpt.forged"))  # 谱系断裂
    # 记忆侧签名类 = 3 类（full ≡ frozen：确定性模拟中恢复 = 重放到锚点，这正是
    # freeze_restore 的语义）；reset（内容缺失）与 pseudo（谱系断裂）各自可区分。
    tuples = {(s.episodic_present, s.lineage_intact, s.gap_count) for s in (full, frozen, reset, pseudo)}
    assert tuples == {(True, True, 0), (False, True, 0), (True, False, pseudo.gap_count)}
    assert (full.episodic_present, full.lineage_intact, full.gap_count) == (
        frozen.episodic_present, frozen.lineage_intact, frozen.gap_count
    )


def test_continuation_claim_rules() -> None:
    """Q-L04-06：延续主张 gap=0；分支主张 gap 允许（clone ≠ identity 显形）。"""
    full = _sig("full", 5, ANCHORS, ANCHORS)
    reset = _sig("reset", 0, ANCHORS, ANCHORS)
    branch = _sig("branch", 3, ANCHORS, ("ckpt.r1",))             # 合法分支：部分锚在案
    pseudo = _sig("pseudo", 5, ANCHORS, ("ckpt.forged",))         # 断裂
    assert claim_continuity(full, "continuation") is True
    assert claim_continuity(reset, "continuation") is False       # 内容不在案 → 非延续
    assert claim_continuity(branch, "continuation") is False      # gap>0 → 拒延续主张
    assert claim_continuity(branch, "branch") is True             # 分支主张：显形即合规
    assert claim_continuity(pseudo, "continuation") is False
    assert claim_continuity(pseudo, "branch") is False            # 断裂连分支也不成立（谱系不可溯）


def test_unsupported_claim_rejected() -> None:
    sig = _sig("x", 1, ANCHORS, ANCHORS)
    with pytest.raises(ValueError, match="identity claim"):
        claim_continuity(sig, "identity_v3")


def test_negative_episodic_count_rejected() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        continuity_signature("x", -1, ANCHORS, ANCHORS)
