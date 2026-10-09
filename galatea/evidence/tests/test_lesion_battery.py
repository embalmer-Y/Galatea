"""E1 lesion 电池测试（选择性 = 目标失败 ∧ 他人保持；language 保持面 = 非语言逐位恒等）。"""
from pathlib import Path

import pytest

from galatea.evidence.control.lesion_battery import _LESIONS, run_lesion
from galatea.evidence.control.recording import load_recording
from galatea.subject.language.replay import ReplayStore

_ROOT = Path(__file__).resolve().parents[3]
_RECORDING = _ROOT / "evidence" / "c4_recording" / "recording_v1.json"


@pytest.fixture(scope="module")
def replay() -> ReplayStore:
    return load_recording(_RECORDING)


@pytest.fixture(scope="module")
def baseline(replay: ReplayStore) -> dict:
    return run_lesion(_ROOT, "none", replay)


def test_baseline_no_lesion_all_functions_alive(baseline: dict) -> None:
    m = baseline.markers
    assert not baseline.target_failed
    assert m["frames_total"] > 0 and m["posteriors"] > 0
    assert m["parsed_count"] >= 1   # 基线：真实录制（evidence/c4_recording）回放命中


def test_each_lesion_is_selective(replay: ReplayStore) -> None:
    """七 lesion 全部：目标失败 ∧ 他人保持（选择性双面）。"""
    for lesion in _LESIONS:
        if lesion == "none":
            continue
        result = run_lesion(_ROOT, lesion, replay)
        assert result.target_failed, f"{lesion}: target not failed {result.markers}"
        if lesion != "language_off":   # 保持面由 digest 恒等专用断言承载（下一测试）
            assert result.others_preserved, f"{lesion}: others not preserved"


def test_language_lesion_preserves_non_language_plane_bit_exact(replay: ReplayStore) -> None:
    """language_off 保持面 = 非语言形成面与基线逐位恒等（Q-L12-07 复用）。"""
    base = run_lesion(_ROOT, "none", replay)
    off = run_lesion(_ROOT, "language_off", replay)
    assert off.target_failed                      # R-PARSE 全 miss
    assert base.markers["ext_digest_set"] == off.markers["ext_digest_set"]


def test_perception_lesion_preserves_formation(replay: ReplayStore) -> None:
    """perception_off：形成帧照常（保持）而消费面后验缺席（失败）——L02/L03 分界面。"""
    result = run_lesion(_ROOT, "perception_off", replay)
    assert result.markers["frames_total"] > 0
    assert result.markers["posteriors"] == 0
    assert result.selective


def test_battery_double_run_bit_exact(replay: ReplayStore) -> None:
    r1 = run_lesion(_ROOT, "affect_off", replay)
    r2 = run_lesion(_ROOT, "affect_off", replay)
    assert json.dumps(r1.markers, sort_keys=True) == json.dumps(r2.markers, sort_keys=True)


import json  # noqa: E402
