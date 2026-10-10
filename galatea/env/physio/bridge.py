"""PhysIO Bridge（Q-L10-10③：物理源 → INTERO 合同 payload → RECEIVED 包）。

纪律（全部锚冻结文）：
- **合同 payload = MW0 对齐三键**（energy/integrity/events——ingest fail-closed 校验面；
  Q-L01-10 REV-0025 R5 勘误）；原始物理量只入证据侧 log（DeliveryFact 分离）；
- energy = 计算余量代理 = 1 − busy_rate；busy_rate = 1 − Δ(idle+iowait)/Δ(total)
  （/proc/stat cpu 聚合行；round 6dp；首 cycle 无差分 → busy=None → energy=1.0）
  ——ADR-G-0025 §7 R7 派生式成文；
- integrity = 恒 1.0（主机平台无损伤通道 v1）；events = 空（零新事件，Q-L02-05）；
- 包构造与 sensorium 测试装置逐字段同构（RECEIVED 层级；event_id 确定性可排序）；
- 决策路径零 RNG 零墙钟：采样时间戳是数据；reader 函数注入（测试零 /sys 依赖，
  生产默认真实 /sys + procfs）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from galatea.env.physio.hwmon import HwmonResolver
from galatea.env.physio.ports import P1PhysioProfile
from galatea.kernel.digest import content_digest
from galatea.kernel.packet import (
    AccessScope,
    ArtifactRef,
    CognitivePacket,
    Provenance,
    RepresentationLevel,
)

PROC_STAT = Path("/proc/stat")

# content_type = 载体串（ingest kind↔载体匹配面；env 侧字面量——P06 禁 import 主体平面，
# 值与 galatea.subject.sensorium.ingest.CARRIER_INTERO 逐字同源，双侧测试钉死一致性）
CARRIER_INTERO_CONTENT_TYPE = "channel.interoceptive.received.v1"


@dataclass(frozen=True, slots=True)
class TelemetryRecord:
    """单 cycle 原始采样（全部进证据侧 log；主体不可见）。"""

    cycle: int
    t_mono: float
    t_epoch: float
    hwmon_temps: dict[str, dict[str, int]]      # name → {tempN: 毫度}
    loadavg: tuple[float, float, float]
    stat_idle: int
    stat_total: int
    mem_available_kb: int
    net_rx_pkts: int
    net_tx_pkts: int

    def raw_view(self) -> dict[str, object]:
        """证据侧序列化视图（json.dumps sort_keys 稳定）。"""
        return {
            "cycle": self.cycle, "t_mono": self.t_mono, "t_epoch": self.t_epoch,
            "hwmon_temps": self.hwmon_temps,
            "loadavg": list(self.loadavg), "stat": {"idle": self.stat_idle, "total": self.stat_total},
            "mem_available_kb": self.mem_available_kb,
            "net": {"rx_pkts": self.net_rx_pkts, "tx_pkts": self.net_tx_pkts},
        }


@dataclass(frozen=True, slots=True)
class BridgeDelivery:
    """单 cycle 桥产物：主体侧合同包 + 证据侧 log 行（严格分离）。"""

    packet: CognitivePacket
    payload_text: str
    evidence_raw: dict[str, object]
    evidence_payload_digest: str
    busy_rate: float | None


def _read_proc_stat(path: Path) -> tuple[int, int]:
    """(idle+iowait, total)——cpu 聚合行；格式漂移 fail-closed。"""
    first = path.read_text(encoding="utf-8").splitlines()[0]
    if not first.startswith("cpu "):
        raise ValueError(f"proc stat format drift: {first[:40]!r}")
    parts = [int(x) for x in first.split()[1:]]
    if len(parts) < 5:
        raise ValueError("proc stat cpu row too short")
    return parts[3] + parts[4], sum(parts)


def _read_loadavg(path: Path) -> tuple[float, float, float]:
    parts = path.read_text(encoding="utf-8").split()[:3]
    return float(parts[0]), float(parts[1]), float(parts[2])


def _read_mem_available(path: Path) -> int:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1])
    raise ValueError("MemAvailable not found in meminfo")


def _read_net_pkts(path: Path, iface: str) -> tuple[int, int]:
    for line in path.read_text(encoding="utf-8").splitlines()[2:]:
        name, rest = line.split(":", 1)
        if name.strip() == iface:
            fields = rest.split()
            return int(fields[1]), int(fields[9])  # rx_pkts, tx_pkts
    raise ValueError(f"iface {iface} not found in netdev")


class PhysioBridge:
    """物理遥测桥（v1 被动期：INTERO 主机遥测；Tessera 流随设备事件扩展）。"""

    def __init__(
        self, profile: P1PhysioProfile, cycle_origin: int = 0,
        *, resolver: HwmonResolver | None = None,
        proc_stat_path: Path = PROC_STAT, loadavg_path: Path = Path("/proc/loadavg"),
        meminfo_path: Path = Path("/proc/meminfo"), netdev_path: Path = Path("/proc/net/dev"),
        monotonic_fn: Callable[[], float] | None = None, epoch_fn: Callable[[], float] | None = None,
        hwmon_names: tuple[str, ...] | None = None,
        net_iface: str = "enp3s0",
    ) -> None:
        if profile.carrier != "interoceptive":
            raise ValueError(f"v1 bridge carriers interoceptive only, got {profile.carrier}")
        self._profile = profile
        self._cycle_origin = cycle_origin          # t0 钉死（Q-L01-10④：单调计拍）
        self._resolver = resolver or HwmonResolver()
        self._proc_stat_path = proc_stat_path
        self._loadavg_path = loadavg_path
        self._meminfo_path = meminfo_path
        self._netdev_path = netdev_path
        self._mono = monotonic_fn or _default_monotonic
        self._epoch = epoch_fn or _default_epoch
        # R6（修订 1）：hwmon 名单 = profile 冻结源键（name 文件实值锚），禁硬编码
        self._hwmon_names = hwmon_names if hwmon_names is not None else tuple(
            source.path for source in profile.sources if source.kind == "hwmon"
        )
        self._net_iface = net_iface
        self._prev_stat: tuple[int, int] | None = None

    def sample(self, cycle: int) -> TelemetryRecord:
        """采集单 cycle 原始读数（全部非决策数据；reader 失败向上抛——调用方转 MISSING）。"""
        idle, total = _read_proc_stat(self._proc_stat_path)
        record = TelemetryRecord(
            cycle=cycle - self._cycle_origin,
            t_mono=round(self._mono(), 6),
            t_epoch=round(self._epoch(), 6),
            hwmon_temps={name: self._resolver.read_temps_millicelsius(name) for name in self._hwmon_names},
            loadavg=_read_loadavg(self._loadavg_path),
            stat_idle=idle,
            stat_total=total,
            mem_available_kb=_read_mem_available(self._meminfo_path),
            net_rx_pkts=0,
            net_tx_pkts=0,
        )
        rx, tx = _read_net_pkts(self._netdev_path, self._net_iface)
        record = TelemetryRecord(
            cycle=record.cycle, t_mono=record.t_mono, t_epoch=record.t_epoch,
            hwmon_temps=record.hwmon_temps, loadavg=record.loadavg,
            stat_idle=record.stat_idle, stat_total=record.stat_total,
            mem_available_kb=record.mem_available_kb, net_rx_pkts=rx, net_tx_pkts=tx,
        )
        self._prev_stat = (idle, total)
        return record

    def derive_busy_rate(self, record: TelemetryRecord, prev: TelemetryRecord | None) -> float | None:
        """冻结派生式（ADR-G-0025 §7 R7）：1 − Δ(idle+iowait)/Δ(total)，round dp。"""
        if prev is None:
            return None
        d_total = record.stat_total - prev.stat_total
        if d_total <= 0:
            return None
        d_idle = record.stat_idle - prev.stat_idle
        return round(1.0 - d_idle / d_total, self._profile.energy_round_dp)

    def build_delivery(
        self, record: TelemetryRecord, prev: TelemetryRecord | None,
    ) -> BridgeDelivery:
        """原始读数 → (合同三键 payload 包, 证据侧 log 行)。busy 派生独立可复算。"""
        busy = self.derive_busy_rate(record, prev)
        energy = round(1.0 - busy, self._profile.energy_round_dp) if busy is not None else 1.0
        payload: dict[str, object] = {
            "kind": "interoceptive_state", "energy": energy, "integrity": 1.0, "events": [],
        }
        payload_text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = content_digest(payload_text)
        packet = CognitivePacket(
            event_id=f"evt.physio.intero.{record.cycle}",
            subject_candidate_id="S", run_id="R", branch_id="B",
            activity_window_id="physio", cycle_id=record.cycle,
            virtual_time=record.cycle + self._profile.delay_cycles,
            source_module="env.physio.bridge", content_type=CARRIER_INTERO_CONTENT_TYPE,
            representation_level=RepresentationLevel.RECEIVED, schema_version="v1",
            payload_ref=ArtifactRef(digest=digest, kind="payload"),
            confidence=1.0, provenance=Provenance(), causal_parent_ids=(),
            access_scope=AccessScope.MODULE_LOCAL,
            content_digest=digest,
        )
        evidence_raw = record.raw_view()
        evidence_raw["payload_digest"] = digest
        return BridgeDelivery(
            packet=packet, payload_text=payload_text,
            evidence_raw=evidence_raw, evidence_payload_digest=digest, busy_rate=busy,
        )


def _default_monotonic() -> float:
    import time
    return time.monotonic()


def _default_epoch() -> float:
    import time
    return time.time()
