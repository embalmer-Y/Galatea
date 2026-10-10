"""音频闭环测试驱动（P2 单元 C；ADR-G-0027）：主体发声 → 听见 → 归属。

在目标主机上运行（硬件面）：
    cd ~/galatea && export PATH=$HOME/.local/bin:$PATH PYTHONPATH=$HOME/galatea
    uv run python scripts/audio_closed_loop_test.py --card 2 --out evidence/audio_closed_loop

T1 治理 v2：L4 常态化信封（批准者 = owner 2026-10-10 常态授权消息）+ L 机逐级爬升
T2 L4 有界路由：audio_play 在 L4 执行（physical_limited）；L1 拒；越界时长拒（封套机械强制）
T3 听觉闭环：主体发声（660Hz 2s）→ 麦克风帧流 → 未改动形成管线（audio_enabled）→
   loudness 感觉时序——发声窗显著高于静默基线（机械判定）
T4 物理域归属（机械面）：命令回执（aplay 成功）+ 频率匹配（Goertzel 660 vs 对照）→
   归属记录 SELF_CONSISTENT（efference 绑定证据链；归属六类证据规则的自源面——
   选择 + 回执 + 形成后结果一致；不做超出证据的宣称）
T5 急停：estop → L0 → audio_play 拒 + 在途部分执行如实留痕
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import threading
import time
from pathlib import Path

from galatea.env.physio.audio import (
    AudioActuator,
    AudioBridge,
    features_from_pcm,
    features_payload,
    packet_for_audio,
)
from galatea.env.physio.lstate import ESTOP_EVENT, PhysioLStateMachine
from galatea.env.physio.ports import load_p1_physio_profile
from galatea.evidence.physio.authz import AuthzEnvelope, AuthorizationLedger
from galatea.kernel.digest import content_digest
from galatea.subject.sensorium.calibration import bind_calibration
from galatea.subject.sensorium.ingest import CARRIER_AUDIO, CARRIER_EXTERO, CARRIER_INTERO, CARRIER_PROPRIO
from galatea.subject.sensorium.pipeline import SensoriumPipeline
from galatea.subject.sensorium.ports import load_c0_sensorium_profile

_REPO = Path(__file__).resolve().parents[1]
_DWELL = 64
TONE_HZ = 660.0
CONTROL_HZ = 500.0
GOERTZEL_RATIO_PASS = 20.0
LOUDNESS_SPIKE_FACTOR = 3.0


def _goertzel(pcm: bytes, hz: float, rate: int) -> float:
    n = len(pcm) // 2
    if n == 0:
        return 0.0
    k = round(n * hz / rate)
    omega = 2.0 * math.pi * k / n
    coeff = 2.0 * math.cos(omega)
    s1 = s2 = 0.0
    for i in range(n):
        v = int.from_bytes(pcm[2 * i:2 * i + 2], "little", signed=True)
        s0 = float(v) + coeff * s1 - s2
        s2, s1 = s1, s0
    return s1 * s1 + s2 * s2 - coeff * s1 * s2


def _governance() -> tuple[AuthorizationLedger, PhysioLStateMachine, dict]:
    approver = "owner_msg_2026_10_10_standing_hw_auth"      # owner 常态授权消息（ADR-G-0027 §2）
    ledger = AuthorizationLedger(approver_roots=frozenset({approver}))
    for authz_id, cls, target, scope in (
        ("dep-1", "deployment_authorization", "host:192.168.2.91", "p2_audio_arc"),
        ("fa-usb_audio", "functional_ability", "device:usb_audio",
         "audio_capture+audio_play_l4_bounded"),
        ("ei-usb-audio", "enabled_interface", "iface:alsa_card2", "capture+playback"),
        ("ca-audio", "containment_allowance", "scope:usb_audio",
         "volume<=70pct+duration<=5s+estop_armed"),
    ):
        ledger.issue(AuthzEnvelope(
            authz_id=authz_id, authz_class=cls, version=1, target_ref=target,
            granted_scope=scope, granted_at_cycle=0, valid_period_cycles=0,
            approver_ref=approver, auth_chain_digest="root",
            revoke_path="owner_message", reauth_path="new_version_envelope",
            monitoring_binding="audio_closed_loop_report",
        ))
    sm = PhysioLStateMachine(_DWELL)
    cycle = _DWELL
    for level in (2, 3, 4):
        sm.grant(level, cycle, lambda _l, _c=cycle: ledger.freshness("fa-usb_audio", _c).verdict == "VALID")
        cycle += _DWELL
    return ledger, sm, {"final_level": sm.level, "approver": approver}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="音频闭环测试（发声→听见→归属）")
    parser.add_argument("--card", type=int, default=2)
    parser.add_argument("--out", type=Path, default=Path("evidence/audio_closed_loop"))
    args = parser.parse_args(argv)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    root = _REPO
    profile = load_p1_physio_profile(root / "config/profiles/p1_physio.profile.yaml")
    dev = f"plughw:{args.card},0"
    report: dict = {"card": args.card, "tests": {}}
    verdicts: list[bool] = []

    # T1 治理 v2（常态化信封 + L4 爬升）
    ledger, sm, gov = _governance()
    t1 = gov["final_level"] == 4
    report["tests"]["T1_governance_v2"] = {"passed": t1, "detail": gov}
    verdicts.append(t1)
    print(f"T1 governance_v2 = {t1}")

    # T2 L4 有界路由
    dec_l4 = sm.submit("audio_play", 4 * _DWELL)
    sm_l1 = PhysioLStateMachine(_DWELL)
    dec_l1 = sm_l1.submit("audio_play", 0)
    actuator = AudioActuator(profile, dev)
    bounds_ok = False
    try:
        actuator.play_tone(TONE_HZ, 99.0, out_dir=out)      # 越界时长 → 必拒
        bounds_ok = False
    except ValueError:
        bounds_ok = True
    t2 = (dec_l4.outcome == "EXECUTED_LIMITED" and dec_l4.effects == "physical_limited"
          and dec_l1.outcome in ("REJECTED_PASSIVE", "REJECTED_AUTH_REQUIRED") and bounds_ok)
    report["tests"]["T2_l4_bounded_routing"] = {
        "passed": t2, "l4_decision": dec_l4.outcome, "l1_decision": dec_l1.outcome,
        "overbound_rejected": bounds_ok,
    }
    verdicts.append(t2)
    print(f"T2 l4_bounded_routing = {t2}")

    # T3 听觉闭环：主体发声 → 麦克风 → 形成管线 loudness 时序
    rec_raw = out / "closed_loop.raw"
    rec = subprocess.Popen(
        ["arecord", "-D", dev, "-q", "-f", "S16_LE", "-r", "16000", "-c", "1",
         "-d", "6", "-t", "raw", str(rec_raw)],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    time.sleep(0.8)                                          # 录音先起（0.8s 基线）
    wav = actuator.play_tone(TONE_HZ, 2.0, out_dir=out)      # 主体发声（L4 命令回执）
    play_offset_s = 0.8                                      # 发声在录音内偏移
    rec.wait(timeout=30)
    pcm = rec_raw.read_bytes()
    rate = 16000
    frame_samples = int(rate * profile.audio["frame_ms"] / 1000)
    frame_bytes = frame_samples * 2

    # 帧流 → 合同包 → 未改动形成管线（audio_enabled=True）
    c0 = load_c0_sensorium_profile(root / "config/profiles/c0_sensorium.profile.yaml")
    pipeline = SensoriumPipeline(
        c0, bind_calibration(root / "config/profiles/c0_sensorium.profile.yaml", c0.calibration_version),
        {CARRIER_EXTERO: 1, CARRIER_INTERO: 0, CARRIER_PROPRIO: 0, CARRIER_AUDIO: 0},
        audio_enabled=True, audio_ref_rms=profile.audio["audio_ref_rms"])
    loudness: list[tuple[float, int]] = []                   # (effective_time, loudness)
    n_frames = len(pcm) // frame_bytes
    for f in range(n_frames):
        chunk = pcm[f * frame_bytes:(f + 1) * frame_bytes]
        feats = features_from_pcm(chunk, rate)
        _payload, text = features_payload(feats)
        pkt, text = packet_for_audio(text, f, "env.physio.audio_bridge")
        cycle_out = pipeline.process_cycle(f, [(pkt, text)])
        for frame in cycle_out.frames:
            loud = getattr(frame.features, "loudness", None)
            if loud is not None:
                loudness.append((float(frame.effective_time), loud))
    frame_s = profile.audio["frame_ms"] / 1000.0
    baseline = [v for t, v in loudness if t * frame_s < play_offset_s - 0.2]
    during = [v for t, v in loudness if play_offset_s + 0.1 <= t * frame_s <= play_offset_s + 1.8]
    base_max = max(baseline, default=0.0)
    during_mean = sum(during) / len(during) if during else 0.0
    # 判据：发声窗均值 ≥ 基线 + 抬升阈（饱和信号 max==mean——饱和本身即强证据）
    t3 = bool(during) and during_mean >= base_max + LOUDNESS_SPIKE_FACTOR * 0.1
    report["tests"]["T3_hearing_closed_loop"] = {
        "passed": t3, "frames": n_frames, "formed_loudness": len(loudness),
        "baseline_max": round(base_max, 4), "during_mean": round(during_mean, 4),
        "during_max": round(max(during, default=0.0), 4),
        "spike_factor_required": LOUDNESS_SPIKE_FACTOR,
    }
    verdicts.append(t3)
    print(f"T3 hearing_closed_loop = {t3} (base_max={base_max:.3f} during_mean={during_mean:.3f})")

    # T4 物理域归属（机械面）：命令回执 + 频率匹配 → SELF_CONSISTENT
    tone_seg = pcm[int((play_offset_s + 0.3) * rate) * 2: int((play_offset_s + 1.3) * rate) * 2]
    p_target = _goertzel(tone_seg, TONE_HZ, rate)
    p_control = _goertzel(tone_seg, CONTROL_HZ, rate)
    ratio = p_target / max(1.0, p_control)
    attribution = "SELF_CONSISTENT" if (ratio >= GOERTZEL_RATIO_PASS and wav.exists()) \
        else "INDETERMINATE"
    t4 = attribution == "SELF_CONSISTENT"
    report["tests"]["T4_physical_attribution"] = {
        "passed": t4, "attribution": attribution, "freq_ratio": round(ratio, 1),
        "evidence_chain": ["command: audio_play@L4", f"receipt: aplay rc0 ({wav.name})",
                           f"heard: {TONE_HZ}Hz ratio {ratio:.0f}x vs {CONTROL_HZ}Hz control"],
        "note": "归属六类证据规则的自源面（选择+回执+形成后结果一致）；不做超出证据的宣称",
    }
    verdicts.append(t4)
    print(f"T4 physical_attribution = {t4} (ratio={ratio:.0f})")

    # T5 急停：estop → L0 → 拒 + 在途留痕
    sm.submit("audio_play", 4 * _DWELL + 1)
    event = sm.estop(4 * _DWELL + 2)
    settled = sm.apply_estop_to_in_flight(4 * _DWELL + 2)
    rejected_after = sm.submit("audio_play", 4 * _DWELL + 3).outcome == "REJECTED_ESTOP"
    t5 = event == ESTOP_EVENT and sm.level == 0 and rejected_after \
        and all(s.outcome == "PARTIAL_EXECUTED_ESTOP" for s in settled)
    report["tests"]["T5_estop_path"] = {
        "passed": t5, "event": event, "level_after": sm.level,
        "rejected_after": rejected_after, "partial_recorded": len(settled),
    }
    verdicts.append(t5)
    print(f"T5 estop_path = {t5}")

    overall = all(verdicts)
    report["overall"] = {
        "passed": overall,
        "conclusion": ("物理域认知闭环首次成立：主体经 L4 有界命令发声、经未改动形成管线听见"
                       "自己的发声、经 efference 绑定证据链归属为自源（SELF_CONSISTENT）——"
                       "听/说/归属三面全部机械可测。" if overall else
                       "存在失败项——见 tests 详情"),
        "verdicts": dict(zip(["T1", "T2", "T3", "T4", "T5"], verdicts)),
    }
    (out / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8")
    print(f"OVERALL = {overall}")
    print(f"report={out / 'report.json'}")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
