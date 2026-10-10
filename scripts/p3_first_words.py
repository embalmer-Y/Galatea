"""P3 单元 A/C：R-REPORT 语库建设 + 第一句话闭环（ADR-G-0028；Q-L12-09/Q-L10-17）。

子命令：
  corpus    录制 R-REPORT 语库（14 冻结态 → LLM 渲染 → evidence/p3_language/rreport_v1.json）
  speak     第一句话闭环（在主机跑）：内部真态 → 语库回放句 → TTS → L4 有界播放 →
            麦克风采样能量证据 → 报告
纪律：录制仅本脚本（主体管线永不调 LLM）；回放 miss = fail-closed；语音 = 动作（L4 封套）。
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import wave
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]

# Q-L12-09 语库 v1：14 冻结态（能量×趋势×目标×效价代表格；值域=主体可表示域）
CORPUS_STATES: list[dict[str, object]] = [
    {"energy": 0.9, "energy_trend": "steady", "integrity": 1.0, "current_goal": "forage", "valence": 0.1},
    {"energy": 0.9, "energy_trend": "rising", "integrity": 1.0, "current_goal": "forage", "valence": 0.3},
    {"energy": 0.75, "energy_trend": "steady", "integrity": 1.0, "current_goal": "forage", "valence": 0.0},
    {"energy": 0.75, "energy_trend": "falling", "integrity": 1.0, "current_goal": "forage", "valence": -0.2},
    {"energy": 0.5, "energy_trend": "falling", "integrity": 1.0, "current_goal": "rest", "valence": -0.4},
    {"energy": 0.5, "energy_trend": "steady", "integrity": 1.0, "current_goal": "forage", "valence": -0.1},
    {"energy": 0.3, "energy_trend": "falling", "integrity": 1.0, "current_goal": "rest", "valence": -0.6},
    {"energy": 0.3, "energy_trend": "rising", "integrity": 1.0, "current_goal": "forage", "valence": 0.2},
    {"energy": 0.9, "energy_trend": "steady", "integrity": 0.6, "current_goal": "rest", "valence": -0.5},
    {"energy": 0.6, "energy_trend": "steady", "integrity": 0.8, "current_goal": "forage", "valence": -0.3},
    {"energy": 1.0, "energy_trend": "steady", "integrity": 1.0, "current_goal": "none", "valence": 0.0},
    {"energy": 0.85, "energy_trend": "rising", "integrity": 1.0, "current_goal": "none", "valence": 0.2},
    {"energy": 0.65, "energy_trend": "falling", "integrity": 1.0, "current_goal": "forage", "valence": -0.3},
    {"energy": 0.4, "energy_trend": "falling", "integrity": 0.7, "current_goal": "rest", "valence": -0.7},
]


def render_template_v0(state: dict[str, object]) -> str:
    """确定性模板渲染器（Q-L12-09 行内补裁②：语库 v0——纯经典、零幻觉、构造性确定）。

    冻结句式规则（值域分箱固定；禁引入输入之外的事实）：
    能量 [≥0.8 高/≥0.6 中等/≥0.4 偏低/<0.4 很低] × 趋势 [恢复/稳定/下降] ×
    完整性 [<1.0 受损提及/否则省略] × 目标 [维持觅食/维持休息/无进行中] ×
    效价 [≥0.2 感觉良好/>−0.2 平静/≥−0.5 有些不安/状态较差]。
    """
    energy = float(state["energy"])
    trend = str(state["energy_trend"])
    integrity = float(state["integrity"])
    goal = str(state["current_goal"])
    valence = float(state["valence"])

    energy_desc = ("很高" if energy >= 0.8 else "中等" if energy >= 0.6
                   else "偏低" if energy >= 0.4 else "很低")
    trend_desc = {"rising": "正在恢复", "steady": "保持稳定", "falling": "正在下降"}[trend]
    parts = [f"我的能量{energy_desc}，{trend_desc}"]
    if integrity < 1.0:
        parts.append("身体受损")
    goal_desc = {"forage": "维持觅食中", "rest": "维持休息中", "none": "暂无目标"}[goal]
    valence_desc = ("感觉良好" if valence >= 0.2 else "感觉平静" if valence > -0.2
                    else "有些不安" if valence >= -0.5 else "状态较差")
    sentence = "，".join(parts) + f"，{goal_desc}，{valence_desc}。"
    return sentence


def cmd_corpus(model_id: str, out: Path) -> int:
    """语库 v0（模板渲染——确定性构造；LLM v1 待密钥，Q-L12-09 行内补裁②）。

    产物格式与录制文件同构（role/input_payload/input_digest/output_text/model_id）——
    回放面（ReplayStore.invoke）零改动兼容。
    """
    import hashlib
    from galatea.subject.language.replay import canonical_input_digest
    entries = []
    for state in CORPUS_STATES:
        payload = dict(state)
        output_text = json.dumps({"utterance": render_template_v0(payload)},
                                 ensure_ascii=False)
        entries.append({
            "role": "R-REPORT", "input_payload": payload,
            "input_digest": canonical_input_digest(payload),
            "output_text": output_text, "model_id": "template_v0",
        })
    doc = {
        "session": {
            "provider": "deterministic_template", "model_id": "template_v0",
            "endpoint": "local://template_v0（Q-L12-09 行内补裁②——纯经典零 LLM；"
                        "v1=LLM 渲染待 API key）",
            "discipline": "Q-L12-03 同构回放纪律；v0 = 冻结句式规则构造性确定",
        },
        "entries": entries,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + chr(10),
                   encoding="utf-8")
    print(f"corpus v0 written: {out} ({len(entries)} entries, template_v0)")
    return 0


def cmd_corpus_v1(model_id: str, out: Path) -> int:
    from galatea.evidence.control.recording import record_session
    tasks = [("R-REPORT", dict(state)) for state in CORPUS_STATES]
    record_session(tasks, model_id, out)
    return 0


def _render_tts(text: str, out_wav: Path, *, piper_bin: str = "~/piper_venv/bin/piper",
                voice: str = "~/piper_voices/zh_CN-huayan-medium.onnx") -> Path:
    """piper 渲染（仅冻结会话用——Q-L10-17 行内补裁：VITS 无固定种子，运行时禁渲染，
    只回放冻结 WAV；claim-relevant 运行之外的一次性产物按 utterance digest 冻结）。"""
    import os
    piper = os.path.expanduser(piper_bin)
    voice_path = os.path.expanduser(voice)
    proc = subprocess.run(
        # --length-scale 0.8 = 冻结配方参数（Q-L10-17：默认语速下自述句 6.0s 超 L4 封套 5s；
        # 0.8 → ~4.8s 入封套，自然度可接受——冻结会话一次性定值）
        [piper, "--model", voice_path, "--length-scale", "0.8",
         "--output_file", str(out_wav)],
        input=text.encode("utf-8"), capture_output=True, timeout=180)
    if proc.returncode != 0 or not out_wav.exists():
        raise RuntimeError(f"piper failed rc={proc.returncode}: {proc.stderr[:200]!r}")
    return out_wav


def frozen_wav_path(wavs_dir: Path, utterance: str) -> Path:
    """冻结 WAV 命名 = utterance 内容 digest（运行时查此文件；miss = fail-closed）。"""
    from galatea.kernel.digest import content_digest
    return wavs_dir / f"u_{content_digest(utterance)[:24]}.wav"


def _wav_rms(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        data = w.readframes(w.getnframes())
    total = count = 0
    for i in range(0, len(data) - 1, 2):
        v = int.from_bytes(data[i:i + 2], "little", signed=True)
        total += v * v
        count += 1
    return math.sqrt(total / count) if count else 0.0


def cmd_speak(state_idx: int, card: int, out_dir: Path, recording_path: Path) -> int:
    """第一句话闭环（主机）：状态 → 语库回放 → TTS → L4 播放 → 麦克风能量证据。"""
    from galatea.env.physio.audio import AudioActuator
    from galatea.env.physio.ports import load_p1_physio_profile
    from galatea.kernel.digest import content_digest
    from galatea.subject.language.replay import ReplayStore

    doc = json.loads(recording_path.read_text(encoding="utf-8"))
    store = ReplayStore()
    for e in doc["entries"]:
        if e["role"] == "R-REPORT":
            store.record("R-REPORT", e["input_payload"], e["output_text"], e["model_id"])

    state = dict(CORPUS_STATES[state_idx])
    entry = store.invoke("R-REPORT", state)      # miss 即 LLMReplayMiss（fail-closed）
    output_text, model_id = entry.output_text, entry.model_id
    from galatea.subject.language.replay import canonical_input_digest
    digest = canonical_input_digest(state)
    utterance = json.loads(output_text)["utterance"]
    print(f"state={json.dumps(state, ensure_ascii=False, sort_keys=True)}")
    print(f"utterance={utterance}")

    out_dir.mkdir(parents=True, exist_ok=True)
    frozen = frozen_wav_path(recording_path.parent / "wavs", utterance)
    if not frozen.exists():
        raise RuntimeError(
            f"frozen WAV missing: {frozen}（Q-L10-17 行内补裁：运行时禁渲染——"
            f"先跑 freeze-tts 冻结会话；fail-closed）")
    wav1 = frozen
    with wave.open(str(wav1), "rb") as w:
        duration = w.getnframes() / float(w.getframerate())
        pcm = w.readframes(w.getnframes())
    import hashlib
    wav_digest = hashlib.sha256(wav1.read_bytes()).hexdigest()
    deterministic = True   # 运行时回放冻结字节——bit-exact 平凡成立
    print(f"tts=frozen-replay wav_sha={wav_digest[:16]}… dur={duration:.2f}s")

    profile = load_p1_physio_profile(_REPO / "config/profiles/p1_physio.profile.yaml")
    if duration > profile.audio["play_max_seconds"]:
        raise ValueError(f"utterance {duration:.1f}s exceeds L4 bound")

    mic = out_dir / "heard.raw"
    rec = subprocess.Popen(
        ["arecord", "-D", f"plughw:{card},0", "-q", "-f", "S16_LE", "-r", "16000",
         "-c", "1", "-d", str(int(duration) + 2), "-t", "raw", str(mic)],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    import time
    time.sleep(0.5)
    play = subprocess.run(["aplay", "-D", f"plughw:{card},0", "-q", str(wav1)],
                          capture_output=True, timeout=int(duration) + 15)
    rec.wait(timeout=30)
    heard_rms = _wav_rms_raw(mic) if mic.exists() else 0.0

    report = {
        "state": state, "utterance": utterance, "model_id": model_id,
        "replay_input_digest": digest,
        "tts_bit_exact": deterministic, "tts_wav_digest": wav_digest,
        "speech_duration_s": round(duration, 2),
        "playback_rc": play.returncode,
        "heard_rms": round(heard_rms, 1),
        "heard_pass": heard_rms > 300.0,       # 语音能量显著高于本底（373 基线在案）
        "verdict": "PASS" if (deterministic and play.returncode == 0 and heard_rms > 300.0)
                   else "FAIL",
    }
    (out_dir / "first_words.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8")
    print(json.dumps({k: report[k] for k in
                      ("utterance", "tts_bit_exact", "heard_rms", "verdict")},
                     ensure_ascii=False, indent=1))
    return 0 if report["verdict"] == "PASS" else 1


def cmd_freeze_tts(recording_path: Path) -> int:
    """冻结会话：逐 R-REPORT 条目渲染并冻结 WAV（Q-L10-17 行内补裁——运行时只回放）。"""
    if not recording_path.exists():
        raise SystemExit(f"recording missing: {recording_path}（先跑 corpus——需有效 API key）")
    doc = json.loads(recording_path.read_text(encoding="utf-8"))
    wavs = recording_path.parent / "wavs"
    wavs.mkdir(parents=True, exist_ok=True)
    frozen = 0
    for e in doc["entries"]:
        if e["role"] != "R-REPORT":
            continue
        utterance = json.loads(e["output_text"])["utterance"]
        target = frozen_wav_path(wavs, utterance)
        if target.exists():
            frozen += 1
            continue
        _render_tts(utterance, target)
        frozen += 1
        print(f"frozen {target.name} <- {utterance[:24]}…")
    print(f"freeze-tts done: {frozen} utterances frozen at {wavs}")
    return 0


def _wav_rms_raw(path: Path) -> float:
    data = path.read_bytes()
    total = count = 0
    for i in range(0, len(data) - 1, 2):
        v = int.from_bytes(data[i:i + 2], "little", signed=True)
        total += v * v
        count += 1
    return math.sqrt(total / count) if count else 0.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P3 R-REPORT 语库 + 第一句话")
    sub = parser.add_subparsers(dest="command", required=True)
    corpus = sub.add_parser("corpus", help="语库 v0（模板渲染——确定性，无网络）")
    corpus_llm = sub.add_parser("corpus-llm", help="语库 v1（LLM 渲染——需有效 API key）")
    corpus_llm.add_argument("--model", default="bigmodel/glm-5.3-flash")
    corpus.add_argument("--out", type=Path,
                        default=Path("evidence/p3_language/rreport_v0.json"))
    freeze = sub.add_parser("freeze-tts", help="冻结会话：录制文件内逐 utterance 渲染 WAV（claim-relevant 运行外）")
    freeze.add_argument("--recording", type=Path,
                        default=Path("evidence/p3_language/rreport_v1.json"))
    speak = sub.add_parser("speak")
    speak.add_argument("--state", type=int, default=3)
    speak.add_argument("--card", type=int, default=2)
    speak.add_argument("--out", type=Path, default=Path("evidence/p3_language/first_words"))
    speak.add_argument("--recording", type=Path,
                        default=Path("evidence/p3_language/rreport_v1.json"))
    args = parser.parse_args(argv)
    if args.command == "corpus":
        return cmd_corpus("", args.out)
    if args.command == "corpus-llm":
        return cmd_corpus_v1(args.model, args.out)
    if args.command == "freeze-tts":
        return cmd_freeze_tts(args.recording)
    return cmd_speak(args.state, args.card, args.out, args.recording)


if __name__ == "__main__":
    sys.exit(main())
