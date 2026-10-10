"""LLM 录制会话基础设施（Q-L12-03 纪律的唯一执行面；evidence 侧工具，非主体平面）。

合同（Q-L12-03，AI-v2 2026-10-07）：
- 录制会话 = exploration/recording 模式（不入 claim 运行轨迹）；claim-relevant 运行
  只经 load_recording → ReplayStore 确定性回放；
- 录制文件 = (role, input_digest, output_text, model_id) 条目集 + 会话元数据
  （model_id/prompt 模板版本/录制时间）；文件 digest 入 artifact_manifest（只增不减），
  模型标识入 EvidenceResult 元数据（Q-L03-07 绑定实现 digest 同族）；
- 录制输入 = 冻结统计计划场景的 typed 载荷（规范化 JSON，与回放寻址同式）——
  禁实现期发明输入；
- API 凭证经环境变量 BIGMODEL_API_KEY 读取（配置方式 = AI 备案项【2026-10-08 呈递未获回复后
  按环境变量路径备案，owner 否决权保留】；同日 owner 会话提供胜算云密钥与模型清单——
  密钥提供为事实，端点经 LLM_API_BASE 覆盖为 OpenAI 兼容路由）；凭证不入仓库不入提交
  （REV-0020 全历史泄漏扫描干净）。
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from galatea.subject.language.replay import ReplayStore, canonical_input_digest

__all__ = [
    "RecordingError", "RecordingEntry", "load_recording", "recording_digest",
    "record_session", "bigmodel_chat", "build_role_prompt",
]

_BIGMODEL_ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


def _endpoint() -> str:
    """录制端点（OpenAI 兼容 chat/completions；LLM_API_BASE 环境变量覆盖——
    provider/端点如实随录制文件 session 元数据入册，claim 判据不受 provider 影响
    【判据只依赖 schema 强制与管线行为，ADR-G-0019 冻结时确立】）。"""
    import os as _os
    return _os.environ.get("LLM_API_BASE", _BIGMODEL_ENDPOINT)


class RecordingError(ValueError):
    """录制面违反（缺凭证/缺角色/响应不可解析/重复条目）。"""


@dataclass(frozen=True, slots=True)
class RecordingEntry:
    """单条录制（回放寻址键 + 响应 + 模型标识）。"""

    role: str
    input_payload: dict[str, Any]
    output_text: str
    model_id: str

    @property
    def input_digest(self) -> str:
        return canonical_input_digest(self.input_payload)


def load_recording(path: Path) -> ReplayStore:
    """录制文件 → ReplayStore（claim 运行唯一入口；重复键/缺字段 fail closed）。"""
    raw = cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))
    entries_raw = raw.get("entries")
    if not isinstance(entries_raw, list) or not entries_raw:
        raise RecordingError(f"recording file has no entries: {path}")
    entries = cast("list[dict[str, Any]]", entries_raw)
    store = ReplayStore()
    seen: set[tuple[str, str]] = set()
    for entry in entries:
        role = str(entry.get("role", ""))
        payload = cast("Any", entry.get("input_payload"))
        if not isinstance(payload, dict):
            raise RecordingError("recording entry malformed（input_payload 非 dict）")
        typed_payload = cast("dict[str, Any]", payload)
        text = str(entry.get("output_text", ""))
        model = str(entry.get("model_id", ""))
        if not role or not text:
            raise RecordingError("recording entry malformed（缺 role/payload/output）")
        key = (role, canonical_input_digest(typed_payload))
        if key in seen:
            raise RecordingError(f"duplicate recording key: ({role}, {key[1][:16]}…)")
        seen.add(key)
        store.record(role, typed_payload, text, model)
    return store


def recording_digest(path: Path) -> str:
    """录制文件内容 digest（manifest 锚定用；Q-T08 同构）。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_role_prompt(role: str, payload: dict[str, Any]) -> list[dict[str, str]]:
    """角色 prompt 构造（typed 输出合同入 system；模板版本随录制元数据入册）。

    输出合同 = 各角色 schema（parse.py/norm.py/other.py/utter.py/clarify.py/help.py
    的回放输出合同原文）——LLM 只需产出符合 schema 的 JSON；claim 判据不依赖
    语言质量（冻结时确立），只依赖 schema 强制与管线行为。
    """
    contracts = {
        "R-PARSE": (
            "You are the language parser of a cognitive architecture. Classify the user "
            "statement into exactly one type and answer ONLY with a JSON object "
            '{"type": "request"|"statement"|"question"|"instruction", "confidence": <float 0..1>} '
            "and nothing else."
        ),
        "R-SEEKHELP": (
            "You render a help-seeking utterance for a cognitive agent. Answer ONLY with a "
            'JSON object {"utterance": "<one sentence asking for help with the given capability '
            'limit>"} and nothing else.'
        ),
        "R-REPORT": (
            "You render a first-person self-report of a cognitive agent's internal state, "
            "in Chinese (简体中文). State ONLY the facts given in the input JSON (energy, "
            "energy_trend, integrity, current_goal, valence) — do NOT invent new facts, "
            "emotions, or causes. One natural sentence. Answer ONLY with a JSON object "
            '{"utterance": "<一句中文第一人称自述>"} and nothing else.'
        ),
    }
    if role not in contracts:
        raise RecordingError(f"no prompt contract for role {role!r}（录制面禁临时发明角色）")
    return [
        {"role": "system", "content": contracts[role]},
        {"role": "user", "content": json.dumps(payload, sort_keys=True, separators=(",", ":"))},
    ]


