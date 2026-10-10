"""跨模态时间对齐（L02 §4.3/§10 alignment.py；Q-L02-03：W_align=4、迟到回溯 1 窗）。

纪律：窗内各模态帧按 effective_time 归槽；窗关闭原子发布对齐组；未到模态**不等待、
不补零**（部分对齐 + typed Unknown）；迟到信号以 revision 新帧引用旧帧（envelope
不可变），超回溯深度记 Unknown 不产历史帧。
"""
import json

from dataclasses import dataclass


from galatea.kernel.digest import content_digest
from galatea.kernel.unknown import Unknown
from galatea.subject.sensorium.ingest import IngestedSignal, ingest
from galatea.subject.sensorium.ports import C0SensoriumProfile, SensoryFrame
from galatea.subject.sensorium.unknowns import insufficient_observation, missing_signal


@dataclass(frozen=True, slots=True)
class AlignmentGroup:
    """对齐组（窗关闭时原子发布）：组内帧 + 缺席模态的 typed unknown + 对齐误差。"""

    effective_time: int
    frames: tuple[SensoryFrame, ...]
    unknowns: tuple[Unknown, ...]
    alignment_error: int                      # 组内各帧 delivery−effective 极差（指标面）
    group_id: str

    @property
    def frame_ids(self) -> tuple[str, ...]:
        return tuple(f.frame_id for f in self.frames)


class AlignmentWindow:
    """对齐窗（W_align 槽位 + 迟到回溯；状态随 checkpoint 序列化——C0 内存面，L02 §5）。"""

    def __init__(self, profile: C0SensoriumProfile) -> None:
        self._w = profile.w_align_cycles
        self._lookback = profile.late_revision_lookback_windows * profile.w_align_cycles
        self._pending: dict[int, dict[str, IngestedSignal]] = {}   # effective_time → carrier → signal

    def submit(self, signal: IngestedSignal, delivery_cycle: int) -> None:
        """信号入槽；已过期且超回溯深度的迟到信号在此拒绝（记 Unknown 由调用方发布）。"""
        t = signal.effective_time
        if t + self._w <= delivery_cycle:
            # 迟到：窗已关闭。回溯深度内允许 revision（形成面产 revision 帧）；超出 → 拒绝
            if delivery_cycle - (t + self._w) >= self._lookback:
                raise LateBeyondLookback(t, delivery_cycle)
        self._pending.setdefault(t, {})[signal.carrier] = signal

    def due_times(self, delivery_cycle: int) -> list[int]:
        """窗已关闭（t + W ≤ delivery）待发布的 effective_time（升序确定性）。"""
        return sorted(t for t in self._pending if t + self._w <= delivery_cycle)

    def signals_at(self, t: int) -> dict[str, IngestedSignal]:
        """槽内信号（carrier → signal；close 前由 pipeline 消费）。"""
        return dict(self._pending.get(t, {}))

    def close(self, t: int) -> None:
        """窗关闭（pipeline 已消费信号并产出 AlignmentGroup 后调用）。"""
        self._pending.pop(t, None)

    def snapshot(self) -> list[list[int | str]]:
        """窗内 pending 槽序列化（L02 §5 checkpoint 面兑现）：
        sorted [effective_time, carrier, event_id, cycle_id, delivery_basis, payload_text]——
        重摄取元组（restore 经 ingest 重校验，禁绕过合同）。"""
        entries: list[list[int | str]] = []
        for t in sorted(self._pending):
            for carrier in sorted(self._pending[t]):
                sig = self._pending[t][carrier]
                entries.append([t, carrier, sig.packet.event_id, sig.packet.cycle_id,
                                sig.delivery_basis,
                                json.dumps(sig.payload, sort_keys=True,
                                           separators=(",", ":"))])
        return entries

    def restore(self, entries: list[list[int | str]], profile: C0SensoriumProfile,
                time_basis: dict[str, int]) -> None:
        """恢复 pending 槽（逐条重摄取——合同重校验，损坏即抛禁半截谱系）。"""
        for entry in entries:
            t = int(entry[0])
            carrier = str(entry[1])
            event_id = str(entry[2])
            cycle_id = int(entry[3])
            payload_text = str(entry[5])
            from galatea.kernel.packet import (  # noqa: PLC0415——restore 局部面
                AccessScope,
                ArtifactRef,
                CognitivePacket,
                Provenance,
                RepresentationLevel,
            )
            digest = content_digest(payload_text)
            pkt = CognitivePacket(
                event_id=event_id, subject_candidate_id="S", run_id="R", branch_id="B",
                activity_window_id="restore", cycle_id=cycle_id, virtual_time=cycle_id,
                source_module="restore", content_type=carrier,
                representation_level=RepresentationLevel.RECEIVED, schema_version="v1",
                payload_ref=ArtifactRef(digest=digest, kind="payload"), confidence=1.0,
                provenance=Provenance(), causal_parent_ids=(),
                access_scope=AccessScope.MODULE_LOCAL, content_digest=digest,
            )
            sig: IngestedSignal = ingest(pkt, payload_text, profile, time_basis)
            self.submit(sig, delivery_cycle=t + self._w)   # 窗未关闭的槽内信号合法重投

    @staticmethod
    def late_unknown(t: int, delivery_cycle: int, lookback: int) -> list[Unknown]:
        """超回溯深度迟到的 typed unknown（不产历史帧）。"""
        return [
            insufficient_observation(
                (f"effective_time={t}",),
                f"late signal beyond lookback: effective {t}, delivery {delivery_cycle}"
                f"（Q-L02-03：回溯 {lookback} cycles，禁历史帧改写）",
                delivery_cycle,
            )
        ]


class LateBeyondLookback(RuntimeError):
    """内部信号：超回溯深度迟到（AlignmentWindow.submit 抛出，pipeline 转 Unknown）。"""

    def __init__(self, effective_time: int, delivery_cycle: int) -> None:
        super().__init__(f"late beyond lookback: effective {effective_time} at delivery {delivery_cycle}")
        self.effective_time = effective_time
        self.delivery_cycle = delivery_cycle


def missing_carrier_unknown(carrier: str, t: int, delivery_cycle: int) -> Unknown:
    """窗内载体缺席（延迟/丢失）→ MISSING_SIGNAL（部分对齐发布，禁补零）。"""
    return missing_signal(
        (f"carrier={carrier}", f"effective_time={t}"),
        f"carrier {carrier} absent for effective_time {t} at delivery {delivery_cycle}（部分对齐）",
        delivery_cycle,
    )

