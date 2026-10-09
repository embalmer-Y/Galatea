"""E1 收口命令（entry e1）：I2 报告 + 60 格闭合 + lesion 电池状态汇总落盘。"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[3]
_LESION_LIST = ("none", "affect_off", "goals_off", "memory_off", "language_off",
                "metacontrol_off", "perception_off")


def run_e1_closure(out_dir: Path | None = None) -> dict[str, Any]:
    """E1 门判据收口汇总（60 格 + I2 + lesion 选择性 + 保护集计数）。"""
    from galatea.evidence.control.lesion_battery import run_lesion

    out_dir = out_dir or _ROOT / "evidence" / "e1_integration"
    closure = json.loads(
        (out_dir / "decision-registry-closure.json").read_text(encoding="utf-8"))
    i2 = json.loads((out_dir / "I2-c5-gain-001.json").read_text(encoding="utf-8"))
    replay = __import__("galatea.evidence.control.recording",
                        fromlist=["load_recording"]).load_recording(
        _ROOT / "evidence" / "c4_recording" / "recording_v1.json")
    lesion_results = {lesion: run_lesion(_ROOT, lesion, replay).selective
                      for lesion in _LESION_LIST}
    # 选择性聚合域 = 六实 lesion（none = 基线排除；language_off 保持面 = digest
    # 恒等专用断言承载【test_language_lesion_preserves...】——selective 标记豁免）
    core_lesions = [l for l in _LESION_LIST if l not in ("none", "language_off")]
    summary: dict[str, Any] = {
        "closure": closure,
        "i2_match": i2["match"],
        "lesion_selective": lesion_results,
        "lesion_all_selective": all(lesion_results[l] for l in core_lesions),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "e1-closure-summary.json").write_text(
        json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    return summary


def main() -> int:
    summary = run_e1_closure()
    print(f"e1: closure={summary['closure']['gate']} "
          f"i2={summary['i2_match']} "
          f"lesion_all_selective={summary['lesion_all_selective']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
