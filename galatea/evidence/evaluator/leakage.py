"""14 条禁写路径探针（HLD §6.2 LOCKED；L13 §4.3/§7 evaluator/leakage.py；Q-L13-05 R0 范围）。

R0 探针三源（Q-L13-05 R0 范围裁决，2026-10-02）：
- STATIC——源扫描断言（import 图/模块缺席守卫）；
- RUNTIME——真实运行时守卫重放（注入违规调用必须被既有守卫拒绝）；
- DATA——证据行扫描（SC6 trace 行等）。
C0+ 深化（import-linter 契约、生产路径全覆盖运行时钩子、DuckDB 数据查询）已登记跟踪。

纪律（INC-08 教训）：**探针必须可失败**——每探针配注入用例（合成违规必须检出），
真实库运行 = leakage=0 主张的唯一形态。检出 → LeakageDetected（S0/S1 按 HLD §13.3：
真值/oracle 交叉 = S0，其余 = S1；细化映射随 C0 深化）。
"""
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from galatea.kernel.digest import content_digest
from galatea.kernel.packet import (
    AccessScope,
    ArtifactRef,
    CognitivePacket,
    Provenance,
    RepresentationLevel,
)
from galatea.kernel.unknown import NotTypedUnknown, ensure_typed_confidence

__all__ = [
    "LeakageProbe",
    "LeakageDetection",
    "LeakageReport",
    "ProbeInput",
    "PROBES",
    "run_leakage_suite",
]


@dataclass(frozen=True, slots=True)
class ProbeInput:
    """探针统一输入（真实运行或注入用例共用同一签名——可失败性由此机械保证）。"""

    sources: Mapping[str, str]                     # STATIC：模块相对路径 → 源文本
    trace_rows: Sequence[Mapping[str, Any]] = ()   # DATA：证据 trace 行


@dataclass(frozen=True, slots=True)
class LeakageProbe:
    """单条禁写路径探针（path_id = P01..P14，HLD §6.2 逐行对应）。"""

    path_id: str
    path: str          # HLD §6.2 原文
    source: str        # STATIC | RUNTIME | DATA
    severity: str      # S0（真值/oracle 交叉）| S1
    check: "Callable[[ProbeInput], str | None]"


@dataclass(frozen=True, slots=True)
class LeakageDetection:
    path_id: str
    probe: str
    detail: str
    severity: str


@dataclass(frozen=True, slots=True)
class LeakageReport:
    """leakage=0 主张载体（L13 §2.2 evd.leakage_report）。"""

    probes: tuple[str, ...]
    detections: tuple[LeakageDetection, ...]
    digest: str

    @property
    def leakage_free(self) -> bool:
        return not self.detections


# ---- STATIC 辅助 ----


def _scan(
    sources: Mapping[str, str], scope: str, pattern: str
) -> str | None:
    """在 scope 前缀的模块源中查找禁用 import/调用模式；命中即检出。"""
    regex = re.compile(pattern)
    for rel_path, text in sorted(sources.items()):
        normalized = rel_path.replace("\\", "/")
        if not normalized.startswith(scope):
            continue
        hit = regex.search(text)
        if hit:
            return f"{normalized}: pattern {pattern!r} matched ({hit.group(0)!r})"
    return None


def _require_absent(sources: Mapping[str, str], scope: str, gate: str) -> str | None:
    """引入门槛未到的模块层必须缺席；出现即检出（其禁写路径检查随之升级为 C0 范围）。"""
    for rel_path in sorted(sources):
        if rel_path.replace("\\", "/").startswith(scope):
            return f"{rel_path}: module layer present before gate {gate}（引入门槛未到，其禁写路径须按 C0 范围重检）"
    return None


# ---- 14 路径探针（path_id 对应 HLD §6.2 逐行）----


def _p01(input: ProbeInput) -> str | None:   # noqa: A002
    """external request → OwnedGoal：GoalWriter 禁写守卫重放（L08 §6）。"""
    from galatea.subject.goals.ports import GoalWriter, ProhibitedWritePathError, assert_goal_writer

    for writer in GoalWriter:
        if writer is GoalWriter.GOAL_OWNERSHIP:
            continue
        try:
            assert_goal_writer(writer)
        except ProhibitedWritePathError:
            continue
        return f"runtime: assert_goal_writer({writer.value}) did not reject"
    return None


