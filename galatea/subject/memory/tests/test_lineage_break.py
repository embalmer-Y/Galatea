"""谱系断裂检测（L06 §10 test_lineage_break.py；L06 §4.5 LineageBreak + Q-L04-06）。"""
import pytest

from galatea.subject.memory.items import LineageBreak, assert_lineage_continuous


def test_continuous_lineage_passes() -> None:
    assert_lineage_continuous(("a", "b"), ("a", "b", "c"))   # 观测链覆盖期望链


def test_broken_lineage_raises() -> None:
    with pytest.raises(LineageBreak, match="missing anchors"):
        assert_lineage_continuous(("a", "b", "c"), ("a", "x", "c"))


def test_missing_tail_raises() -> None:
    with pytest.raises(LineageBreak, match="b"):
        assert_lineage_continuous(("a", "b"), ("a",))


def test_empty_observed_fully_broken() -> None:
    with pytest.raises(LineageBreak):
        assert_lineage_continuous(("a",), ())
