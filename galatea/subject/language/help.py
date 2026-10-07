"""R-SEEKHELP 求助语句（L12 §4.1 / §10 help.py；REPLAY_LLM；Q-L12-08 权限面）。

求助链：L09 SEEK_HELP（元决策）→ R-SEEKHELP → Utterance 全链回放可复现
（Q-L12-08③）。求助 = 一等能力非失败（L09 §4.3）；频次帽 1/64 由 metacontrol
承载（Q-L09-07③——本模块不重复计数）；经 gateway 记录留痕由装配层执行
（观察类动作不耗动作预算）；MW0 containment = 仅实验者可见、无网络（负清单）。
"""
import json
from typing import Any, cast

from galatea.subject.language.ports import LanguagePlaneViolation
from galatea.subject.language.replay import ReplayStore
from galatea.subject.language.roles import RoleKind, get_role
from galatea.subject.language.utter import Utterance

__all__ = ["HELP_TEMPLATES", "seek_help_utterance"]

HELP_TEMPLATES: tuple[str, ...] = (
    "HELP_CAPABILITY_BOUNDARY",
    "HELP_LOSS_OF_CONTROL",
)


def seek_help_utterance(
    context_summary: str, template: str, cited_evidence: tuple[str, ...], replay: ReplayStore
) -> Utterance:
    """R-SEEKHELP 调用（求助内容 cited_evidence 强制——无引用即拒，L12 §4.4）。"""
    spec = get_role(RoleKind.R_SEEKHELP)
    if not cited_evidence:
        raise LanguagePlaneViolation("R-SEEKHELP requires cited_evidence（求助内容无引用即拒）")
    if template not in HELP_TEMPLATES:
        raise LanguagePlaneViolation(
            f"help template {template!r} not in frozen enum {HELP_TEMPLATES}（模板受限）"
        )
    payload = {"context": context_summary, "template": template}
    entry = replay.invoke(spec.kind.value, payload)
    try:
        out = cast(dict[str, Any], json.loads(entry.output_text))
        text = str(out["utterance"])
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise LanguagePlaneViolation(f"R-SEEKHELP output schema violation: {exc}") from exc
    return Utterance(
        text=text, cited_evidence=cited_evidence, role=spec.kind.value, template=template,
    )