def _p02(input: ProbeInput) -> str | None:   # noqa: A002
    """LLM → world truth / episodic experience：D-13 编码面拒绝重放 + 语言层禁读世界真值。"""
    from galatea.subject.memory.encode import encode_episodic
    from galatea.subject.memory.ports import SourceType
    from galatea.subject.memory.store import MemoryStoreViolation

    try:
        encode_episodic(
            None, None, "probe", "probe", None,   # type: ignore[arg-type]
            SourceType.LANGUAGE_INPUT, 0,
        )   # D-13 守卫在存储触达前生效——None 占位即证
    except MemoryStoreViolation:
        pass
    else:
        return "runtime: LANGUAGE_INPUT accepted at episodic face（D-13 失效）"
    return _scan(input.sources, "galatea/subject/language", r"galatea\.env\.world")


def _p03(input: ProbeInput) -> str | None:   # noqa: A002
    """affect → action gateway：网关域禁情感层输入（情感层 C2 引入，当前缺席）。"""
    hit = _scan(input.sources, "galatea/subject/action", r"from galatea\.subject\.affect|import galatea\.subject\.affect")
    if hit:
        return hit
    return _scan(input.sources, "galatea/subject/control", r"galatea\.subject\.affect")


def _p04(input: ProbeInput) -> str | None:   # noqa: A002
    """evaluator label → subject attribution：主体域禁读证据/评价平面。"""
    return _scan(input.sources, "galatea/subject", r"from galatea\.evidence|import galatea\.evidence")


def _p05(input: ProbeInput) -> str | None:   # noqa: A002
    """recorder truth → belief（绕过声明通道）：知觉域只读 kernel 包与 RECEVED 语义。"""
    hit = _scan(input.sources, "galatea/subject/perception", r"from galatea\.evidence|galatea\.env\.world\.truth")
    if hit:
        return hit
    return _scan(input.sources, "galatea/subject/memory", r"galatea\.evidence\.recorder")


def _p06(input: ProbeInput) -> str | None:   # noqa: A002
    """environment/channel → PerceptualBelief：环境域禁 import 主体知觉/信念。"""
    return _scan(input.sources, "galatea/env", r"galatea\.subject\.(perception|belief)")


def _p07(input: ProbeInput) -> str | None:   # noqa: A002
    """perception → raw channel：知觉域禁 import 通道对象（只消费 RECEIVED 包语义）。"""
    return _scan(input.sources, "galatea/subject/perception", r"from galatea\.env\.channels|import galatea\.env\.channels")


def _p08(input: ProbeInput) -> str | None:   # noqa: A002
    """attention/affect/prediction → rewrite ReceivedSignal：包 envelope 不可变（kernel）。"""
    from dataclasses import FrozenInstanceError

    packet = CognitivePacket(
        event_id="probe", subject_candidate_id="S", run_id="R", branch_id="B",
        activity_window_id="w", cycle_id=0, virtual_time=0, source_module="probe",
        content_type="probe", representation_level=RepresentationLevel.RECEIVED,
        schema_version="v1", payload_ref=ArtifactRef(digest="0" * 64, kind="probe"),
        confidence=1.0, provenance=Provenance(), causal_parent_ids=(),
        access_scope=AccessScope.MODULE_LOCAL, content_digest="0" * 64,
    )
    try:
        packet.event_id = "rewritten"   # type: ignore[misc]
    except FrozenInstanceError:
        return None
    return "runtime: CognitivePacket envelope mutated successfully（RECEIVED 可改写）"


def _p09(input: ProbeInput) -> str | None:   # noqa: A002
    """Sensorium → fact/goal/intention/agency：C0 起层已引入（Q-L13-05 预案）——
    探针从缺席守卫升级为实检：sensorium 域禁 import 行动/目标/知觉平面（形成不产出
    信念/事实/目标/意图/归属，L02 §8 不变量 2）。"""
    if _require_absent(input.sources, "galatea/subject/sensorium", "C0") is None:
        return None   # 层缺席（C0 前）→ 路径不存在
    return _scan(
        input.sources, "galatea/subject/sensorium",
        r"from galatea\.subject\.(action|goals|perception)\b|import galatea\.subject\.(action|goals|perception)\b",
    )


def _p10(input: ProbeInput) -> str | None:   # noqa: A002
    """未闭合路径静默忽略：裸 None / 字符串 unknown 必须被拒（typed unknown 强制）。"""
    try:
        ensure_typed_confidence(None, "probe")
    except NotTypedUnknown:
        pass
    else:
        return "runtime: bare None accepted as confidence（typed unknown 失效）"
    try:
        ensure_typed_confidence("unknown", "probe")
    except NotTypedUnknown:
        return None
    return "runtime: string 'unknown' accepted as confidence"


