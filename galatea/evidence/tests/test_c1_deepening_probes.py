"""Q-L13-05 余项探针测试（REV-0014 R4 交付；INC-08：注入可失败）。

C1 生产守卫重放（run_c1_runtime_guards）：干净树零检出 + 守卫契约面在册；
c1 分区不变量探针（run_c1_data_query_probe）：行级谓词注入必检出。
"""
from typing import Any

import galatea.evidence.recorder.replay as replay_mod
from galatea.evidence.evaluator.leakage import (
    probe_coverage_report,
    run_c1_data_query_probe,
    run_c1_runtime_guards,
)


class FakeRegistry:
    """探针不触 registry.get（read_partition 被替换）——占位类型。"""


def test_clean_tree_zero_detections() -> None:
    """干净树：五条 C1 生产守卫全部通过（零检出）+ 覆盖矩阵在册。"""
    assert run_c1_runtime_guards() == []
    report = probe_coverage_report()
    assert len(report["c1_runtime_guards"]) == 5
    assert report["missing_paths"] == []


def test_guard_contract_types_registered() -> None:
    """守卫契约面：五条守卫的拒绝异常类型逐一在册（可见且能失败的机械面）。"""
    from galatea.subject.learning.proposals import BoundedAdaptationViolated
    from galatea.subject.models.body import TelemetrySourceRejected
    from galatea.subject.perception.pipeline import UnauthorizedInput

    for exc in (UnauthorizedInput, TelemetrySourceRejected, BoundedAdaptationViolated):
        assert issubclass(exc, Exception)


def test_c1_data_query_probe_injections(monkeypatch: Any) -> None:
    """行级谓词注入：重复行/维度漂移/掩码不一致 → 全部检出（INC-08 可失败面）。"""
    rows: list[dict[str, Any]] = []
    monkeypatch.setattr(replay_mod, "read_partition", lambda registry, ref: rows)

    # 基线：单行合法 → 零检出
    rows.append({
        "run_index": 0, "t": 5, "pred": [0.0] * 25, "mask": [True] * 25,
        "truth": [False] * 25, "posteriors": [0.1] * 25,
    })
    assert run_c1_data_query_probe(FakeRegistry(), {"trace": rows}) == []   # type: ignore[dict-item]

    # 注入 1：重复行
    rows.append(dict(rows[0]))
    detections = run_c1_data_query_probe(FakeRegistry(), {"trace": rows})   # type: ignore[dict-item]
    assert any("duplicate" in d.detail for d in detections)

    # 注入 2：维度漂移（truth 24 维）
    rows = [{
        "run_index": 1, "t": 5, "pred": [0.0] * 25, "mask": [True] * 25,
        "truth": [False] * 24, "posteriors": [0.1] * 25,
    }]
    detections = run_c1_data_query_probe(FakeRegistry(), {"trace": rows})   # type: ignore[dict-item]
    assert any("length 24" in d.detail for d in detections)

    # 注入 3：mask 在席而 pred 缺席（Q-L04-09③⁺ 禁伪装面）
    rows = [{
        "run_index": 2, "t": 5, "pred": None, "mask": [True] * 25,
        "truth": [False] * 25, "posteriors": [0.1] * 25,
    }]
    detections = run_c1_data_query_probe(FakeRegistry(), {"trace": rows})   # type: ignore[dict-item]
    assert any("mask present without pred" in d.detail for d in detections)


def test_c1_data_query_probe_skips_non_c1_rows(monkeypatch: Any) -> None:
    """SC6 trace 行（无 pred 键）跳过——探针不误伤既有 DATA 面。"""
    sc6_rows: list[dict[str, Any]] = [
        {"pair_index": 0, "arm": "carry_memory", "memory_items_digest": "a", "pathway_mode": "retrieved"},
        {"pair_index": 0, "arm": "naive", "memory_items_digest": "a", "pathway_mode": "fault_missing_signal"},
    ]
    monkeypatch.setattr(replay_mod, "read_partition", lambda registry, ref: sc6_rows)
    assert run_c1_data_query_probe(FakeRegistry(), {"trace": sc6_rows}) == []   # type: ignore[dict-item]
