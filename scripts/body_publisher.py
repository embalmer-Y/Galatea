"""体模拟源（Q-L13-16④：宿主 zenoh 网的电源/执行器流承载——Tessera 节点部署到主机网前的过渡源）。

**如实标注**：发布于 `tessera/galatea/gbridge/**` 命名空间（gbridge = Galatea 桥体模拟，
与真机节点命名空间显式区分——禁冒充真机）。确定性正弦摆动（零 RNG）。

    ~/zenoh_venv/bin/python scripts/body_publisher.py --duration 3600 --router tcp/127.0.0.1:7447
    # --duration 0 = 无限（systemd 服务模式，SIGTERM 退出）
"""
from __future__ import annotations

import argparse
import json
import math
import signal
import sys
import time

import cbor2
import zenoh

stop = {"flag": False}


def _graceful(signum: int, _frame: object) -> None:
    stop["flag"] = True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="体模拟源（gbridge 命名空间）")
    parser.add_argument("--duration", type=float, default=0.0, help="秒；0 = 无限（服务模式）")
    parser.add_argument("--router", default="tcp/127.0.0.1:7447")
    args = parser.parse_args(argv)
    signal.signal(signal.SIGTERM, _graceful)
    signal.signal(signal.SIGINT, _graceful)

    conf = zenoh.Config()
    conf.insert_json5("connect", json.dumps({"endpoints": [args.router]}))
    session = zenoh.open(conf)
    pub_power = session.declare_publisher("tessera/galatea/gbridge/sys/power")
    pub_act = session.declare_publisher("tessera/galatea/gbridge/dbpwm/telemetry")
    print(f"body publisher start: router={args.router} duration={args.duration or 'forever'}",
          flush=True)
    i = 0
    t0 = time.monotonic()
    while not stop["flag"] and (args.duration <= 0 or time.monotonic() - t0 < args.duration):
        used = int(250 + 200 * math.sin(i / 10.0))            # 确定性摆动 50..450 mA
        pub_power.put(cbor2.dumps({"ver": 1, "kind": 97, "budget_ma": 500, "used_ma": used,
                                   "peak_ma": 450, "wall_ms": int(i * 200)}))
        pub_act.put(cbor2.dumps({"ver": 1, "kind": 96, "dev": 2,
                                 "value_u": int(300000 + 100000 * math.sin(i / 7.0)),
                                 "wall_ms": int(i * 200)}))
        i += 1
        time.sleep(0.2)
    session.close()
    print(f"body publisher stop: samples={i}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
