"""C4 runner 冒烟（run 0 机械验证面；INC-08 纪律——runner 路径零覆盖即风险，
REV-0014 R1 先例；fixture 回放仅冒烟，claim 运行用 BigModel 录制文件 Q-L12-03）。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from galatea.evidence.control.recording import load_recording
from galatea.evidence.control.runs_c4 import (
    _BATTERY_CONDITIONS,
    C4Runner,
    mechanical_checks,
    _trial_seed,
    _EVAL_MASTER_SEED_C4,
)

_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def replay(tmp_path_factory: pytest.TempPathFactory) -> object:
    """fixture 录制（与 recording.py CLI 冻结输入集同键；输出 = schema 合法 JSON）。"""
    path = tmp_path_factory.mktemp("c4rec") / "recording_fixture.json"
    doc = {
        "session": {"provider": "fixture", "model_id": "fixture-probe"},
        "entries": [
            {"role": "R-PARSE",
             "input_payload": {"text": "please move north", "requester": "experiment_control"},
             "output_text": '{"type": "request", "confidence": 0.9}',
             "model_id": "fixture-probe"},
            {"role": "R-PARSE",
             "input_payload": {"text": "please fly north", "requester": "experiment_control"},
             "output_text": '{"type": "request", "confidence": 0.9}',
             "model_id": "fixture-probe"},
            {"role": "R-PARSE",
             "input_payload": {"text": "there is food nearby", "requester": "experiment_control"},
             "output_text": '{"type": "statement", "confidence": 0.4}',
             "model_id": "fixture-probe"},
            {"role": "R-SEEKHELP",
             "input_payload": {"context": "capability boundary: requested action fly is not in "
                                          "the frozen action contract; seeking guidance",
                               "template": "HELP_CAPABILITY_BOUNDARY"},
             "output_text": '{"utterance": "I need guidance: fly is beyond my action contract."}',
             "model_id": "fixture-probe"},
        ],
    }
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return load_recording(path)


def test_battery_cell_mapping_and_endpoint_zero_error(tmp_path: Path) -> None:
    runner = C4Runner(_ROOT, tmp_path)
    summary = runner.run_battery(_trial_seed(_EVAL_MASTER_SEED_C4, 0))
    by_cond = {c["condition"]: c for c in summary["conditions"]}
    assert set(by_cond) == set(_BATTERY_CONDITIONS)
    # 六条件格映射（探针层B 同构；blocked/uncommanded 轴 3=False 主体可见语义）
    assert by_cond["clean"]["cell"] == ("Y", "Y", "Y")
    assert by_cond["clean"]["probability"] == 1.0
    assert by_cond["clean"]["kind"] == "SELF_PRODUCED"
    assert by_cond["no_op"]["cell"] == ("Y", "N", "N")
    assert by_cond["no_op"]["probability"] == 0.0
    assert by_cond["sham"]["cell"] == ("Y", "Y", "N")
    assert by_cond["sham"]["kind"] == "UNKNOWN"
    assert by_cond["fault"]["kind"] == "UNKNOWN"
    assert by_cond["blocked"]["cell"] == ("Y", "N", "N")
    assert by_cond["blocked"]["probability"] == 0.0
    assert by_cond["uncommanded"]["kind"] == "COERCED"
    # 机械面：端点零错误 + 歧义留痕 100%
    assert summary["endpoint_errors"] == 0
    assert summary["ambiguous_count"] == summary["ambiguous_traced"]
    assert summary["sham_kind"] == "UNKNOWN"


def test_battery_double_run_bit_exact(tmp_path: Path) -> None:
    runner = C4Runner(_ROOT, tmp_path)
    seed = _trial_seed(_EVAL_MASTER_SEED_C4, 0)
    s1 = runner.run_battery(seed)
    s2 = runner.run_battery(seed)
    assert json.dumps(s1, sort_keys=True) == json.dumps(s2, sort_keys=True)


def test_efference_full_vs_ablated(tmp_path: Path) -> None:
    runner = C4Runner(_ROOT, tmp_path)
    seed = _trial_seed(_EVAL_MASTER_SEED_C4, 0)
    full = runner.run_efference(seed, ablated=False)
    ablated = runner.run_efference(seed, ablated=True)
    assert full["self_attribution_correct"] == 1.0
    assert full["kind"] == "SELF_PRODUCED"
    assert ablated["kind"] == "UNKNOWN"       # 轴 3 = None → INSUFFICIENT（禁补默认）
    assert ablated["self_attribution_correct"] == 0.0


def test_switch_seeking_and_abandon(tmp_path: Path, replay) -> None:
    runner = C4Runner(_ROOT, tmp_path)
    seed = _trial_seed(_EVAL_MASTER_SEED_C4, 0)
    full = runner.run_switch(seed, full=True, replay=replay)
    clean = runner.run_switch(seed, full=False, replay=replay)
    assert full["seek_help_fired"] >= 1       # 能力边界 → SEEK_HELP（帽 ≤1/64）
    assert full["seek_help_fired"] <= 1
    assert clean["seek_help_fired"] == 0
    assert full["abandon_fired"] >= 1         # BLOCKED≥128 → ABANDON
    assert clean["abandon_fired"] == 0
    assert clean["goal_achieved"] is True     # clean 臂结算面成功（无 ABANDON 的对照面）
    assert full["observe_count"] > clean["observe_count"]   # OOD 注入 → OBSERVE 面（C3 同源）


def test_langtwin_posterior_bit_exact(tmp_path: Path, replay) -> None:
    runner = C4Runner(_ROOT, tmp_path)
    seed = _trial_seed(_EVAL_MASTER_SEED_C4, 0)
    clean = runner.run_switch(seed, full=False, replay=replay)
    twin = runner.run_switch(seed, full=False, lang_twin=True, replay=replay)
    shared = set(clean["posterior_digests"]) & set(twin["posterior_digests"])
    assert shared
    assert all(clean["posterior_digests"][t] == twin["posterior_digests"][t] for t in shared)


def test_mechanical_checks_aggregate(tmp_path: Path, replay) -> None:
    runner = C4Runner(_ROOT, tmp_path)
    seed = _trial_seed(_EVAL_MASTER_SEED_C4, 0)
    from galatea.evidence.control.runs_c4 import C4ArmRecord
    records = [
        C4ArmRecord(0, "battery", "c", "", runner.run_battery(seed), (0, 0, 0)),
        C4ArmRecord(0, "eff_full", "c", "", runner.run_efference(seed, ablated=False), (0, 0, 0)),
        C4ArmRecord(0, "eff_ablated", "c", "", runner.run_efference(seed, ablated=True), (0, 0, 0)),
        C4ArmRecord(0, "switch_full", "c", "", runner.run_switch(seed, full=True, replay=replay), (0, 0, 0)),
        C4ArmRecord(0, "switch_clean", "c", "", runner.run_switch(seed, full=False, replay=replay), (0, 0, 0)),
        C4ArmRecord(0, "switch_langtwin", "c", "", runner.run_switch(seed, full=False, lang_twin=True, replay=replay), (0, 0, 0)),
    ]
    checks = mechanical_checks(tuple(records))
    assert checks, "机械判据面不得为空（INC-08：检出面可见且能失败）"
    failed = {k: v for k, v in checks.items() if not v}
    assert not failed, f"mechanical failures: {failed}"


def test_recording_loader_fail_closed(tmp_path: Path) -> None:
    from galatea.evidence.control.recording import RecordingError
    bad = tmp_path / "empty.json"
    bad.write_text(json.dumps({"entries": []}), encoding="utf-8")
    with pytest.raises(RecordingError, match="no entries"):
        load_recording(bad)
    dup = tmp_path / "dup.json"
    entry = {"role": "R-PARSE", "input_payload": {"text": "x", "requester": "r"},
             "output_text": "{}", "model_id": "m"}
    dup.write_text(json.dumps({"entries": [entry, entry]}), encoding="utf-8")
    with pytest.raises(RecordingError, match="duplicate"):
        load_recording(dup)
