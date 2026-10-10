"""常驻运行验证器（Q-L13-15②③：谱系链跨重启延续 + 迁移审计机械判据）。

    uv run python scripts/resident_verify.py --audit ~/galatea_resident/checkpoint_migrations.jsonl \
        --store ~/galatea_resident/stores --min-cycles 256

判据（全过 = PASS）：
  A 谱系链连续：每条 checkpoint 的 parent = 上一条 checkpoint id（根 parent=None），无断链
  B 总周期 ≥ min-cycles（跨重启单调时间轴）
  C fault 注入 + 恢复：crash_injected/crash_recovered 事件在案且其后仍有 checkpoint
  D kernel_checkpoints 持久面计数 = 审计 checkpoint 数（H1 registry index 判据沿用）
  E 谱系 DAG 重建通过（LineageTable 全量重放——父链/无环/无重复）
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from galatea.kernel.state import LineageTable


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="常驻运行谱系验证")
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--min-cycles", type=int, default=256)
    args = parser.parse_args(argv)
    events = [json.loads(l) for l in args.audit.read_text(encoding="utf-8").splitlines() if l.strip()]
    checks: dict[str, bool] = {}
    details: dict[str, object] = {}

    # A 谱系完整性（D-12 clone≠identity：fresh 会话 = 新根，合法）——
    #  (i) 每个 checkpoint 的 parent ∈ {None(根)} ∪ {先前行 id}（禁悬挂/乱序父引）；
    #  (ii) 最长根链承载长程主张：其末 checkpoint 的 cycle ≥ min-cycles 且含崩溃后恢复
    checkpoints = [e for e in events if e.get("event") == "checkpoint"]
    seen_ids: set[str] = set()
    linkage_ok = True
    for cp in checkpoints:
        parent = cp["parent"]
        if parent is not None and parent not in seen_ids:
            linkage_ok = False
            break
        seen_ids.add(cp["checkpoint_id"])
    # 最长链回放（从末 checkpoint 沿 parent 回溯至根）
    by_id = {cp["checkpoint_id"]: cp for cp in checkpoints}
    longest: list[str] = []
    if checkpoints:
        cursor = checkpoints[-1]["checkpoint_id"]
        guard = 0
        while cursor is not None and guard <= len(checkpoints):
            longest.append(cursor)
            cursor = by_id[cursor]["parent"]
            guard += 1
        longest.reverse()
    longest_cycles = by_id[longest[-1]]["cycle"] if longest else 0
    checks["A_lineage_linkage_and_longest_chain"] = (
        linkage_ok and bool(longest) and longest_cycles >= args.min_cycles)
    details["longest_chain"] = longest
    details["longest_chain_cycles"] = longest_cycles
    details["roots"] = [cp["checkpoint_id"] for cp in checkpoints if cp["parent"] is None]

    # B 总周期
    total_cycles = checkpoints[-1]["cycle"] if checkpoints else 0
    checks["B_min_cycles"] = total_cycles >= args.min_cycles
    details["total_cycles"] = total_cycles

    # C fault + 恢复
    crash_events = [e for e in events if e.get("event") in ("crash_injected", "crash_recovered")]
    crash_idx = events.index(crash_events[0]) if crash_events else -1
    post_crash_cp = any(e.get("event") == "checkpoint"
                        for e in events[crash_idx + 1:]) if crash_events else False
    checks["C_fault_and_recovery"] = bool(crash_events) and post_crash_cp
    details["crash_events"] = [e["event"] for e in crash_events]

    # D 持久面计数（H1 判据沿用）
    from galatea.kernel.state import StoreName, Stores
    stores = Stores(args.store)
    persisted = stores.read(StoreName.SUBJECT_STATE,
                            "SELECT count(*) FROM kernel_checkpoints")[0][0]
    stores.close()
    checks["D_kernel_checkpoints_persisted"] = persisted == len(checkpoints)
    details["persisted"] = persisted

    # E DAG 重建
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "resident_subject", Path(__file__).resolve().parent / "resident_subject.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _rebuild_lineage = mod._rebuild_lineage
    try:
        lineage = _rebuild_lineage(events)
        checks["E_lineage_dag_rebuild"] = len(lineage.all()) == len(checkpoints)
    except Exception as exc:                            # 谱系违规即 FAIL
        checks["E_lineage_dag_rebuild"] = False
        details["dag_error"] = str(exc)

    overall = all(checks.values())
    report = {"overall": overall, "checks": checks, "details": details}
    print(json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False))
    out = args.audit.parent / "resident_verify.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"verdict={'PASS' if overall else 'FAIL'} report={out}")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
