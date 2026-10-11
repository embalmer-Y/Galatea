"""P3 单元 E：发声时机循环（Q-L08-10——主体因状态漂移**内生决定**说话）。

在主机跑（真 zenoh 流 + 真情感引擎 + 真仲裁 + 真发声）：
    cd ~/galatea_deploy && export PATH=$HOME/.local/bin:$PATH PYTHONPATH=$HOME/galatea_deploy
    uv run python scripts/p3_speech_initiative.py --minutes 2 --card 2 \
        --out evidence/p3_language/speech_initiative

闭环：body-sim 电源流（真 zenoh）→ energy（电源余量比）→ 真情感管线（valence）→
语库分箱（Q-L12-09 冻结格）→ 自述冲动（分箱变化比例）→ Pareto 仲裁（与占位觅食
动机非独占竞争）→ 胜出 → L4 播放当前格冻结 WAV → 麦克风能量证据。
纪律：WAV/语料缺失 = fail-closed 跳过留痕；判据 = 至少一次内生发声事件。
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1] if (Path(__file__).resolve().parents[1] / "config").exists() \
    else Path(__file__).resolve().parents[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="发声时机循环（自述冲动内生决策）")
    parser.add_argument("--minutes", type=float, default=2.0)
    parser.add_argument("--card", type=int, default=None,
                        help="ALSA 卡号；缺省 = 按设备名锚定自动解析（R6 纪律）")
    parser.add_argument("--router", default="tcp/127.0.0.1:7447")
    parser.add_argument("--corpus", type=Path, default=_REPO / "evidence/p3_language/rreport_v1.json")
    parser.add_argument("--wavs", type=Path, default=_REPO / "evidence/p3_language/wavs")
    parser.add_argument("--out", type=Path, default=_REPO / "evidence/p3_language/speech_initiative")
    args = parser.parse_args(argv)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    card = args.card if args.card is not None else resolve_usb_card()
    print(f"usb audio card resolved: {card}")

    import zenoh
    import cbor2
    from galatea.subject.affect.pipeline import AffectPipeline
    from galatea.subject.affect.ports import AffectCycleInputs
    from galatea.subject.c2profile import load_c2_affect_profile
    from galatea.subject.goals.arbitration import pareto_front, vector_of
    from galatea.subject.goals.motives import Motive, MotiveSource
    from galatea.subject.goals.report_motive import (
        bin_vector,
        nearest_corpus_state,
        self_report_motive,
    )

    corpus_doc = json.loads(args.corpus.read_text(encoding="utf-8"))
    corpus_states = [dict(e["input_payload"]) for e in corpus_doc["entries"]
                     if e["role"] == "R-REPORT"]
    utterances = {json.dumps(dict(e["input_payload"]), sort_keys=True,
                             separators=(",", ":"), ensure_ascii=False):
                  json.loads(e["output_text"])["utterance"]
                  for e in corpus_doc["entries"] if e["role"] == "R-REPORT"}

    affect = AffectPipeline(load_c2_affect_profile(_REPO / "config/profiles/c2_affect.profile.yaml"))

    samples: list[dict[str, object]] = []
    speech_events: list[dict[str, object]] = []
    skipped: list[str] = []
    last_reported_bins = None
    prev_energy: float | None = None
    import threading
    speak_lock = threading.Lock()   # 设备串行（zenoh 回发并发 → aplay/arecord 争用即败）

    def on_sample(sample: zenoh.Sample) -> None:
        nonlocal last_reported_bins, prev_energy
        key = str(sample.key_expr)
        if not key.endswith("sys/power"):
            return
        try:
            obj = cbor2.loads(bytes(sample.payload))
        except Exception:
            return
        budget = max(1.0, float(obj.get("budget_ma", 0)))
        used = max(0.0, float(obj.get("used_ma", 0)))
        energy = round(max(0.0, 1.0 - used / budget), 6)
        # 真情感管线（energy 驱动驱力误差 → valence）
        affect_out = affect.step(AffectCycleInputs(cycle=len(samples), body_energy=energy))
        valence = _state_field(affect_out, "valence") or 0.0
        trend = ("steady" if prev_energy is None or abs(energy - prev_energy) < 1e-9
                 else "rising" if energy > prev_energy else "falling")
        prev_energy = energy
        state = {"energy": energy, "energy_trend": trend, "integrity": 1.0,
                 "current_goal": "none", "valence": round(valence, 4)}
        bins = bin_vector(state)

        # 自述冲动 → 仲裁（SELF_REPORT vs 占位觅食动机——非独占）
        motive = self_report_motive(state, last_reported_bins, len(samples),
                                    evidence_ref=f"power:{key}")
        front_ids: tuple[str, ...] = ()
        vectors = {"forage": (0.5, 0.0, 0.0, 0.0, 0.5)}      # 占位觅食（无目标栈运行时）
        if motive is not None:
            cv = vector_of("self_report", motive)
            vectors[cv.candidate_id] = cv.vector
        front_ids = pareto_front(vectors)

        spoke = False
        if motive is not None and "self_report" in front_ids:
            if not speak_lock.acquire(blocking=False):
                skipped.append(f"device_busy at cycle {len(samples)}（串行锁——并发回调让路）")
            else:
                try:
                    corpus_state = nearest_corpus_state(state, corpus_states)
                    ckey = json.dumps(corpus_state, sort_keys=True,
                                      separators=(",", ":"), ensure_ascii=False)
                    utterance = utterances.get(ckey)
                    wav = _frozen_wav(args.wavs, utterance) if utterance else None
                    if wav is None or utterance is None:
                        skipped.append(f"corpus/wav miss at cycle {len(samples)}")
                    else:
                        spoke = _speak(wav, utterance, card, out, len(samples),
                                       state, bins, motive.urgency, speech_events)
                        if spoke:
                            # 自述已实际播出——分箱基线更新（heard = 验证遥测，非行为门槛）
                            last_reported_bins = bins
                finally:
                    speak_lock.release()
        samples.append({"cycle": len(samples), "energy": energy, "trend": trend,
                        "valence": round(valence, 4), "bins": list(bins),
                        "urge": round(motive.urgency, 3) if motive else 0.0,
                        "front": list(front_ids), "spoke": spoke})

    conf = zenoh.Config()
    conf.insert_json5("connect", json.dumps({"endpoints": [args.router]}))
    session = zenoh.open(conf)
    sub = session.declare_subscriber("tessera/**", on_sample)
    print(f"speech-initiative loop: {args.minutes} min, corpus={args.corpus.name}")
    time.sleep(args.minutes * 60)
    sub.undeclare()
    session.close()

    report = {
        "duration_minutes": args.minutes,
        "power_samples": len(samples),
        "speech_events": speech_events,
        "skipped_fail_closed": skipped,
        "bins_trace_head": [s["bins"] for s in samples[:8]],
        "endogenous_speech": bool(speech_events),
        "verdict": "PASS" if speech_events else "FAIL",
    }
    (out / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8")
    print(f"speech_events={len(speech_events)} samples={len(samples)} "
          f"verdict={report['verdict']}")
    return 0 if speech_events else 1


def resolve_usb_card() -> int:
    """按设备名锚定解析 USB 声卡号（REV-0025 R6 同纪律：USB 重枚举致索引漂移——
    实测 card 2→1；禁硬编码）。找不到 → 抛（fail-closed）。"""
    import re
    cards = Path("/proc/asound/cards").read_text(encoding="utf-8")
    m = re.search(r"^\s*(\d+)\s+\[Device\s*\]", cards, re.M)
    if m is None:
        m = re.search(r"^\s*(\d+)\s+\[USB PnP Audio Device\]", cards, re.M)
    if m is None:
        raise RuntimeError("USB audio card not found in /proc/asound/cards: " + cards[:200])
    return int(m.group(1))


def _state_field(out: object, field: str) -> float | None:
    for holder in (out, getattr(out, "affect", None), getattr(out, "state", None)):
        value = getattr(holder, field, None) if holder is not None else None
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _frozen_wav(wavs_dir: Path, utterance: str) -> Path | None:
    from galatea.kernel.digest import content_digest
    p = wavs_dir / f"u_{content_digest(utterance)[:24]}.wav"   # 与 frozen_wav_path 同式
    return p if p.exists() else None


def _speak(wav: Path, utterance: str, card: int, out: Path, cycle: int,
           state: dict[str, object], bins: tuple[str, ...], urgency: float,
           events: list[dict[str, object]]) -> bool:
    import hashlib
    import wave as _wave
    with _wave.open(str(wav), "rb") as _w:
        _dur = _w.getnframes() / float(_w.getframerate())
    mic = out / f"heard_{cycle}.raw"
    proc_rec = subprocess.Popen(
        ["arecord", "-D", f"plughw:{card},0", "-q", "-f", "S16_LE", "-r", "16000",
         "-c", "1", "-d", str(int(_dur) + 1), "-t", "raw", str(mic)],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    time.sleep(0.4)
    play = subprocess.run(["aplay", "-D", f"plughw:{card},0", "-q", str(wav)],
                          capture_output=True, timeout=20)
    proc_rec.wait(timeout=30)
    data = mic.read_bytes() if mic.exists() else b""
    total = count = 0
    for i in range(0, len(data) - 1, 2):
        v = int.from_bytes(data[i:i + 2], "little", signed=True)
        total += v * v
        count += 1
    rms = math.sqrt(total / count) if count else 0.0
    event = {"cycle": cycle, "state": state, "bins": list(bins),
             "urgency": round(urgency, 3), "utterance": utterance,
             "wav": wav.name, "wav_sha256": hashlib.sha256(wav.read_bytes()).hexdigest(),
             "playback_rc": play.returncode, "heard_rms": round(rms, 1),
             "heard": rms > 300.0}
    events.append(event)
    print(f"  [speech] cycle={cycle} urgency={urgency:.2f} 「{utterance}」 heard_rms={rms:.0f}")
    return bool(play.returncode == 0 and rms > 300.0)


if __name__ == "__main__":
    sys.exit(main())
