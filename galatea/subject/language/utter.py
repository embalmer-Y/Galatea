"""Utterance 渲染与 R-TRANSLATE（L12 §4.4 输出面 / §10 utter.py；REPLAY_LLM）。

输出必须**引用**内部状态/证据（cited_evidence）；不能引用的量化主张被拒
（UncitedClaimRejected——文本含数字 token 而 cited_evidence 为空，机械规则）。
出边界经 L01 Language 通道（装配层投递，subject 面零 env import——平面纪律）。
"""
import json
import re
from dataclasses import dataclass
from typing import Any, cast

from galatea.subject.language.ports import LanguagePlaneViolation
from galatea.subject.language.replay import ReplayStore
from galatea.subject.language.roles import RoleKind, get_role

__all__ = ["Utterance", "UncitedClaimRejected", "translate_utterance"]

_NUMERIC_TOKEN = re.compile(r"\d+(?:\.\d+)?")


class UncitedClaimRejected(LanguagePlaneViolation):
    """无引用的量化主张（L12 §4.4：cannot 引用 = 拒，防幻觉入规范链）。"""


@dataclass(frozen=True, slots=True)
class Utterance:
    """出边界话语（模板受限 + 引用强制；层级行 = EXTERNAL_STATEMENT 面）。"""

    text: str
    cited_evidence: tuple[str, ...]
    role: str
    template: str | None = None      # R-CLARIFY/R-SEEKHELP 模板受限枚举名

    def __post_init__(self) -> None:
        if not self.text:
            raise ValueError("Utterance requires text")
        if _NUMERIC_TOKEN.search(self.text) and not self.cited_evidence:
            raise UncitedClaimRejected(
                f"utterance contains a quantitative claim without cited evidence: {self.text!r}"
                "（L12 §4.4 UncitedClaimRejected）"
            )
        if not self.role:
            raise ValueError("Utterance requires role")


def translate_utterance(
    structured: dict[str, str], cited_evidence: tuple[str, ...], replay: ReplayStore
) -> Utterance:
    """R-TRANSLATE 调用（受限保留：must_cite_evidence=true + 输出引用式——Q-L12-01②）。

    回放输出合同：{"utterance": str, "template": str|null}；cited_evidence 为空时
    产出即拒（require_evidence_citation 角色的构造面强制）。
    """
    spec = get_role(RoleKind.R_TRANSLATE)
    if not cited_evidence:
        raise UncitedClaimRejected("R-TRANSLATE requires cited_evidence（must_cite_evidence=true）")
    payload = {"structured": json.dumps(structured, sort_keys=True)}
    entry = replay.invoke(spec.kind.value, payload)
    try:
        out = cast(dict[str, Any], json.loads(entry.output_text))
        text = str(out["utterance"])
        template = out.get("template")
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise LanguagePlaneViolation(f"R-TRANSLATE output schema violation: {exc}") from exc
    return Utterance(
        text=text, cited_evidence=cited_evidence, role=spec.kind.value,
        template=str(template) if template is not None else None,
    )
