"""R-NORMEXTRACT：规范候选提取（L12 §4.1/§4.3 / §10 norm.py；REPLAY_LLM）。

无源规范禁令（L08 §8 不变量 6 / L12 §4.1）：derivation_refs 必填非空，缺失即
SchemaViolation（REJECT(UNSOURCED_NORM) 同义——C-4 构造面在 goals 侧二次强制）。
本模块只产出语言侧 NormSource 提案；目的地 = L08 C-4 检查（motives.motive_norm），
禁直写 OwnedGoal/仲裁向量（社会认知 ≠ 执行权限，Q-L12-04②c 同族）。
"""
import json
from dataclasses import dataclass
from typing import Any, cast

from galatea.subject.language.ports import LanguagePlaneViolation
from galatea.subject.language.replay import ReplayStore
from galatea.subject.language.roles import RoleKind, get_role

__all__ = ["NormSource", "extract_norm_source"]


@dataclass(frozen=True, slots=True)
class NormSource:
    """语言侧规范提案（L12 §4.1：NormSource(derivation_refs[] 必填)）。"""

    norm_id: str
    derivation_refs: tuple[str, ...]     # 每 ref 须为 registry 可解析事件 id（Q-L08-07②）
    source_event_ref: str                # RECEIVED 语言事件 id

    def __post_init__(self) -> None:
        if not self.norm_id:
            raise LanguagePlaneViolation("NormSource requires norm_id")
        if not self.derivation_refs:
            raise LanguagePlaneViolation(
                "NormSource requires derivation_refs（无源规范 = UNSOURCED_NORM，L08 §8 不变量 6）"
            )
        if not self.source_event_ref:
            raise LanguagePlaneViolation("NormSource requires source_event_ref")


def extract_norm_source(
    statement_text: str, requester: str, source_event_ref: str, replay: ReplayStore
) -> NormSource:
    """R-NORMEXTRACT 调用（提取决策 = 录制回放；ref 齐全性 = schema 级机械强制）。"""
    spec = get_role(RoleKind.R_NORMEXTRACT)
    payload = {"text": statement_text, "requester": requester}
    entry = replay.invoke(spec.kind.value, payload)
    try:
        out = cast(dict[str, Any], json.loads(entry.output_text))
        norm_id = str(out["norm_id"])
        refs = tuple(str(r) for r in out["derivation_refs"])
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise LanguagePlaneViolation(f"R-NORMEXTRACT output schema violation: {exc}") from exc
    return NormSource(
        norm_id=norm_id, derivation_refs=refs, source_event_ref=source_event_ref,
    )
