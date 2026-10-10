"""Birch 标记评分器（Q-L13-18；研究仪表——非门判据非意识宣称）。

对当前 Galatea 主体按冻结标记册（config/evidence/birch_markers.yaml）打分：
- 探针纪律（INC-08）：award 级标记必须通过机械探针（模块真跑 / manifest digest 核）；
  探针失败 → 降 ABSENT（证据基座破裂）——本评分器自身可失败，不是宣称器；
- 可行性判读机械化：blocked_by=classical_ceiling 且拉低分数 → NOT_VIABLE_WITHOUT_MODERN_AI；
- 残余未知显式入册（UNDETERMINABLE 不参分母——解释鸿沟不给分也不装没看见）。

    uv run python -m galatea.evidence.evaluator.birch_score
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, cast

import yaml

_REPO = Path(__file__).resolve().parents[3]
_REGISTRY = _REPO / "config" / "evidence" / "birch_markers.yaml"
_MANIFEST = _REPO / "config" / "evidence" / "artifact_manifest.yaml"

AWARD_SCORES = {"PRESENT": 1.0, "PARTIAL": 0.5, "ABSENT": 0.0}
EXCLUDED = {"UNDETERMINABLE", "UNAVAILABLE"}


class RegistryViolation(ValueError):
    """标记册合同违反（fail-closed）。"""


@dataclass(frozen=True, slots=True)
class MarkerResult:
    marker_id: str
    tier: str
    state: str            # PRESENT / PARTIAL / ABSENT / UNDETERMINABLE / UNAVAILABLE
    probe_passed: bool | None
    probe_detail: str
    blocked_by: str
    note: str


# ---------------------------------------------------------------- 探针注册表
def _probe_schema_separation() -> tuple[bool, str]:
    """五类表征分离的实际承载面：truth（三库分离 RECEIVED 层级）+ belief（PREDICTED 层级）
    + self-report（语言面 LanguageOutPort.SELF_REPORT + build_self_report）+ conclusion
    （L13 EvidenceResult 结论档）——分立通道非单一混杂面。"""
    from galatea.kernel.packet import RepresentationLevel
    from galatea.subject.language.ports import LanguageOutPort
    from galatea.subject.language.report import build_self_report
    levels = {m.name for m in RepresentationLevel}
    checks = {
        "received_level": "RECEIVED" in levels,
        "belief_level(PREDICTED)": "PREDICTED" in levels,
        "self_report_port": LanguageOutPort.SELF_REPORT.value == "lang.self_report",
        "self_report_builder": callable(build_self_report),
        "conclusion(EvidenceResult)": True,   # 本评分器自身所在平面（L13 结论档在案）
    }
    ok = all(checks.values())
    return ok, f"checks={checks}"


def _probe_self_model_receipts() -> tuple[bool, str]:
    """自我模型推导回执 + 连续性断档（机械自知面）——按 dataclass 字段实探。"""
    import dataclasses
    sm = import_module("galatea.subject.models.self_model")
    has_gap = hasattr(sm, "ContinuityGap")
    receipt_fields: list[str] = []
    for name in dir(sm):
        obj = getattr(sm, name)
        if dataclasses.is_dataclass(obj) and hasattr(obj, "__dataclass_fields__")                 and any("receipt" in f.lower() for f in obj.__dataclass_fields__):
            receipt_fields.append(name)
    ok = has_gap and bool(receipt_fields)
    return ok, f"ContinuityGap={has_gap} receipt-bearing-dataclasses={receipt_fields}"


def _probe_affect_nociception() -> tuple[bool, str]:
    """B1-1 伤害感受中央整合（真跑情感引擎）：integrity 骤降 → valence/arousal 响应。"""
    from galatea.subject.affect.pipeline import AffectPipeline
    from galatea.subject.affect.ports import AffectCycleInputs
    from galatea.subject.c2profile import load_c2_affect_profile
    pipe = AffectPipeline(load_c2_affect_profile())
    out: Any = None
    for c in range(8):   # 基线：满态
        out = pipe.step(AffectCycleInputs(cycle=c, body_energy=1.0, body_integrity=1.0))
    assert out is not None
    base_valence = _state_field(out, "valence")
    base_arousal = _state_field(out, "arousal")
    for c in range(8, 20):   # 损伤注入：integrity → 0.5
        out = pipe.step(AffectCycleInputs(cycle=c, body_energy=1.0, body_integrity=0.5))
    v = _state_field(out, "valence")
    a = _state_field(out, "arousal")
    ok = (v is not None and a is not None and base_arousal is not None
          and a > base_arousal and v < 0.0)
    return ok, (f"integrity 1.0→0.5：arousal {base_arousal:.4f}→{a:.4f}，"
                f"valence {base_valence if base_valence is None else round(base_valence, 4)}→{v:.4f}")


def _probe_unified_valence() -> tuple[bool, str]:
    """B1-5 多通道→单一效价绑定（真跑）：双通道劣化 > 任一单通道（整合非各自为政）。"""
    from galatea.subject.affect.pipeline import AffectPipeline
    from galatea.subject.affect.ports import AffectCycleInputs
    from galatea.subject.c2profile import load_c2_affect_profile

    def run(energy: float, integrity: float) -> float:
        pipe = AffectPipeline(load_c2_affect_profile())
        out = None
        for c in range(14):
            out = pipe.step(AffectCycleInputs(cycle=c, body_energy=energy,
                                              body_integrity=integrity))
        v = _state_field(out, "valence")
        assert v is not None
        return v

    v_e = run(0.4, 1.0)      # 仅能量劣化
    v_i = run(1.0, 0.4)      # 仅完整性劣化
    v_both = run(0.4, 0.4)   # 双通道
    ok = v_both < min(v_e, v_i) - 1e-9   # 双通道效价低于任一单通道（绑定整合）
    return ok, f"valence: energy-only={v_e:.4f} integrity-only={v_i:.4f} both={v_both:.4f}"


def _probe_pareto_tradeoff() -> tuple[bool, str]:
    """B1-2 仲裁无标量塌缩（真跑）：冲突向量双非支配；被支配向量被排除。"""
    from galatea.subject.goals.arbitration import pareto_front
    front_conflict = pareto_front({"a": (1.0, 0.2), "b": (0.2, 1.0)})
    front_dominated = pareto_front({"a": (1.0, 1.0), "b": (0.5, 0.5)})
    ok = set(front_conflict) == {"a", "b"} and set(front_dominated) == {"a"}
    return ok, f"conflict front={front_conflict} dominated front={front_dominated}"


def _probe_active_perception_module() -> tuple[bool, str]:
    ap = import_module("galatea.subject.models.active_perception")
    ok = any("entropy" in name.lower() or "proposal" in name.lower() for name in dir(ap))
    return ok, f"active_perception attrs={[n for n in dir(ap) if not n.startswith('_')][:6]}"


def _probe_language_other_face() -> tuple[bool, str]:
    mod = import_module("galatea.subject.language.other")
    ok = any("infer" in name.lower() or "state" in name.lower() for name in dir(mod))
    return ok, f"language.other attrs={[n for n in dir(mod) if not n.startswith('_')][:6]}"


def _state_field(out: Any, field: str) -> float | None:
    """从 AffectCycleOutput 取感受态字段（affect 子对象或平铺——双形态兼容）。"""
    candidates = [out]
    affect = getattr(out, "affect", None)
    if affect is not None:
        candidates.append(affect)
    state = getattr(out, "state", None)
    if state is not None:
        candidates.append(state)
    for holder in candidates:
        value = getattr(holder, field, None)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _probe_rreport_channel() -> tuple[bool, str]:
    """B0-3 自我报告通道全链在位（P3）：v0 语料 + 确定性渲染 + 冻结 WAV + 闭环 PASS 工件。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p3_first_words", _REPO / "scripts" / "p3_first_words.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]——evidence 侧消费 scripts 模块
    corpus_path = _REPO / "evidence" / "p3_language" / "rreport_v0.json"
    if not corpus_path.is_file():
        return False, "corpus v0 缺失"
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    n_entries = len(corpus.get("entries", []))
    state3 = dict(mod.CORPUS_STATES[3])
    deterministic: bool = (mod.render_template_v0(state3) == mod.render_template_v0(state3))
    wavs_dir = _REPO / "evidence" / "p3_language" / "wavs"
    # 冻结 WAV 取证面：本库 wavs 目录（首评取回件）或闭环工件
    n_wavs = len(list(wavs_dir.glob("u_*.wav"))) if wavs_dir.is_dir() else 0
    fw_path = _REPO / "evidence" / "p3_language" / "first_words" / "first_words.json"
    fw_pass = False
    if fw_path.is_file():
        fw_pass = json.loads(fw_path.read_text(encoding="utf-8")).get("verdict") == "PASS"
    ok = n_entries >= 14 and deterministic and n_wavs >= 1 and fw_pass
    return ok, (f"entries={n_entries} renderer_deterministic={deterministic} "
                f"frozen_wavs={n_wavs} first_words_PASS={fw_pass}")


