"""录制回放机（L12 §10 补录件 replay.py；Q-L12-03 LLM 确定性纪律的唯一承载）。

合同（Q-L12-03，AI-v2 2026-10-07）：
- claim-relevant 运行中 LLM 角色输出唯一允许来源 = 录制回放——(role, input_digest)
  寻址，输入规范化 = 排序键 JSON（sort_keys + 紧凑分隔符，与 kernel digest 同纪律）；
- 回放 miss = fail closed：Unknown(LLM_REPLAY_MISS) 语义异常抛出，**禁在线补调**
  （本模块不存在任何网络调用路径——运行时无在线面，结构上排除事后选择）；
- 录制会话（exploration/recording）由评价编排层的录制工具执行，不入主体管线；
  录制工件（prompt 模板版本 + 模型标识 + 原始响应）digest 锚入 artifact_manifest
  （Q-T08 同构），模型标识入 EvidenceResult 元数据（Q-L03-07 绑定实现 digest 同族）。
"""
import hashlib
import json
from dataclasses import dataclass
from typing import Any

__all__ = ["LLMReplayMiss", "ReplayEntry", "ReplayStore", "canonical_input_digest"]


class LLMReplayMiss(LookupError):
    """回放未命中（fail closed——调用方转为 Unknown(LLM_REPLAY_MISS) 留痕，禁在线补调）。"""


@dataclass(frozen=True, slots=True)
class ReplayEntry:
    """录制条目（模型标识随条目走——EvidenceResult 元数据来源）。"""

    output_text: str
    model_id: str


def canonical_input_digest(payload: dict[str, Any]) -> str:
    """输入规范化 digest（排序键 JSON；同输入同 digest——回放寻址唯一键）。"""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ReplayStore:
    """录制回放库（(role, input_digest) → ReplayEntry；运行期只读 + 显式 record）。"""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], ReplayEntry] = {}

    def record(
        self, role: str, payload: dict[str, Any], output_text: str, model_id: str
    ) -> str:
        """录制会话写入点（评价编排层专用；主体管线永不调用）。"""
        key = (role, canonical_input_digest(payload))
        self._entries[key] = ReplayEntry(output_text=output_text, model_id=model_id)
        return key[1]

    def invoke(self, role: str, payload: dict[str, Any]) -> ReplayEntry:
        """角色调用（唯一运行时路径：回放命中或 fail closed，无第三态）。"""
        key = (role, canonical_input_digest(payload))
        entry = self._entries.get(key)
        if entry is None:
            raise LLMReplayMiss(
                f"Unknown(LLM_REPLAY_MISS): no recording for ({role!r},"
                f" input_digest={key[1][:16]}…)——fail closed，禁在线补调（Q-L12-03③）"
            )
        return entry

    def __len__(self) -> int:
        return len(self._entries)
