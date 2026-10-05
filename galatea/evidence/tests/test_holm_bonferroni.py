"""holm_bonferroni step-down 手算锚测试（REV-0014 闭环复核关切②：专属单测钉死）。"""
from galatea.evidence.evaluator.hypotheses import holm_bonferroni


def test_all_tiny_reject_all():
    """全 p≈0：全部拒绝，adjustment = m·p_min 单调化（截 1.0 前）。"""
    rejected, adjusted = holm_bonferroni((1e-20, 1e-20, 1e-20))
    assert rejected == (True, True, True)
    assert all(abs(a - 3e-20) < 1e-35 for a in adjusted)   # m·p_min（float64 舍入内）


def test_holm_hand_anchor_mixed():
    """手算锚：(0.001, 0.04, 0.03)，α=0.05 → 排序 0.001/0.03/0.04。

    m=3：0.001 ≤ 0.05/3 → 拒；0.03 ≤ 0.05/2 = 0.025？否 → 停止。
    rejected（原索引序）= (True, False, False)；
    adjusted = (3×0.001, 1.0（break 后未达）, max(3×0.001, 2×0.03)=0.06)。
    """
    rejected, adjusted = holm_bonferroni((0.001, 0.04, 0.03))
    assert rejected == (True, False, False)
    assert abs(adjusted[0] - 0.003) < 1e-12
    assert adjusted[1] == 1.0
    assert abs(adjusted[2] - 0.06) < 1e-12


def test_holm_two_rejections_then_stop():
    """(0.9, 0.01, 0.02)：0.01 ≤ 0.0167 拒、0.02 ≤ 0.025 拒、0.9 > 0.05 停。"""
    rejected, _adjusted = holm_bonferroni((0.9, 0.01, 0.02))
    assert rejected == (False, True, True)


def test_holm_single_p():
    """m=1：p ≤ α 即拒（adjusted p = 裸 p）。"""
    assert holm_bonferroni((0.04,)) == ((True,), (0.04,))
    assert holm_bonferroni((0.06,)) == ((False,), (0.06,))


def test_holm_empty():
    assert holm_bonferroni(()) == ((), ())
