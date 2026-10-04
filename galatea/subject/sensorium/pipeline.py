"""Sensorium 流水线门面（L02 §4.2 形成流水线的装配面 / §10 补录件，C0 实现期）。

process_cycle（T1 挂点）：ingest → 对齐窗入槽 → 到期窗关闭 → 形成三面
（ext_local_obs / ext_event+intero / proprio）→ 校准绑定 → 增益（恒等）→
帧 + FormationReceipt + GainReceipt 发布；缺席载体 = MISSING_SIGNAL（部分对齐，
禁补零）；迟到 revision 按冻结回溯深度（Q-L02-03）。

确定性：字典遍历全部 sorted；无 RNG、无墙钟（Q-G00-12④）；audit = 无帧无回执、
无回执无帧、增益回执绑定逐帧核验（消融面，test_ablation_gain_receipt）。
"""
from dataclasses import dataclass

from galatea.kernel.packet import CognitivePacket
from galatea.kernel.unknown import Unknown
from galatea.subject.sensorium.alignment import (
    AlignmentGroup,
    AlignmentWindow,
    LateBeyondLookback,
    missing_carrier_unknown,
)
from galatea.subject.sensorium.calibration import CalibrationVersion
from galatea.subject.sensorium.form_extero import form_ext_event, form_ext_local_obs
from galatea.subject.sensorium.form_intero import form_intero
from galatea.subject.sensorium.form_proprio import form_proprio
from galatea.subject.sensorium.gain import C0_GAIN, apply_gain
from galatea.subject.sensorium.ingest import (
    CARRIER_EXTERO,
    CARRIER_INTERO,
    CARRIER_PROPRIO,
    IngestedSignal,
    SchemaViolation,
    ingest,
)
from galatea.subject.sensorium.unknowns import calibration_uncertain
from galatea.subject.sensorium.ports import C0SensoriumProfile, SensoryFrame
from galatea.subject.sensorium.receipt import FormationReceipt, GainReceipt, build_receipt

_EXPECTED_CARRIERS: tuple[str, ...] = (CARRIER_EXTERO, CARRIER_INTERO, CARRIER_PROPRIO)


@dataclass(frozen=True, slots=True)
class CycleOutput:
    """单 cycle 形成产物（帧/回执/增益回执/unknowns/对齐组——全部证据侧可审计）。"""

    frames: tuple[SensoryFrame, ...]
    formation_receipts: tuple[FormationReceipt, ...]
    gain_receipts: tuple[GainReceipt, ...]
    unknowns: tuple[Unknown, ...]
    groups: tuple[AlignmentGroup, ...]