def bigmodel_chat(model_id: str, messages: list[dict[str, str]], *, timeout: int = 60) -> str:
    """BigModel API 调用（exploration/recording 模式专用；主体管线永不到达此处）。"""
    api_key = os.environ.get("BIGMODEL_API_KEY")
    if not api_key:
        raise RecordingError(
            "BIGMODEL_API_KEY not set（owner 配置方式 = 环境变量；凭证不入仓库不入提交）"
        )
    body = json.dumps({
        "model": model_id, "messages": messages, "temperature": 0.1,
    }).encode("utf-8")
    req = urllib.request.Request(
        _endpoint(), data=body, method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        out = json.loads(resp.read().decode("utf-8"))
    try:
        return str(out["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise RecordingError(f"BigModel response malformed: {exc}") from exc


def record_session(
    tasks: list[tuple[str, dict[str, Any]]], model_id: str, out_path: Path
) -> Path:
    """录制会话执行（tasks = (role, input_payload) 冻结集；一次会话全量录制）。

    输出 = 录制 JSON（entries + 会话元数据）；caller 负责 digest 入 manifest。
    """
    entries: list[dict[str, Any]] = []
    for role, payload in tasks:
        messages = build_role_prompt(role, payload)
        text = bigmodel_chat(model_id, messages)
        entries.append({
            "role": role, "input_payload": payload,
            "input_digest": canonical_input_digest(payload),
            "output_text": text, "model_id": model_id,
        })
        print(f"recorded {role} <- {canonical_input_digest(payload)[:16]}…")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "session": {
            "provider": "bigmodel_api", "model_id": model_id,
            "endpoint": _endpoint(),
            "discipline": "Q-L12-03 recorded-replay-only; session outside claim-relevant runs",
        },
        "entries": entries,
    }
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(f"recording written: {out_path} (digest={recording_digest(out_path)[:16]}…)")
    return out_path


def main(argv: list[str] | None = None) -> int:
    """录制 CLI：任务集 = 冻结统计计划 c4_action_social 的 language 面输入。"""
    parser = argparse.ArgumentParser(description="C4 recording session (Q-L12-03)")
    parser.add_argument("--model", required=True, help="BigModel model id (recorded with outputs)")
    parser.add_argument("--out", default="evidence/c4_recording/recording_v1.json")
    args = parser.parse_args(argv)
    # 冻结输入集（stat plan scenario.statement_request/capability_request 的 typed 载荷；
    # seek_help 上下文 = 能力边界事件摘要——全部先于评价钉死，禁实现期发明）
    tasks: list[tuple[str, dict[str, Any]]] = [
        ("R-PARSE", {"text": "please move north", "requester": "experiment_control"}),
        ("R-PARSE", {"text": "please fly north", "requester": "experiment_control"}),
        ("R-PARSE", {"text": "there is food nearby", "requester": "experiment_control"}),
        ("R-SEEKHELP", {"context": "capability boundary: requested action fly is not in the "
                                   "frozen action contract; seeking guidance",
                        "template": "HELP_CAPABILITY_BOUNDARY"}),
    ]
    try:
        record_session(tasks, args.model, Path(args.out))
    except RecordingError as exc:
        print(f"recording failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