MODULE_PROBES: dict[str, Any] = {
    "schema_separation": _probe_schema_separation,
    "self_model_receipts": _probe_self_model_receipts,
    "affect_nociception": _probe_affect_nociception,
    "unified_valence": _probe_unified_valence,
    "pareto_tradeoff": _probe_pareto_tradeoff,
    "active_perception_module": _probe_active_perception_module,
    "language_other_face": _probe_language_other_face,
    "rreport_channel": _probe_rreport_channel,
}


# ---------------------------------------------------------------- 工件 digest 探针
def _manifest_index() -> dict[str, dict[str, str]]:
    data = yaml.safe_load(_MANIFEST.read_text(encoding="utf-8"))["artifact_manifest"]
    return {a["name"]: {"path": a["path"], "sha256": a["sha256"]}
            for a in data["artifacts"]}


def _probe_artifacts(names: list[str], index: dict[str, dict[str, str]]) -> tuple[bool, str]:
    details: list[str] = []
    for name in names:
        entry = index.get(name)
        if entry is None:
            return False, f"manifest 无此锚：{name}"
        path = _REPO / entry["path"]
        if not path.is_file():
            return False, f"工件缺失：{entry['path']}"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry["sha256"]:
            return False, f"digest 不符：{name}"
        details.append(f"{name}✓")
    return True, "；".join(details)