class SensoriumPipeline:
    """形成流水线（T1；形成义务无条件——包缺失产 Unknown，不跳过形成）。"""

    def __init__(
        self, profile: C0SensoriumProfile, calibration: CalibrationVersion,
        time_basis: dict[str, int],
    ) -> None:
        """time_basis = 冻结通道延迟表（REV-0012 R2：世界时恢复的唯一来源；
        装配层从冻结 m0_mw0 profile 的 channel_delay_cycles 提取传入，禁运行时发明）。"""
        missing = [c for c in (CARRIER_EXTERO, CARRIER_INTERO, CARRIER_PROPRIO) if c not in time_basis]
        if missing:
            raise ValueError(f"time_basis missing frozen delays for: {missing}")
        self._time_basis = dict(time_basis)
        self._profile = profile
        self._calibration = calibration
        self._window = AlignmentWindow(profile)
        self._prev_energy: float | None = None
        self._published_count: dict[tuple[int, str], int] = {}   # (effective_time, modality) → 已发布帧数
        self._closed: set[int] = set()                            # 已原子关闭的 effective_time

    def process_cycle(
        self, delivery_cycle: int, packets: list[tuple[CognitivePacket, str]]
    ) -> CycleOutput:
        frames: list[SensoryFrame] = []
        formation_receipts: list[FormationReceipt] = []
        gain_receipts: list[GainReceipt] = []
        unknowns: list[Unknown] = []

        for packet, payload_text in sorted(packets, key=lambda p: p[0].event_id):
            try:
                signal = ingest(packet, payload_text, self._profile, self._time_basis)
                self._window.submit(signal, delivery_cycle)
            except SchemaViolation as broken:
                # L02 §6 行 3（REV-0012 R3）：损坏/异构包 → typed unknown + 留痕，
                # 禁整 cycle 崩止、禁静默丢弃、禁补零
                unknowns.append(calibration_uncertain(
                    (packet.event_id,),
                    f"packet {packet.event_id} not formable: {broken}（通道损坏面，corruption 留痕）",
                    delivery_cycle,
                ))
                continue
            except LateBeyondLookback as late:
                unknowns.extend(
                    AlignmentWindow.late_unknown(
                        late.effective_time, late.delivery_cycle,
                        self._profile.late_revision_lookback_windows * self._profile.w_align_cycles,
                    )
                )

        for t in self._window.due_times(delivery_cycle):
            signals = self._window.signals_at(t)
            group_frames: list[SensoryFrame] = []
            for carrier in _EXPECTED_CARRIERS:
                signal = signals.get(carrier)
                if signal is None:
                    unknowns.append(missing_carrier_unknown(carrier, t, delivery_cycle))
                    continue
                group_frames.extend(self._form_for_carrier(signal, delivery_cycle, is_revision=t in self._closed))
            for frame in group_frames:
                receipt, gain_receipt = self._receipt_for(frame)
                frames.append(frame)
                formation_receipts.append(receipt)
                gain_receipts.append(gain_receipt)
            self._closed.add(t)
            self._window.close(t)

        return CycleOutput(
            frames=tuple(frames),
            formation_receipts=tuple(formation_receipts),
            gain_receipts=tuple(gain_receipts),
            unknowns=tuple(unknowns),
            groups=self._published_groups(frames, unknowns),
        )

    def _form_for_carrier(
        self, signal: IngestedSignal, delivery_cycle: int, is_revision: bool
    ) -> list[SensoryFrame]:
        """单载体形成（t 已关闭过 → 本轮全部帧为 revision 帧，引用原帧）。"""
        version = self._calibration.version_id
        formed: list[SensoryFrame] = []
        if signal.carrier == CARRIER_EXTERO:
            formed.append(form_ext_local_obs(
                signal, delivery_cycle, version, C0_GAIN,
                revision_of=self._last_frame_id(signal.effective_time, "EXT_LOCAL_OBS") if is_revision else None,
                revision_index=self._published_count.get((signal.effective_time, "EXT_LOCAL_OBS"), 0)
                if is_revision else 0,
            ))
        elif signal.carrier == CARRIER_INTERO:
            intero_frame, _unknowns, energy = form_intero(
                signal, delivery_cycle, version, C0_GAIN,
                prev_energy_level=None if is_revision else self._prev_energy,
            )
            formed.append(intero_frame)
            event_frame = form_ext_event(signal, delivery_cycle, version, C0_GAIN)
            if event_frame is not None:
                formed.append(event_frame)
            self._prev_energy = energy
        elif signal.carrier == CARRIER_PROPRIO:
            formed.append(form_proprio(signal, delivery_cycle, version, C0_GAIN))
        for frame in formed:
            key = (frame.effective_time, frame.modality.value)
            self._published_count[key] = self._published_count.get(key, 0) + 1
        return formed

    def _receipt_for(self, frame: SensoryFrame) -> tuple[FormationReceipt, GainReceipt]:
        _state, gain_receipt = apply_gain(frame.frame_id, None)
        return build_receipt(frame, gain_receipt), gain_receipt

    def _last_frame_id(self, t: int, modality: str) -> str | None:
        count = self._published_count.get((t, modality), 0)
        if count == 0:
            return None
        base = f"sf.{modality}.{t}"
        return base if count == 1 else f"{base}.r{count - 1}"

    def _published_groups(
        self, frames: list[SensoryFrame], unknowns: list[Unknown]
    ) -> tuple[AlignmentGroup, ...]:
        by_time: dict[int, list[SensoryFrame]] = {}
        for frame in frames:
            by_time.setdefault(frame.effective_time, []).append(frame)
        return tuple(
            AlignmentGroup(
                effective_time=t,
                frames=tuple(by_time[t]),
                unknowns=tuple(
                    u for u in unknowns
                    if any(f"effective_time={t}" in ref for ref in u.evidence_refs)
                ),
                alignment_error=max(
                    (frame.alignment_offset for frame in by_time[t]), default=0
                ) - min((frame.alignment_offset for frame in by_time[t]), default=0),
                group_id=f"ag.{t}",
            )
            for t in sorted(by_time)
        )


def audit(
    frames: tuple[SensoryFrame, ...], formation_receipts: tuple[FormationReceipt, ...],
    gain_receipts: tuple[GainReceipt, ...],
) -> None:
    """证据侧审计（L02 §7 ablation①）：无帧无回执、无回执无帧、增益回执逐帧绑定。

    移除增益回执（消融注入）→ 此处检出——C2 因果调制证据缺失的可检面。
    """
    frame_ids = {f.frame_id for f in frames}
    receipt_ids = {r.frame_id for r in formation_receipts}
    if frame_ids != receipt_ids:
        raise AssertionError(
            f"formation receipt audit failed: frames−receipts={sorted(frame_ids - receipt_ids)} "
            f"receipts−frames={sorted(receipt_ids - frame_ids)}"
        )
    gain_ids = {g.frame_id for g in gain_receipts}
    if gain_ids != frame_ids:
        raise AssertionError(
            f"gain receipt audit failed: frames−gain={sorted(frame_ids - gain_ids)} "
            f"gain−frames={sorted(gain_ids - frame_ids)}（消融检出面：移除增益回执必须可检）"
        )
    by_id = {f.frame_id: f for f in frames}
    for receipt in formation_receipts:
        frame = by_id[receipt.frame_id]
        if receipt.frame_digest != frame.content_digest:
            raise AssertionError(f"receipt digest mismatch for {receipt.frame_id}（帧被改写检出）")
