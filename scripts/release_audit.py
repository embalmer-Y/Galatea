"""发布供应链审计（Q-L13-15⑤：require-hashes 强化兑现；H1 移交构建面）。

    uv run python scripts/release_audit.py [--lock uv.lock]

判据：uv.lock 中每个 package 的所有 wheels/sdist 条目均带哈希（hash ≥1 且每条目有 hash 字段）
→ 全覆盖 = PASS；输出锁文件整体 digest（发布锚）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tomllib
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="uv.lock 哈希覆盖审计")
    parser.add_argument("--lock", type=Path, default=Path("uv.lock"))
    args = parser.parse_args(argv)
    data = tomllib.loads(args.lock.read_text(encoding="utf-8"))
    packages = data.get("package", [])
    missing: list[str] = []
    total_entries = 0
    for pkg in packages:
        for source in pkg.get("wheels", []) + ([pkg["sdist"]] if "sdist" in pkg else []):
            total_entries += 1
            if not source.get("hash"):
                missing.append(f"{pkg['name']}:{source.get('url', '?')[:60]}")
    lock_digest = hashlib.sha256(args.lock.read_bytes()).hexdigest()
    report = {
        "lock": str(args.lock), "lock_sha256": lock_digest,
        "packages": len(packages), "hashable_entries": total_entries,
        "entries_missing_hash": len(missing), "missing": missing[:10],
        "require_hashes_satisfied": not missing and total_entries > 0,
    }
    out = Path("evidence/release_audit.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + chr(10), encoding="utf-8")
    print(json.dumps(report, indent=1, sort_keys=True))
    print(f"verdict={'PASS' if report['require_hashes_satisfied'] else 'FAIL'} report={out}")
    return 0 if report["require_hashes_satisfied"] else 1


if __name__ == "__main__":
    sys.exit(main())
