"""H1 收口命令（entry h1）：四判据复跑 + 汇总工件落盘（REV-0024 R6：生成器入库）。"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[3]
_LESION_LIST = ("none", "affect_off", "goals_off", "memory_off", "language_off",
                "metacontrol_off", "perception_off")


def run_h1_hardening_eval(out_dir: Path | None = None) -> dict[str, Any]:
    """四判据复跑 + 汇总落盘（seed 记录在案——REV-0024 R6 可复算口径）。"""
    from galatea.evidence.control.h1_hardening import (
        fault_injection_and_recovery,
        i3_independent_reproduction,
        long_run_stability,
        supply_chain_audit,
    )

    out_dir = out_dir or _ROOT / "evidence" / "h1_hardening"
    out_dir.mkdir(parents=True, exist_ok=True)
    seed = hashlib.sha256(b"h1-hardening-eval").digest()   # 评测 seed（记录于工件 seed_hex）
    recording = _ROOT / "evidence" / "c4_recording" / "recording_v1.json"
    out: dict[str, Any] = {
        "seed_hex": seed.hex(),
        "long_run": long_run_stability(seed),
        "fault_recovery": fault_injection_and_recovery(seed),
        "supply_chain": supply_chain_audit(_ROOT),
        "i3_reproduction": i3_independent_reproduction(_ROOT, recording, n=8),
    }
    out["all_stable"] = all(
        out[k]["stable"]
        for k in ("long_run", "fault_recovery", "supply_chain", "i3_reproduction"))
    (out_dir / "h1-evaluation-summary.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8", newline="")
    return out


def main() -> int:
    from galatea.evidence.control.lesion_battery import run_lesion

    summary = run_h1_hardening_eval()
    lesion_results = {lesion: run_lesion(_ROOT, lesion,
                      __import__("galatea.evidence.control.recording",
                                 fromlist=["load_recording"]).load_recording(
                          _ROOT / "evidence" / "c4_recording" / "recording_v1.json")).selective
                      for lesion in _LESION_LIST
                      if lesion not in ("none", "language_off")}
    print(f"h1: all_stable={summary['all_stable']} "
          f"long_run={summary['long_run']['stable']} "
          f"fault={summary['fault_recovery']['stable']} "
          f"supply={summary['supply_chain']['stable']} "
          f"i3={summary['i3_reproduction']['stable']} "
          f"lesion_all_selective={all(lesion_results.values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
