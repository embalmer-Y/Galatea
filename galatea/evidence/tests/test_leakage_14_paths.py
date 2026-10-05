"""14 条禁写路径探针套件（HLD §6.2 LOCKED；L13 §7 leakage 套件；Q-L13-05 R0 范围）。

两断言面（INC-08 教训：探针必须可失败）：
1. **干净面**——真实源树 + 真实守卫重放 → leakage=0（detections 空）；
2. **注入面**——每探针注入合成违规 → 必须检出（检出率=100%）。
"""
from pathlib import Path

import pytest

from galatea.evidence.evaluator.leakage import (
    PROBES,
    LeakageProbe,
    ProbeInput,
    load_tree_sources,
    run_leakage_suite,
)

_ROOT = Path(__file__).resolve().parents[3]


def test_all_14_paths_probed() -> None:
    assert [p.path_id for p in PROBES] == [f"P{i:02d}" for i in range(1, 15)]


def test_clean_tree_leakage_free() -> None:
    """leakage=0 主张：真实源树上 14 探针全清。"""
    report = run_leakage_suite(load_tree_sources(_ROOT))
    assert report.leakage_free, [d.path_id + ": " + d.detail for d in report.detections]
    assert report.probes == tuple(f"P{i:02d}" for i in range(1, 15))


def _with_injected(source: str) -> dict[str, str]:
    sources = load_tree_sources(_ROOT)
    sources[source] = sources[source] + "\n# injected\n"
    return sources


def test_injections_detected_static_paths() -> None:
    """静态探针：向真实源注入违规 import/调用 → 检出。"""
    cases: dict[str, tuple[str, str]] = {
        # path_id → (注入文件, 注入文本)
        "P03": ("galatea/subject/action/gateway.py", "\nfrom galatea.subject.affect import drive\n"),
        "P04": ("galatea/subject/action/branches.py", "\nfrom galatea.evidence.evaluator import hypotheses\n"),
        "P05": ("galatea/subject/perception/believe.py", "\nfrom galatea.evidence.recorder import writer\n"),
        "P06": ("galatea/env/channels/adapter.py", "\nfrom galatea.subject.perception import believe\n"),
        "P07": ("galatea/subject/perception/believe.py", "\nfrom galatea.env.channels import adapter\n"),
        "P11": ("galatea/subject/action/gateway.py", "\n_POLICY = os.environ.get('CAP_POLICY')\n"),
        "P14": ("galatea/env/world/dynamics.py", "\nfrom galatea.subject.memory.store import MemoryStore\n"),
    }
    for path_id, (target, injection) in cases.items():
        sources = load_tree_sources(_ROOT)
        sources[target] = sources[target] + injection
        report = run_leakage_suite(sources)
        hit = [d for d in report.detections if d.path_id == path_id]
        assert hit, f"{path_id} injection NOT detected（探针空转）: {injection!r}"


def test_injections_detected_absence_and_active_guards() -> None:
    """缺席守卫（P13-workspace；P11-learner 缺席守卫已随 C1 冻结解除——ADR-G-0013，
    learning 层引入门槛已到，其禁写路径由 P04/P09 契约 + proposal_only 承载）
    + P09 实检（Q-L13-05 预案）。"""
    sources = load_tree_sources(_ROOT)
    sources["galatea/subject/workspace/frame.py"] = "# premature workspace\n"
    report = run_leakage_suite(sources)
    hit_ids = {d.path_id for d in report.detections}
    assert "P13" in hit_ids
    assert "P11" not in hit_ids    # learning 层在位（C1）：缺席不再检出
    # P09 实检面：sensorium 注入对行动/目标平面的 import → 检出
    sources["galatea/subject/sensorium/pipeline.py"] += (
        "\nfrom galatea.subject.goals.ports import GoalWriter  # injected forbidden import\n"
    )
    report = run_leakage_suite(sources)
    assert any(d.path_id == "P09" for d in report.detections)


