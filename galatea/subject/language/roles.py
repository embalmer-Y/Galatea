"""typed LLM 角色注册表（L12 §4.1 八角色权威清单 / §10 roles.py；Q-L12-01 全启用）。

实现分型（本单元补裁，随 Q-L12-01/Q-L12-05 裁决语义细化——角色清单/端口/权限面
为冻结核，实现分型不改变任何判据）：
- REPLAY_LLM：开放形语言产出（解析/澄清/求助/规范提取/他者推断/翻译）——输出唯一
  来源 = 录制回放（Q-L12-03：claim-relevant 唯一允许方式；运行时**无在线调用路径**）。
- MECHANICAL：输出完全由 typed 输入决定（R-REPORT = SelfModelView 派生引用机械装配、
  R-CHECKCONSIST = Q-L12-05 两层机械判定——LLM 判定一致性反而引入不可复算面）。
消融判据（Q-L12-07）作用于**角色**禁用，不区分实现分型。
"""
import enum
from dataclasses import dataclass

from galatea.subject.language.ports import LanguageOutPort

__all__ = ["ImplementationKind", "RoleKind", "RoleSpec", "get_role", "roles_enabled"]


class RoleKind(enum.StrEnum):
    """八角色（L12 §4.1 表为权威清单；扩展 = 新 profile 版本，Q-L12-01 重开条件）。"""

    R_PARSE = "R-PARSE"
    R_CLARIFY = "R-CLARIFY"
    R_SEEKHELP = "R-SEEKHELP"
    R_REPORT = "R-REPORT"
    R_NORMEXTRACT = "R-NORMEXTRACT"
    R_OTHERINFER = "R-OTHERINFER"
    R_CHECKCONSIST = "R-CHECKCONSIST"
    R_TRANSLATE = "R-TRANSLATE"


class ImplementationKind(enum.StrEnum):
    """实现分型（REPLAY_LLM = 录制回放承载；MECHANICAL = typed 输入决定论输出）。"""

    REPLAY_LLM = "REPLAY_LLM"
    MECHANICAL = "MECHANICAL"


@dataclass(frozen=True, slots=True)
class RoleSpec:
    """角色规格（输入面/输出端口/引用强制；禁写面由 permission.py 矩阵承载）。"""

    kind: RoleKind
    implementation: ImplementationKind
    out_port: LanguageOutPort
    require_evidence_citation: bool

    def __post_init__(self) -> None:
        if self.kind is RoleKind.R_TRANSLATE and not self.require_evidence_citation:
            raise ValueError("R-TRANSLATE must require evidence citation（Q-L12-01② 受限保留）")


_REGISTRY: dict[str, RoleSpec] = {
    RoleKind.R_PARSE: RoleSpec(
        RoleKind.R_PARSE, ImplementationKind.REPLAY_LLM,
        LanguageOutPort.PARSED_REQUEST, require_evidence_citation=False,
    ),
    RoleKind.R_CLARIFY: RoleSpec(
        RoleKind.R_CLARIFY, ImplementationKind.REPLAY_LLM,
        LanguageOutPort.UTTERANCE, require_evidence_citation=False,
    ),
    RoleKind.R_SEEKHELP: RoleSpec(
        RoleKind.R_SEEKHELP, ImplementationKind.REPLAY_LLM,
        LanguageOutPort.UTTERANCE, require_evidence_citation=True,
    ),
    RoleKind.R_REPORT: RoleSpec(
        RoleKind.R_REPORT, ImplementationKind.MECHANICAL,
        LanguageOutPort.SELF_REPORT, require_evidence_citation=True,
    ),
    RoleKind.R_NORMEXTRACT: RoleSpec(
        RoleKind.R_NORMEXTRACT, ImplementationKind.REPLAY_LLM,
        LanguageOutPort.NORM_SOURCE, require_evidence_citation=True,
    ),
    RoleKind.R_OTHERINFER: RoleSpec(
        RoleKind.R_OTHERINFER, ImplementationKind.REPLAY_LLM,
        LanguageOutPort.OTHER_MODEL, require_evidence_citation=False,
    ),
    RoleKind.R_CHECKCONSIST: RoleSpec(
        RoleKind.R_CHECKCONSIST, ImplementationKind.MECHANICAL,
        LanguageOutPort.INCONSISTENCY, require_evidence_citation=True,
    ),
    RoleKind.R_TRANSLATE: RoleSpec(
        RoleKind.R_TRANSLATE, ImplementationKind.REPLAY_LLM,
        LanguageOutPort.UTTERANCE, require_evidence_citation=True,
    ),
}


def get_role(kind: RoleKind) -> RoleSpec:
    """角色查表（注册表外角色不存在——扩展须新 profile，禁运行时注册）。"""
    try:
        return _REGISTRY[kind]
    except KeyError as exc:
        raise ValueError(f"unknown role: {kind!r}（角色扩展须新 profile 版本）") from exc


def roles_enabled() -> tuple[RoleKind, ...]:
    """启用角色全列（Q-L12-01①：8 角色全启用——消融选择性要求完整角色面）。"""
    return tuple(RoleKind)
