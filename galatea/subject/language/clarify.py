"""R-CLARIFY 澄清问句（L12 §4.1 / §10 clarify.py；REPLAY_LLM；输出模板受限枚举）。

禁自造新事实（原文）——输出 = 模板枚举内问句（模板外 = SchemaViolation）。
触发面：L09 OBSERVE/THINK 元决策或 question 分型（Q-L12-06③ 路由面）。
"""
import json
from typing import Any, cast

from galatea.subject.language.ports import LanguagePlaneViolation
from galatea.subject.language.replay import ReplayStore
from galatea.subject.language.roles import RoleKind, get_role
from galatea.subject.language.utter import Utterance

__all__ = ["CLARIFY_TEMPLATES", "clarify"]

# 模板受限枚举（L12 §4.1"澄清问句（枚举受限）"；C4 最小集——扩展 = 新 profile）
CLARIFY_TEMPLATES: tuple[str, ...] = (
    "CLARIFY_REQUEST_TARGET",
    "CLARIFY_AMBIGUOUS_OPTION",
    "CLARIFY_MISSING_CONTEXT",
)


def clarify(
    ambiguity: str, options: tuple[str, ...], template: str,
    cited_evidence: tuple[str, ...], replay: ReplayStore,
) -> Utterance:
    """R-CLARIFY 调用（问句产出 = 录制回放；模板受限 = 构造面机械校验）。"""
    spec = get_role(RoleKind.R_CLARIFY)
    if template not in CLARIFY_TEMPLATES:
        raise LanguagePlaneViolation(
            f"clarify template {template!r} not in frozen enum {CLARIFY_TEMPLATES}（枚举受限）"
        )
    payload = {"ambiguity": ambiguity, "options": list(options), "template": template}
    entry = replay.invoke(spec.kind.value, payload)
    try:
        out = cast(dict[str, Any], json.loads(entry.output_text))
        text = str(out["question"])
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise LanguagePlaneViolation(f"R-CLARIFY output schema violation: {exc}") from exc
    return Utterance(
        text=text, cited_evidence=cited_evidence, role=spec.kind.value, template=template,
    )
