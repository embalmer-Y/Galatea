"""Birch 评分器测试（Q-L13-18；INC-08：探针可见且能失败 + loader fail-closed）。"""
import pytest

from galatea.evidence.evaluator import birch_score
from galatea.evidence.evaluator.birch_score import (
    RegistryViolation,
    load_registry,
    score,
)


def test_registry_load_fail_closed(tmp_path) -> None:
    broken = tmp_path / "broken.yaml"
    broken.write_text("markers: []", encoding="utf-8")
    with pytest.raises(RegistryViolation):
        load_registry(broken)
    dupe = tmp_path / "dupe.yaml"
    dupe.write_text(
        "birch_marker_registry:\n"
        "  id: x\n  version: v1\n  frozen_at: d\n"
        "  markers:\n"
        "    - {id: A, tier: t, definition: d, probe: {type: registry, spec: x}, award: PRESENT, blocked_by: none}\n"
        "    - {id: A, tier: t, definition: d, probe: {type: registry, spec: x}, award: PRESENT, blocked_by: none}\n",
        encoding="utf-8")
    with pytest.raises(RegistryViolation, match="重复"):
        load_registry(dupe)


def test_score_runs_and_all_declared_probes_pass() -> None:
    """首评口径：全部 award 级标记的探针过（证据基座完整）——回归锚。"""
    report = score()
    assert report["total_markers"] == 15
    assert report["scored_markers"] == 14          # UNDETERMINABLE 排除
    failed = [m for ms in report["tiers"].values() for m in ms if m["probe"] == "FAIL"]
    assert not failed, failed
    assert report["verdict"] in ("VIABLE_SO_FAR_WITH_FORWARD_RISKS",
                                 "NOT_VIABLE_WITHOUT_MODERN_AI")


def test_probe_failure_demotes_to_absent(monkeypatch) -> None:
    """INC-08：探针失败 → 标记降 ABSENT 且分数下降（评分器可失败非宣称器）。"""
    baseline = score()
    good = birch_score._probe_artifacts
    def sabotaged(names, index):
        return False, "sabotaged"
    monkeypatch.setattr(birch_score, "_probe_artifacts", sabotaged)
    degraded = score()
    absent = [m for ms in degraded["tiers"].values() for m in ms if m["state"] == "ABSENT"]
    assert absent                                   # 工件类标记全部跌落
    assert degraded["score"] < baseline["score"]
    monkeypatch.setattr(birch_score, "_probe_artifacts", good)


def test_verdict_flips_on_classical_ceiling(tmp_path) -> None:
    """判读机械化：classical_ceiling 命中 PARTIAL → NOT_VIABLE（owner 汇报触发线）。"""
    registry = load_registry()
    for m in registry["markers"]:
        if m["id"] == "B1-2":
            m["blocked_by"] = "classical_ceiling"
    report = score(registry)
    assert "B1-2" in report["classical_ceiling_blockers"]
    assert report["verdict"] == "NOT_VIABLE_WITHOUT_MODERN_AI"


def test_module_probes_run_real_computation() -> None:
    """模块探针真跑（非静态宣称）：情感引擎与仲裁的核心探针直接可调用。"""
    ok_v, detail_v = birch_score._probe_unified_valence()
    assert ok_v, detail_v
    ok_n, detail_n = birch_score._probe_affect_nociception()
    assert ok_n, detail_n
    ok_p, detail_p = birch_score._probe_pareto_tradeoff()
    assert ok_p, detail_p