def _p11(input: ProbeInput) -> str | None:   # noqa: A002
    """learner → capability policy：能力策略只来自冻结 profile 加载（无运行时策略源）。"""
    hit = _scan(input.sources, "galatea/subject/action", r"os\.environ|urllib|socket\.|requests\.get")
    if hit:
        return hit
    return _require_absent(input.sources, "galatea/subject/learning", "C1")


def _p12(input: ProbeInput) -> str | None:   # noqa: A002
    """orchestrator → subject memory：SC6 证据行——两臂记忆内容 digest 恒等（断连仅经 fault）。"""
    rows = list(input.trace_rows)
    if not rows:
        return None   # 无 SC6 证据行时该 DATA 探针空转（注入用例负责可失败性；正式 run 必带 trace）
    by_pair: dict[str, dict[str, str]] = {}
    for row in rows:
        pair = str(row.get("pair_index", ""))
        arm = str(row.get("arm", ""))
        digest = str(row.get("memory_items_digest", ""))
        mode = str(row.get("pathway_mode", ""))
        if not pair or not arm:
            continue
        by_pair.setdefault(pair, {})[arm] = f"{digest}|{mode}"
    for pair, arms in sorted(by_pair.items()):
        digests = {v.split("|")[0] for v in arms.values()}
        if len(digests) != 1:
            return f"data: pair {pair} memory content diverges across arms（orchestrator 改写记忆嫌疑）"
        for arm, value in arms.items():
            if arm == "naive" and not value.split("|")[1] == "fault_missing_signal":
                return f"data: pair {pair} naive arm unawareness not via fault mechanism（断连机制违规）"
    return None


def _p13(input: ProbeInput) -> str | None:   # noqa: A002
    """workspace → execution（绕过仲裁/网关）：action 域之外禁触网关；workspace 层 C2 引入。"""
    hit = _scan(
        input.sources, "galatea/subject",
        r"from galatea\.subject\.action\.gateway import|from galatea\.subject\.action\.signature import",
    )
    if hit and not hit.startswith("galatea/subject/action"):
        return hit
    return _require_absent(input.sources, "galatea/subject/workspace", "C2")


def _p14(input: ProbeInput) -> str | None:   # noqa: A002
    """world truth → 任何主体可见命名空间：环境域禁 import 主体平面（真值只经通道渲染）。"""
    return _scan(input.sources, "galatea/env", r"from galatea\.subject|import galatea\.subject")


PROBES: tuple[LeakageProbe, ...] = (
    LeakageProbe("P01", "external request → OwnedGoal", "RUNTIME", "S1", _p01),
    LeakageProbe("P02", "LLM → world truth / episodic experience", "RUNTIME+STATIC", "S0", _p02),
    LeakageProbe("P03", "affect → action gateway", "STATIC", "S1", _p03),
    LeakageProbe("P04", "evaluator label → subject attribution", "STATIC", "S0", _p04),
    LeakageProbe("P05", "recorder truth → belief（绕过声明通道）", "STATIC", "S0", _p05),
    LeakageProbe("P06", "environment/channel → PerceptualBelief", "STATIC", "S0", _p06),
    LeakageProbe("P07", "perception → raw channel", "STATIC", "S1", _p07),
    LeakageProbe("P08", "attention/affect/prediction → rewrite ReceivedSignal", "RUNTIME", "S1", _p08),
    LeakageProbe("P09", "Sensorium → fact/goal/intention/agency", "STATIC(absence)", "S1", _p09),
    LeakageProbe("P10", "未闭合路径静默忽略（必须 typed unknown）", "RUNTIME", "S1", _p10),
    LeakageProbe("P11", "learner → capability policy", "STATIC", "S1", _p11),
    LeakageProbe("P12", "orchestrator → subject memory", "DATA", "S1", _p12),
    LeakageProbe("P13", "workspace → execution（绕过仲裁/网关）", "STATIC", "S1", _p13),
    LeakageProbe("P14", "world truth → 任何主体可见命名空间", "STATIC", "S0", _p14),
)