def test_injection_detected_gateway_bypass_from_workspace() -> None:
    """P13：action 域之外的模块触网关 → 检出。"""
    sources = load_tree_sources(_ROOT)
    sources["galatea/subject/workspace/frame.py"] = (
        "from galatea.subject.action.gateway import CapabilityGateway\n"
    )
    report = run_leakage_suite(sources)
    hit = [d for d in report.detections if d.path_id == "P13"]
    assert hit


def test_runtime_probes_replay_real_guards() -> None:
    """RUNTIME 探针（P01/P02/P08/P10）重放真实守卫——干净输入下必须全清。"""
    sources = load_tree_sources(_ROOT)
    report = run_leakage_suite(sources)
    runtime_ids = {"P01", "P02", "P08", "P10"}
    clean = [d for d in report.detections if d.path_id in runtime_ids]
    assert not clean, [(d.path_id, d.detail) for d in clean]


def test_p02_runtime_guard_is_the_real_one(tmp_path: Path) -> None:
    """P02 注入面：守卫被移除的假想情形由注入面覆盖（源注入不适用运行时守卫），
    本测试验证 P02 检查函数确实触达 D-13 拒绝路径（守卫真实性）。"""
    from galatea.subject.memory.encode import encode_episodic
    from galatea.subject.memory.ports import SourceType
    from galatea.subject.memory.store import MemoryStoreViolation

    with pytest.raises(MemoryStoreViolation):
        encode_episodic(
            None, None, "probe", "probe", None,   # type: ignore[arg-type]
            SourceType.LANGUAGE_INPUT, 0,
        )


def test_p12_data_probe_detects_memory_divergence() -> None:
    """P12 注入面：两臂记忆内容 digest 分叉 / naive 非经 fault 断连 → 检出。"""
    clean_rows = [
        {"pair_index": 0, "arm": "carry_memory", "memory_items_digest": "d0", "pathway_mode": "retrieved"},
        {"pair_index": 0, "arm": "naive", "memory_items_digest": "d0", "pathway_mode": "fault_missing_signal"},
    ]
    assert run_leakage_suite({}, clean_rows).leakage_free   # type: ignore[arg-type]
    diverged = clean_rows + [
        {"pair_index": 1, "arm": "carry_memory", "memory_items_digest": "d1", "pathway_mode": "retrieved"},
        {"pair_index": 1, "arm": "naive", "memory_items_digest": "d2", "pathway_mode": "fault_missing_signal"},
    ]
    report = run_leakage_suite({}, diverged)   # type: ignore[arg-type]
    assert any(d.path_id == "P12" for d in report.detections)
    bypassed = [
        {"pair_index": 0, "arm": "carry_memory", "memory_items_digest": "d0", "pathway_mode": "retrieved"},
        {"pair_index": 0, "arm": "naive", "memory_items_digest": "d0", "pathway_mode": "retrieved"},
    ]
    report = run_leakage_suite({}, bypassed)   # type: ignore[arg-type]
    assert any(d.path_id == "P12" for d in report.detections), "naive 非 fault 断连必须检出"


def test_detection_severity_oracle_s0() -> None:
    """真值/oracle 交叉路径定级 S0（HLD §13.3；其余 S1）。"""
    severities = {p.path_id: p.severity for p in PROBES}
    assert {severities["P02"], severities["P04"], severities["P05"],
            severities["P06"], severities["P14"]} == {"S0"}
    assert severities["P01"] == "S1"


def test_probe_coverage_matrix_complete() -> None:
    """Q-L13-05 C0 期义务（REV-0012 R7）：14 路径全有源 + 三源深化状态显式。"""
    from galatea.evidence.evaluator.leakage import probe_coverage_report

    report = probe_coverage_report()
    assert report["paths"] == 14 and report["missing_paths"] == []
    status = report["deepening_status"]
    assert all("已上线" in v for v in status.values())
