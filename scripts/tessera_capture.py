"""Tessera 活网捕获（P2 单元 E 地面层；Q-L10-16 设备事件证据采集）。

在 zenoh 活网环境运行（本机 WSL——S3 板 + 路由 7447 在线）：
    ~/zenoh_venv/bin/pip install cbor2
    PYTHONPATH=~/galatea ~/zenoh_venv/bin/python scripts/tessera_capture.py \
        --seconds 15 --out evidence/tessera_bridge/capture.json
判据：≥2 主题、≥10 样本经桥解码为 Galatea 合同包（digest 可复算）。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

from galatea.env.tessera_bridge import sample_from_wire

_REPO = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tessera 活网桥捕获")
    parser.add_argument("--seconds", type=int, default=15)
    parser.add_argument("--router", default="tcp/127.0.0.1:7447")
    parser.add_argument("--out", type=Path, default=Path("evidence/tessera_bridge/capture.json"))
    args = parser.parse_args(argv)

    import zenoh                                          # 部署面惰性依赖

    samples: list[dict[str, object]] = []
    keys: Counter[str] = Counter()
    decode_fail: list[str] = []
    cycle = 0

    def on_sample(sample: zenoh.Sample) -> None:
        nonlocal cycle
        key = str(sample.key_expr)
        keys[key] += 1
        raw = bytes(sample.payload)
        try:
            s = sample_from_wire(key, raw, cycle)
        except (ValueError, Exception) as broken:         # 未映射 suffix/解码失败——留痕不静默
            decode_fail.append(f"{key}: {type(broken).__name__}: {broken}")
            return
        cycle += 1
        samples.append({
            "key": key, "carrier": s.carrier, "schema": s.schema,
            "payload": json.loads(s.payload_text),
            "payload_digest": s.payload_digest, "raw_digest": s.raw_digest,
            "cycle": cycle,
        })

    conf = zenoh.Config()
    conf.insert_json5("connect", json.dumps({"endpoints": [f"tcp/{args.router}"]}))
    session = zenoh.open(conf)
    sub = session.declare_subscriber("tessera/**", on_sample)
    time.sleep(args.seconds)
    sub.undeclare()
    session.close()

    by_carrier = Counter(s["carrier"] for s in samples)
    report = {
        "router": args.router, "seconds": args.seconds,
        "keys_seen": dict(keys), "packets_built": len(samples),
        "by_carrier": dict(by_carrier), "decode_fail": decode_fail[:10],
        "samples_head": samples[:6],
        "passed": len(samples) >= 10 and len(by_carrier) >= 1,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                        encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("keys_seen", "packets_built", "by_carrier")},
                     indent=1, ensure_ascii=False))
    print(f"verdict={'PASS' if report['passed'] else 'FAIL'} report={args.out}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
