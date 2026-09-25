"""干预注册表（L01 §2.2/§4.3/§10 interventions/registry.py）。

纪律：**先注册后生效**（from_cycle > registered_at_cycle，L01 §8 不变量 4）；
注册记录不可变；每类干预必有 expected_signature（由 m0_interventions.yaml 冻结，
本模块按类实现其世界侧执行：no_op/sham/coercion 在 dynamics.apply 生效；
blocked 在 gateway（L10）、fault 在通道行为层执行——注册与 signature 定义在本域）。
"""
from dataclasses import dataclass

from galatea.kernel.digest import content_digest

INTERVENTION_KINDS = ("no_op", "sham", "blocked", "fault", "coercion")


class InterventionViolation(ValueError):
    """干预注册违规（未知类别/追溯生效）。"""


@dataclass(frozen=True, slots=True)
class InterventionRecord:
    """干预台账条目（L01 §2.1 intervention.log）。"""

    record_id: str
    kind: str
    target_primitive: str | None
    params: tuple[tuple[str, str], ...]
    registered_at_cycle: int
    from_cycle: int
    to_cycle: int
    registered_by: str
    protocol_ref: str

    def digest(self) -> str:
        return content_digest(
            {
                "record_id": self.record_id,
                "kind": self.kind,
                "target": self.target_primitive,
                "params": dict(self.params),
                "window": [self.from_cycle, self.to_cycle],
            }
        )


class InterventionRegistry:
    """注册表（append-only；active_at 查询确定性排序）。"""

    def __init__(self) -> None:
        self._records: list[InterventionRecord] = []

    def register(
        self,
        *,
        record_id: str,
        kind: str,
        registered_at_cycle: int,
        from_cycle: int,
        to_cycle: int,
        target_primitive: str | None = None,
        params: dict[str, str] | None = None,
        registered_by: str = "experiment_control",
        protocol_ref: str = "m0_interventions@v1",
    ) -> InterventionRecord:
        if kind not in INTERVENTION_KINDS:
            raise InterventionViolation(f"unknown intervention kind: {kind!r}")
        if from_cycle <= registered_at_cycle:
            raise InterventionViolation("intervention must take effect after registration（先注册后生效，L01 §8）")
        if to_cycle < from_cycle:
            raise InterventionViolation("empty intervention window")
        record = InterventionRecord(
            record_id=record_id,
            kind=kind,
            target_primitive=target_primitive,
            params=tuple(sorted((params or {}).items())),
            registered_at_cycle=registered_at_cycle,
            from_cycle=from_cycle,
            to_cycle=to_cycle,
            registered_by=registered_by,
            protocol_ref=protocol_ref,
        )
        self._records.append(record)
        return record

    def active_at(self, cycle: int, primitive: str | None = None) -> tuple[InterventionRecord, ...]:
        """窗口内生效的干预（kind 序确定性排序，供 apply 逐类消费）。"""
        matched = [
            r
            for r in self._records
            if r.from_cycle <= cycle <= r.to_cycle and (r.target_primitive is None or r.target_primitive == primitive)
        ]
        return tuple(sorted(matched, key=lambda r: (r.kind, r.record_id)))

    def records(self) -> tuple[InterventionRecord, ...]:
        return tuple(self._records)

    def __len__(self) -> int:
        return len(self._records)
