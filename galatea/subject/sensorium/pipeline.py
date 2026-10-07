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
from galatea.subject.sensorium.form_language import form_language
from galatea.subject.sensorium.form_proprio import form_proprio
from galatea.subject.sensorium.gain import C0_GAIN, apply_gain, apply_gain_c2, scale_frame_features
from galatea.subject.sensorium.ingest import (
    CARRIER_EXTERO,
    CARRIER_INTERO,
    CARRIER_LANGUAGE,
    CARRIER_PROPRIO,
    IngestedSignal,
    SchemaViolation,
    ingest,
)
from galatea.subject.sensorium.unknowns import calibration_uncertain
from galatea.subject.sensorium.ports import C0SensoriumProfile, GainState, SensoryFrame
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
        time_basis: dict[str, int], *, language_enabled: bool = False,
    ) -> None:
        """time_basis = 冻结通道延迟表（REV-0012 R2：世界时恢复的唯一来源；
        装配层从冻结 m0_mw0 profile 的 channel_delay_cycles 提取传入，禁运行时发明）。

        language_enabled = C4 LANGUAGE 模态机会型形成分支（c4_action_social.profile
        sensorium_c4.modality_set_extension；默认 False——C0–C3 装配行为 bit-exact 不变：
        语言通道为事件驱动稀疏面，缺席 = 正常静默，**不产** MISSING_SIGNAL unknown）。
        """
        missing = [c for c in (CARRIER_EXTERO, CARRIER_INTERO, CARRIER_PROPRIO) if c not in time_basis]
        if missing:
            raise ValueError(f"time_basis missing frozen delays for: {missing}")
        self._time_basis = dict(time_basis)
        self._profile = profile
        self._calibration = calibration
        self._language_enabled = language_enabled
        self._window = AlignmentWindow(profile)
        self._prev_energy: float | None = None
        self._published_count: dict[tuple[int, str], int] = {}   # (effective_time, modality) → 已发布帧数
        self._closed: set[int] = set()                            # 已原子关闭的 effective_time
        # C2 增益调制面（Q-L02-02：apply_gain_c2 接收——None = 无调制恒等路径，
        # C0/C1 行为不变；override 在位时连续强度特征缩放 + MODULATION 来源回执）
        self._gain_override: float | None = None

    def apply_gain_modulation(self, requested: float) -> GainReceipt:
        """C2 增益调制接收面（clip [0.5,2.0] + CLIPPED；applied 生效于后续形成窗，
        回执由调用方交 affect 台账——无回执调制 = 未发生，L05 §4.4）。"""
        _state, receipt = apply_gain_c2("sensorium.pipeline", requested)
        self._gain_override = receipt.applied_gain
        return receipt

    def clear_gain_modulation(self) -> None:
        """TTL 到期归零（L05 §4.4：禁常驻调制）。"""
        self._gain_override = None

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
                    formed = self._form_for_carrier(signal, delivery_cycle, is_revision=t in self._closed)
                    if self._gain_override is not None and self._gain_override != 1.0:
                        formed = [scale_frame_features(f, self._gain_override) for f in formed]
                    group_frames.extend(formed)
                if self._language_enabled:
                    # C4 机会型语言形成（L12 §4.3）：有 typed 陈述则成帧，缺席 = 正常静默；
                    # 语言为分类面，增益缩放豁免（Q-L12-06① 零后验权重承载面）
                    lang_signal = signals.get(CARRIER_LANGUAGE)
                    if lang_signal is not None:
                        group_frames.append(form_language(
                            lang_signal, delivery_cycle, self._calibration.version_id,
                            GainState(applied_factor=1.0, source="PROFILE"),
                        ))
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
        if self._gain_override is None:
            _state, gain_receipt = apply_gain(frame.frame_id, None)
        else:
            _state, gain_receipt = apply_gain_c2(frame.frame_id, self._gain_override)
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
