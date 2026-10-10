"""设备登记与 BodyGraph（ADR-G-0025 §4 范围声明：L4+ 执行面随设备新增事件交付）。

设备新增/更换/隔离/重新纳入各自独立授权（L10 §4.6）：
- add = 须 deployment_authorization + functional_ability（目标设备）双 fresh；
- isolate = enabled_interface 撤销事件驱动（登记只记录拓扑事实）；
- digest = 全设备集内容寻址（BodyGraph digest——L4+ 执行面的锚，设备集变即变）。
被动期 v1：主机平台虚拟设备（host_telemetry）登记在案，无执行器。
"""
from __future__ import annotations

from dataclasses import dataclass

from galatea.evidence.physio.authz import AuthorizationLedger
from galatea.kernel.digest import content_digest


class DeviceRegistryViolation(RuntimeError):
    """设备登记合同违反（授权缺失/未知设备）。"""


@dataclass(frozen=True, slots=True)
class DeviceEntry:
    device_id: str
    kind: str                       # telemetry_host | tessera_node | actuator | ...
    capabilities: tuple[str, ...]   # 该设备允许的动作类（functional_ability 承载）
    added_at_cycle: int
    io_surface: str                 # sensor/actuator/both
    source_ref: str                 # 授权信封 authz_id（链回台账）


class DeviceRegistry:
    """设备拓扑登记（BodyGraph 承载物；digest 随设备集变动）。"""

    def __init__(self, ledger: AuthorizationLedger, *,
                 deployment_authz_id: str, functional_authz_prefix: str = "fa-") -> None:
        self._ledger = ledger
        self._deployment_authz_id = deployment_authz_id
        self._functional_prefix = functional_authz_prefix
        self._devices: dict[str, DeviceEntry] = {}

    def add(self, device_id: str, kind: str, capabilities: tuple[str, ...],
            cycle: int, io_surface: str) -> DeviceEntry:
        """设备新增事件：deployment + functional 双授权 fresh 才可入（fail closed）。"""
        for authz_id, expect in ((self._deployment_authz_id, "deployment_authorization"),
                                 (f"{self._functional_prefix}{device_id}", "functional_ability")):
            query = self._ledger.freshness(authz_id, cycle)
            if query.verdict != "VALID":
                raise DeviceRegistryViolation(
                    f"device add rejected ({device_id}): {expect} authz {authz_id} = {query.verdict}"
                )
        if device_id in self._devices:
            raise DeviceRegistryViolation(f"device already registered: {device_id}")
        entry = DeviceEntry(device_id=device_id, kind=kind, capabilities=capabilities,
                            added_at_cycle=cycle, io_surface=io_surface,
                            source_ref=f"{self._functional_prefix}{device_id}")
        self._devices[device_id] = entry
        return entry

    def body_graph_digest(self) -> str:
        """BodyGraph digest = 全设备集规范序列化内容寻址（设备集变即变——L4+ 锚）。"""
        canonical = "|".join(
            f"{e.device_id}:{e.kind}:{','.join(e.capabilities)}:{e.added_at_cycle}:{e.io_surface}"
            for e in (self._devices[k] for k in sorted(self._devices))
        )
        return content_digest(canonical)

    def devices(self) -> tuple[DeviceEntry, ...]:
        """只读视图（按 device_id 排序——确定性）。"""
        return tuple(self._devices[k] for k in sorted(self._devices))

    def actuator_count(self) -> int:
        """执行器面计数（L4+ 前置盘点——被动期应为 0）。"""
        return sum(1 for d in self._devices.values() if d.io_surface in ("actuator", "both"))
