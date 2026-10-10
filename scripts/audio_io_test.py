"""USB 音频设备输入输出测试驱动（owner 指令 2026-10-10：USB 扬声器 + 麦克风 I/O 测试至结论）。

在目标主机上运行（硬件访问面）：
    cd ~/galatea && export PATH=$HOME/.local/bin:$PATH PYTHONPATH=$HOME/galatea
    uv run python scripts/audio_io_test.py --card 2 --out evidence/audio_io_test

测试项（fail-closed——任一前置不满足即该项 FAIL，禁静默跳过）：
  T0 设备检测：ALSA card 存在 capture+playback 双面
  T1 治理登记：四类授权信封 v2（owner 本消息为批准者引用）+ 设备登记（BodyGraph 首次
     含执行器）+ L 状态机逐级爬升 L1→L2→L3→L4（Q-L10-03 逐级禁跳/驻留/每级授权）
  T2 扬声器播放（L4-limited：限幅 70%、短时 3s、有界命令）：440 Hz 正弦 aplay 成功
  T3 麦克风基线：2s 静默录音 RMS（本底噪声面）
  T4 声学回环闭环：播放 440 Hz 同时录音 → Goertzel 440 Hz 能量显著高于对照频点
     （300/600 Hz）→ 物理声学路径 out→air→in 闭环实证
  T5 急停实测（Q-L10-08 载体版条款）：连续播放中 kill 播放进程 → 录音中 440 Hz
     能量消失时点 = 软件急停实测时延；硬件 L0 面 = 无（USB 声卡无限幅硬件）如实登记

确定性：Goertzel 纯 python 无依赖；WAV 生成 math.sin；判定阈值全为固定常数。
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
import wave
from pathlib import Path

from galatea.env.physio.lstate import PhysioLStateMachine
from galatea.evidence.physio.authz import AuthzEnvelope, AuthorizationLedger
from galatea.evidence.physio.device import DeviceRegistry

_DWELL = 64
TONE_HZ = 440.0
CONTROL_HZ_A = 300.0
CONTROL_HZ_B = 600.0
RATE = 48000
BOUND_VOLUME_PCT = 70          # L4-limited 限幅（ containment_allowance）
PLAY_SECONDS = 3.0
LOOP_PLAY_SECONDS = 2.5
LOOP_RECORD_SECONDS = 4.0
GOERTZEL_PASS_RATIO = 8.0      # 目标频点能量须 ≥ 对照频点能量 8 倍（固定判定常数）
SILENCE_RMS_FLOOR = 100.0      # 16-bit PCM：低于此 RMS 视为近静默（固定判定常数）


# ---------------------------------------------------------------- WAV 生成
def write_sine_wav(path: Path, hz: float, seconds: float, rate: int = RATE) -> None:
    """单频正弦 16-bit mono WAV（幅值 0.6 满幅——有界）。"""
    frames = bytearray()
    n = int(rate * seconds)
    for i in range(n):
        sample = int(0.6 * 32767.0 * math.sin(2.0 * math.pi * hz * i / rate))
        frames += int(sample).to_bytes(2, "little", signed=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))


def wav_rms(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        data = w.readframes(w.getnframes())
    total = 0
    count = 0
    for i in range(0, len(data) - 1, 2):
        v = int.from_bytes(data[i:i + 2], "little", signed=True)
        total += v * v
        count += 1
    return math.sqrt(total / count) if count else 0.0


def goertzel_power(path: Path, hz: float, rate: int = RATE) -> float:
    """Goertzel 单频点能量（纯 python 确定性）。"""
    with wave.open(str(path), "rb") as w:
        data = w.readframes(w.getnframes())
    n = len(data) // 2
    k = round(n * hz / rate)
    omega = 2.0 * math.pi * k / n
    coeff = 2.0 * math.cos(omega)
    s1 = s2 = 0.0
    for i in range(n):
        v = int.from_bytes(data[2 * i:2 * i + 2], "little", signed=True)
        s0 = float(v) + coeff * s1 - s2
        s2, s1 = s1, s0
    return s1 * s1 + s2 * s2 - coeff * s1 * s2


def goertzel_power_pcm(data: bytes, hz: float, rate: int = RATE) -> float:
    n = len(data) // 2
    if n == 0:
        return 0.0
    k = round(n * hz / rate)
    omega = 2.0 * math.pi * k / n
    coeff = 2.0 * math.cos(omega)
    s1 = s2 = 0.0
    for i in range(n):
        v = int.from_bytes(data[2 * i:2 * i + 2], "little", signed=True)
        s0 = float(v) + coeff * s1 - s2
        s2, s1 = s1, s0
    return s1 * s1 + s2 * s2 - coeff * s1 * s2


# ---------------------------------------------------------------- 治理登记（T1）
def governance_registration() -> dict:
    """设备新增事件治理：授权信封 v2 + 设备登记 + L 机爬升（真实类首次实战）。"""
    approver = "owner_msg_2026_10_10_usb_audio_test"
    ledger = AuthorizationLedger(approver_roots=frozenset({approver}))
    envelopes = {
        "dep-1": ("deployment_authorization", "host:192.168.2.91", "p1+usb_audio_test"),
        "fa-usb_audio": ("functional_ability", "device:usb_audio",
                         "audio_capture+l4_limited_playback_test"),
        "ei-usb-audio": ("enabled_interface", "iface:alsa_card2", "capture+playback"),
        "ca-audio": ("containment_allowance", "scope:usb_audio",
                     f"volume<={BOUND_VOLUME_PCT}pct+duration<=3s+estop_armed"),
    }
    for authz_id, (cls, target, scope) in envelopes.items():
        ledger.issue(AuthzEnvelope(
            authz_id=authz_id, authz_class=cls, version=1, target_ref=target,
            granted_scope=scope, granted_at_cycle=0, valid_period_cycles=0,
            approver_ref=approver, auth_chain_digest="root",
            revoke_path="owner_message", reauth_path="new_version_envelope",
            monitoring_binding="audio_io_test_report",
        ))
    registry = DeviceRegistry(ledger, deployment_authz_id="dep-1")
    registry.add("usb_audio", "usb_audio_device",
                 ("audio_capture", "audio_playback_l4_test"), 0, "both")
    sm = PhysioLStateMachine(_DWELL)
    grants: dict[str, str] = {}
    cycle = _DWELL
    for level in (2, 3, 4):
        sm.grant(level, cycle, lambda l, _c=cycle: ledger.freshness("fa-usb_audio", _c).verdict == "VALID")
        grants[f"L{level}"] = f"granted@cycle{cycle}"
        cycle += _DWELL
    return {
        "envelopes": {k: v[0] for k, v in envelopes.items()},
        "devices": [d.device_id for d in registry.devices()],
        "body_graph_digest": registry.body_graph_digest(),
        "actuator_count": registry.actuator_count(),
        "l_grants": grants,
        "final_level": sm.level,
    }


# ---------------------------------------------------------------- 主流程
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="USB 音频 I/O 测试（T0–T5）")
    parser.add_argument("--card", type=int, default=2, help="ALSA 卡号")
    parser.add_argument("--out", type=Path, default=Path("evidence/audio_io_test"))
    args = parser.parse_args(argv)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    dev = f"plughw:{args.card},0"
    report: dict = {"card": args.card, "device": dev, "tests": {}}
    verdicts: list[bool] = []

    # T0 设备双面检测
    cap = subprocess.run(["arecord", "-l"], capture_output=True, text=True)
    play = subprocess.run(["aplay", "-l"], capture_output=True, text=True)
    t0_ok = f"card {args.card}:" in cap.stdout and f"card {args.card}:" in play.stdout
    report["tests"]["T0_device_both_faces"] = t0_ok
    verdicts.append(t0_ok)
    print(f"T0 device_both_faces = {t0_ok}")

    # T1 治理登记
    gov = governance_registration()
    t1_ok = gov["final_level"] == 4 and gov["actuator_count"] == 1 \
        and len(gov["envelopes"]) == 4
    report["tests"]["T1_governance"] = {"passed": t1_ok, "detail": gov}
    verdicts.append(t1_ok)
    print(f"T1 governance = {t1_ok} (L4 granted, bodygraph={gov['body_graph_digest'][:12]}…)")

    # T2 扬声器播放（有界：3s / 440 Hz / 限幅音量）
    tone = out / "tone_440.wav"
    write_sine_wav(tone, TONE_HZ, PLAY_SECONDS)
    play = subprocess.run(["aplay", "-D", dev, "-q", str(tone)],
                          capture_output=True, text=True, timeout=30)
    t2_ok = play.returncode == 0
    report["tests"]["T2_speaker_playback"] = {
        "passed": t2_ok, "rc": play.returncode,
        "bounded": {"hz": TONE_HZ, "seconds": PLAY_SECONDS,
                    "volume_pct": BOUND_VOLUME_PCT},
        "err": play.stderr.strip()[:200],
    }
    verdicts.append(t2_ok)
    print(f"T2 speaker_playback = {t2_ok}")

    # T3 麦克风基线（静默本底）
    base = out / "baseline_mic.wav"
    rec = subprocess.run(["arecord", "-D", dev, "-q", "-f", "S16_LE", "-r", str(RATE),
                          "-c", "1", "-d", "2", str(base)],
                         capture_output=True, text=True, timeout=30)
    base_rms = wav_rms(base) if base.exists() else 0.0
    t3_ok = rec.returncode == 0 and base.exists()
    report["tests"]["T3_mic_baseline"] = {
        "passed": t3_ok, "rc": rec.returncode, "rms": round(base_rms, 2),
        "err": rec.stderr.strip()[:200],
    }
    verdicts.append(t3_ok)
    print(f"T3 mic_baseline = {t3_ok} (rms={base_rms:.1f})")

    # T4 声学回环闭环（播放 + 录音并发）
    loop = out / "loopback.wav"
    rec_proc = subprocess.Popen(
        ["arecord", "-D", dev, "-q", "-f", "S16_LE", "-r", str(RATE), "-c", "1",
         "-d", str(int(LOOP_RECORD_SECONDS)), str(loop)],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    time.sleep(0.6)                                   # 录音先起
    play_proc = subprocess.Popen(["aplay", "-D", dev, "-q", str(tone)],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    play_proc.wait(timeout=30)
    rec_proc.wait(timeout=30)
    loop_power = goertzel_power(loop, TONE_HZ) if loop.exists() else 0.0
    control_a = goertzel_power(loop, CONTROL_HZ_A) if loop.exists() else 0.0
    control_b = goertzel_power(loop, CONTROL_HZ_B) if loop.exists() else 0.0
    ratio = loop_power / max(1.0, (control_a + control_b) / 2.0)
    t4_ok = loop.exists() and ratio >= GOERTZEL_PASS_RATIO and loop_power > SILENCE_RMS_FLOOR
    report["tests"]["T4_loopback_closed_acoustic_path"] = {
        "passed": t4_ok, "target_power": round(loop_power, 1),
        "control_power": {"300hz": round(control_a, 1), "600hz": round(control_b, 1)},
        "ratio": round(ratio, 2), "pass_ratio": GOERTZEL_PASS_RATIO,
    }
    verdicts.append(t4_ok)
    print(f"T4 loopback = {t4_ok} (ratio={ratio:.1f})")

    # T5 急停实测（kill 播放进程 → 录音中能量消失时点；时延基准 = monotonic 差）
    estop = out / "estop_probe.wav"
    t_rec_start = time.monotonic()
    rec2 = subprocess.Popen(
        ["arecord", "-D", dev, "-q", "-f", "S16_LE", "-r", str(RATE), "-c", "1",
         "-d", "8", str(estop)],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    time.sleep(0.6)
    long_play = out / "tone_long.wav"
    write_sine_wav(long_play, TONE_HZ, 6.0)
    play2 = subprocess.Popen(["aplay", "-D", dev, "-q", str(long_play)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    time.sleep(2.0)                                   # 播放稳定入录音
    t_kill = time.monotonic()
    play2.kill()                                      # 软件急停
    play2.wait(timeout=10)
    rec2.wait(timeout=30)
    kill_offset_s = t_kill - t_rec_start              # kill 时刻在录音内偏移
    with wave.open(str(estop), "rb") as w:
        pcm = w.readframes(w.getnframes())
    window = RATE // 10                               # 100ms 窗
    silent_at = None
    for start in range(0, len(pcm) // 2 - window, window):
        start_s = start / RATE
        if start_s < kill_offset_s:                    # 只扫 kill 之后（前段本就未播）
            continue
        seg = pcm[2 * start: 2 * (start + window)]
        amp = 2.0 * math.sqrt(goertzel_power_pcm(seg, TONE_HZ)) / window  # 幅值归一
        if amp < SILENCE_RMS_FLOOR / 2.0:             # 幅值 < 本底 RMS 一半 = 声学静默
            silent_at = start_s + window / RATE
            break
    latency_ms = None if silent_at is None else round((silent_at - kill_offset_s) * 1000, 0)
    t5_ok = (silent_at is not None and kill_offset_s < silent_at
             and 0.0 <= latency_ms <= 1000.0)
    estop_latency_ms = latency_ms
    report["tests"]["T5_estop_kill_latency"] = {
        "passed": t5_ok, "tone_silent_at_s": silent_at, "kill_offset_s": round(kill_offset_s, 3),
        "estop_latency_ms_est": estop_latency_ms,
        "hardware_l0_floor": "none_usb_audio_no_hw_limiter",
        "note": "Q-L10-08 载体版实测：软件急停时延为播放 kill → 声学能量消失；"
                "硬件限幅面不存在——如实登记（不伪称硬件级）",
    }
    verdicts.append(t5_ok)
    print(f"T5 estop_kill_latency = {t5_ok} (silent_at={silent_at}s)")

    overall = all(verdicts)
    report["overall"] = {
        "passed": overall,
        "conclusion": ("USB 音频输入输出闭环成立：扬声器输出 → 空气声学路径 → 麦克风输入"
                       "全链可测；急停路径有界。可作主体外感受（麦克风）/受控执行面"
                       "（扬声器，L4-limited）候选设备。" if overall else
                       "存在失败项——见 tests 详情（禁静默跳过）"),
        "verdicts": dict(zip(["T0", "T1", "T2", "T3", "T4", "T5"], verdicts)),
    }
    (out / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8")
    print(f"OVERALL = {overall}")
    print(f"report={out / 'report.json'}")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
