"""P1 sealed 语料采集（Q-L13-13 sealed_corpus；在目标主机上运行——生产桥真实 /sys 读数）。

用法（主机 192.168.2.91，部署后）：
    cd ~/galatea && ~/.local/bin/uv run python scripts/capture_sealed_corpus.py \
        --cycles 65 --period-ms 500 --out evidence/p1_physio_sealed/corpus.jsonl
输出：JSONL（首行 header = profile/参数/流 sha256；后续每行 = raw_view + payload_digest）
纪律：读数失败 fail-closed（任何源不可读 → 退出非 0——禁静默缺源语料）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

from galatea.env.physio.bridge import PhysioBridge
from galatea.env.physio.ports import load_p1_physio_profile


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P1 sealed 语料采集（生产桥 + 真实 /sys）")
    parser.add_argument("--cycles", type=int, default=65)
    parser.add_argument("--period-ms", type=int, default=500)
    parser.add_argument("--out", type=Path, default=Path("evidence/p1_physio_sealed/corpus.jsonl"))
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args(argv)

    profile = load_p1_physio_profile(args.repo_root / "config/profiles/p1_physio.profile.yaml")
    if args.period_ms != profile.period_ms:
        print(f"CERT_FAIL: period {args.period_ms} != frozen {profile.period_ms}", file=sys.stderr)
        return 1
    bridge = PhysioBridge(profile)                     # 默认 reader = 真实 /sys + procfs
    lines: list[str] = []
    prev = None
    for cycle in range(args.cycles):
        started = time.monotonic()
        record = bridge.sample(cycle)
        delivery = bridge.build_delivery(record, prev)
        lines.append(json.dumps(
            {"record": delivery.evidence_raw, "busy_rate": delivery.busy_rate,
             "payload_digest": delivery.evidence_payload_digest},
            sort_keys=True, separators=(",", ":")))
        prev = record
        remain = args.period_ms / 1000.0 - (time.monotonic() - started)
        if remain > 0 and cycle < args.cycles - 1:
            time.sleep(remain)
    blob = "".join(line + "\n" for line in lines).encode("utf-8")
    stream_sha = hashlib.sha256(blob).hexdigest()
    header = json.dumps({
        "kind": "p1_sealed_corpus_header", "profile": f"{profile.profile_id}@{profile.version}",
        "capture_cycles": args.cycles, "capture_period_ms": args.period_ms,
        "host_platform": sys.platform, "python": sys.version.split()[0],
        "stream_sha256": stream_sha, "records": args.cycles,
    }, sort_keys=True, separators=(",", ":"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(header + "\n" + blob.decode("utf-8"), encoding="utf-8")
    print(f"corpus={args.out}")
    print(f"stream_sha256={stream_sha}")
    print(f"records={args.cycles}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