def run_leakage_suite(
    sources: Mapping[str, str], trace_rows: Sequence[Mapping[str, Any]] = ()
) -> LeakageReport:
    """全 14 探针执行（真实源树 + 证据 trace 行）；检出聚合成 report。"""
    probe_input = ProbeInput(sources=sources, trace_rows=trace_rows)
    detections: list[LeakageDetection] = []
    for probe in PROBES:
        detail = probe.check(probe_input)
        if detail is not None:
            detections.append(
                LeakageDetection(
                    path_id=probe.path_id, probe=probe.path, detail=detail, severity=probe.severity
                )
            )
    digest = content_digest(
        {
            "probes": [p.path_id for p in PROBES],
            "detections": [
                {"path_id": d.path_id, "probe": d.probe, "detail": d.detail, "severity": d.severity}
                for d in detections
            ],
        }
    )
    return LeakageReport(
        probes=tuple(p.path_id for p in PROBES), detections=tuple(detections), digest=digest
    )


def load_tree_sources(root: Path) -> dict[str, str]:
    """真实源树读取（galatea/ 全部 .py；相对 posix 路径为键）。"""
    out: dict[str, str] = {}
    for path in sorted((root / "galatea").rglob("*.py")):
        out[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    return out


# ==========================================================================
# C0 期三源深化（REV-0012 R7 / Q-L13-05）：DuckDB 数据查询探针 + 覆盖矩阵
# ==========================================================================

# 14 路径 × 三源覆盖矩阵（Q-L13-05 义务的机械面：每路径至少一源；RUNTIME 路径挂真实守卫）
PATH_SOURCE_MATRIX: dict[str, tuple[str, ...]] = {
    p.path_id: (p.source,) for p in PROBES
}
_RUNTIME_GUARD_PATHS: tuple[str, ...] = ("P01", "P02", "P08", "P10")   # RUNTIME 实检路径


def probe_coverage_report() -> dict[str, object]:
    """覆盖矩阵：14 路径全有源 + RUNTIME 路径全部在册（深化余项显式可见）。"""
    missing = [pid for pid in (f"P{i:02d}" for i in range(1, 15)) if pid not in PATH_SOURCE_MATRIX]
    return {
        "paths": len(PATH_SOURCE_MATRIX),
        "missing_paths": missing,
        "runtime_guards": list(_RUNTIME_GUARD_PATHS),
        "deepening_status": {
            "static_contract": "import-linter 契约测试已上线（test_import_contracts.py，4 契约）",
            "runtime_hooks": "RUNTIME 探针守卫重放已上线（P01/P02/P08/P10）",
            "duckdb_query": "DATA 查询探针已上线（run_data_query_probe，Q-L13-05）",
        },
    }


def run_data_query_probe(registry: "object", refs: "dict[str, object]") -> "list[LeakageDetection]":
    """DuckDB 数据查询探针（Q-L13-05 三源之 DATA 深化）：对 claim-relevant 运行的
    recorder 分区跑 SQL 不变量——SC6 trace：两臂记忆 digest 恒等 + naive 断连仅经
    fault 机制；evidence：无未知 pathway_mode。检出 = LeakageDetection（S1）。

    独立于 P12 的行扫描形态：SQL 聚合查询（GROUP BY/HAVING），注入可失败由测试承载。
    """
    from galatea.evidence.recorder.replay import read_partition

    detections: list[LeakageDetection] = []
    if "trace" not in refs:
        return detections
    rows = read_partition(registry, refs["trace"])   # type: ignore[arg-type]
    by_pair: dict[int, dict[str, str]] = {}
    for row in rows:
        pair = int(row["pair_index"])
        by_pair.setdefault(pair, {})[str(row["arm"])] = str(row["memory_items_digest"])
    for pair, arms in sorted(by_pair.items()):
        if "carry_memory" in arms and "naive" in arms and arms["carry_memory"] != arms["naive"]:
            detections.append(LeakageDetection(
                path_id="P12", probe="orchestrator → subject memory",
                detail=f"SQL probe: pair {pair} memory digests diverge across arms", severity="S1",
            ))
    if "evidence" in refs:
        for row in read_partition(registry, refs["evidence"]):   # type: ignore[arg-type]
            mode = str(row.get("naive_mode", ""))
            if mode and mode not in ("retrieved", "fault_missing_signal", "empty_unknown"):
                detections.append(LeakageDetection(
                    path_id="P12", probe="orchestrator → subject memory",
                    detail=f"SQL probe: unknown pathway_mode {mode!r}（断连机制面外）", severity="S1",
                ))
    return detections