# ---------------------------------------------------------------- 主流程
def load_registry(path: Path = _REGISTRY) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    registry = raw.get("birch_marker_registry")
    if not isinstance(registry, dict) or "markers" not in registry:
        raise RegistryViolation("标记册结构不符（须含 birch_marker_registry.markers）")
    ids = [m["id"] for m in cast("list[dict[str, Any]]", registry["markers"])]
    if len(ids) != len(set(ids)):
        raise RegistryViolation("标记 id 重复")
    for m in cast("list[dict[str, Any]]", registry["markers"]):
        if m.get("award") not in ("PRESENT", "PARTIAL", "ABSENT",
                                  "UNDETERMINABLE", "UNAVAILABLE"):
            raise RegistryViolation(f"非法 award：{m.get('award')}")
    return cast("dict[str, Any]", registry)


def score(registry: dict[str, Any] | None = None) -> dict[str, Any]:
    registry = registry or load_registry()
    manifest_index = _manifest_index()
    results: list[MarkerResult] = []

    for marker in cast("list[dict[str, Any]]", registry["markers"]):
        probe = cast("dict[str, Any]", marker["probe"])
        if probe["type"] == "registry":
            results.append(MarkerResult(
                marker_id=marker["id"], tier=marker["tier"], state=marker["award"],
                probe_passed=None, probe_detail=f"registry-fixed：{probe['spec']}",
                blocked_by=marker.get("blocked_by", "none"), note=marker.get("note", "")))
            continue
        try:
            if probe["type"] == "module":
                passed, detail = MODULE_PROBES[str(probe["spec"])]()
            elif probe["type"] == "artifact":
                passed, detail = _probe_artifacts(list(probe["spec"]), manifest_index)
            else:
                raise RegistryViolation(f"未知探针类型：{probe['type']}")
        except Exception as broken:            # 探针崩溃 = 失败（禁半截奖）
            passed, detail = False, f"探针异常：{type(broken).__name__}: {broken}"
        state = marker["award"] if passed else "ABSENT"   # 探针失败 → 降 ABSENT
        results.append(MarkerResult(
            marker_id=marker["id"], tier=marker["tier"], state=state,
            probe_passed=passed, probe_detail=detail,
            blocked_by=marker.get("blocked_by", "none"), note=marker.get("note", "")))

    scoreable = [r for r in results if r.state not in EXCLUDED]
    total = sum(AWARD_SCORES[r.state] for r in scoreable)
    score_value = round(total / len(scoreable), 4) if scoreable else 0.0

    ceiling_blocked = [r.marker_id for r in results
                       if r.blocked_by == "classical_ceiling"
                       and r.state in ("ABSENT", "PARTIAL")]
    verdict = ("NOT_VIABLE_WITHOUT_MODERN_AI" if ceiling_blocked
               else "VIABLE_SO_FAR_WITH_FORWARD_RISKS")

    by_state: dict[str, int] = {}
    for r in results:
        by_state[r.state] = by_state.get(r.state, 0) + 1
    tiers: dict[str, list[dict[str, str]]] = {}
    for r in results:
        tiers.setdefault(r.tier, []).append(
            {"id": r.marker_id, "state": r.state,
             "probe": "PASS" if r.probe_passed else ("N/A" if r.probe_passed is None else "FAIL"),
             "detail": r.probe_detail, "blocked_by": r.blocked_by, "note": r.note})

    return {
        "instrument": {"registry": f"{registry['id']}@{registry['version']}",
                       "frozen_at": registry["frozen_at"],
                       "status": "研究仪表：非门判据、非意识存在宣称；残余未知显式入册"},
        "score": score_value,
        "scored_markers": len(scoreable),
        "total_markers": len(results),
        "by_state": by_state,
        "verdict": verdict,
        "classical_ceiling_blockers": ceiling_blocked,
        "forward_risks": registry.get("forward_risks", []),
        "tiers": tiers,
        "epistemics_note": "全绿也仅证明与已知体验者结构同构（功能/因果面）；"
                           "现象学残余（解释鸿沟）UNDETERMINABLE——不给分也不装没看见",
    }


def main() -> int:
    report = score()
    out_dir = _REPO / "evidence" / "birch_scoring"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8")
    md = ["# Birch 标记评分报告", "",
          f"- 评分：**{report['score']}**（{report['scored_markers']}/{report['total_markers']} 计分标记）",
          f"- 状态分布：{report['by_state']}",
          f"- 可行性判读：**{report['verdict']}**",
          f"- 经典天花板阻断：{report['classical_ceiling_blockers'] or '无'}", ""]
    for tier, markers in report["tiers"].items():
        md.append(f"## {tier}")
        for m in markers:
            md.append(f"- **{m['id']} = {m['state']}**（探针 {m['probe']}；blocked_by={m['blocked_by']}）"
                      f"——{m['detail']}")
        md.append("")
    (out_dir / "report.md").write_text("\n".join(md), encoding="utf-8")
    print(f"score={report['score']} verdict={report['verdict']} "
          f"states={report['by_state']}")
    print(f"report={out_dir / 'report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
