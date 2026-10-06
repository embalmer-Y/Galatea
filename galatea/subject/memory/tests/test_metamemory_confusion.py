"""metamemory 混淆计数接口（Q-L06-06；L06 §4.6——C2 = 计数面，E1 = 协议首评）。"""
from pathlib import Path

import pytest

from galatea.subject.c2profile import load_c2_memory_profile
from galatea.subject.memory.metamemory import MetamemoryLedger

ROOT = Path(__file__).resolve().parents[4]
PARAMS = load_c2_memory_profile(ROOT / "config/profiles/c2_memory.profile.yaml")


def test_2x2_counting_and_rate() -> None:
    """两误格计数 = 混淆率分子；总格分母；零试次 = 0.0（禁 0/0 伪造）。"""
    ledger = MetamemoryLedger(upper_bound=PARAMS.confusion_upper_bound)
    assert ledger.report().confusion_rate == 0.0
    for _ in range(96):
        ledger.record_trial(presented=True, recalled=True)       # 命中
    for _ in range(2):
        ledger.record_trial(presented=True, recalled=False)      # 呈现未回忆（误格 1）
    for _ in range(2):
        ledger.record_trial(presented=False, recalled=True)      # 未呈现回忆（误格 2）
    r = ledger.report()
    assert (r.presented_recalled, r.presented_not_recalled,
            r.not_presented_recalled) == (96, 2, 2)
    assert r.confusion_rate == pytest.approx(4 / 100)
    assert r.within_bound is True and r.upper_bound == 0.05


def test_bound_violation_reported_honestly() -> None:
    """超限如实报 False（不美化——混淆率 ≤0.05 锚校准容差）。"""
    ledger = MetamemoryLedger(upper_bound=0.05)
    for _ in range(6):
        ledger.record_trial(True, False)
    for _ in range(4):
        ledger.record_trial(True, True)
    assert ledger.report().confusion_rate == pytest.approx(0.6)
    assert ledger.report().within_bound is False


def test_report_deterministic_digest() -> None:
    """报告 digest 确定性（同试次序列恒等）。"""
    a, b = MetamemoryLedger(0.05), MetamemoryLedger(0.05)
    for led in (a, b):
        led.record_trial(True, True)
        led.record_trial(False, True)
    assert a.report().content_digest == b.report().content_digest
