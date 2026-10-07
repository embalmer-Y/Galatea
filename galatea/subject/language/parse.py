"""R-PARSE：语言感觉帧分型（L12 §4.1/§4.3 / §10 parse.py；REPLAY_LLM）。

分型输出经录制回放承载（开放形解析 = LLM 职责）；schema 校验失败即拒（不降级
自由文本入库）。statement 类 confidence clamp ≤ 0.5（Q-L12-06②：Q-L03-02
believe_threshold 锚——语言线索自身置信恒不越过主体相信线，clamp 越界留痕）。
statement 的世界侧效应 = 零后验贡献（Q-L12-06①），唯一合法效应 = 触发主体自身
验证行为（active_perception/look）——本模块只产出分型，路由由调用方执行。
"""
import json
from typing import Any, cast

from galatea.subject.c4profile import C4ActionSocialParams
from galatea.subject.language.ports import LanguagePlaneViolation, TypedFields
from galatea.subject.language.replay import ReplayStore
from galatea.subject.language.roles import RoleKind, get_role
from galatea.subject.sensorium.ports import LanguageFeatures

__all__ = ["parse_language_frame"]


def parse_language_frame(
    frame: LanguageFeatures, text_ref: str, replay: ReplayStore, profile: C4ActionSocialParams,
) -> TypedFields:
    """R-PARSE 调用（输入 = LANGUAGE 帧特征；输出 = 分型 + 置信度，schema 受限）。

    回放输出合同（录制会话冻结）：{"type": request|statement|question|instruction,
    "confidence": [0,1] 浮点}。类型外词表/非置信数值 → SchemaViolation 拒绝。
    """
    spec = get_role(RoleKind.R_PARSE)
    payload = {"text": frame.statement_text, "requester": frame.requester}
    entry = replay.invoke(spec.kind.value, payload)
    try:
        out = cast(dict[str, Any], json.loads(entry.output_text))
        kind = str(out["type"])
        confidence = float(out["confidence"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise LanguagePlaneViolation(f"R-PARSE output schema violation: {exc}（不降级入库）") from exc
    clamped = False
    if kind == "statement" and confidence > profile.statement_confidence_max:
        confidence = profile.statement_confidence_max   # Q-L12-06② clamp + 留痕
        clamped = True
    return TypedFields(kind=kind, confidence=confidence, text_ref=text_ref, clamped=clamped)
