"""R-OTHERINFER：他者模型推断（L12 §4.1/§4.5 / §10 other.py；REPLAY_LLM；Q-L12-04）。

D-14 单主体期封锁（Q-L12-04②）：OtherModel 对象面 = 实验控制通道（typed）——
Q-L01-07 裁定不引入第二代理，个体他者无承载；intent_hypothesis 默认
Unknown(CAPABILITY_LIMIT)，仅显式 typed 请求可获得的陈述性内容可填具体值；
**禁确定性心智主张**（输出恒带 Unknown——构造面强制）；禁写 OwnedGoal/仲裁
向量/连续性主张证据（社会认知 ≠ 执行权限）。
"""
import json
from dataclasses import dataclass
from typing import Any, cast

from galatea.kernel.unknown import Unknown, UnknownReason
from galatea.subject.language.ports import LanguagePlaneViolation
from galatea.subject.language.replay import ReplayStore
from galatea.subject.language.roles import RoleKind, get_role

__all__ = ["OtherModelState", "OtherModel", "infer_other_model"]

_FIELDS = ("existence", "intent_hypothesis", "knowledge_estimate", "commitment_estimate")


class OtherModelState:
    """三态字段值（VALUE | UNKNOWN | ABSENT——Q-L12-04① typed 三态）。"""

    def __init__(
        self, name: str,
        value: str | float | None = None,
        unknown: Unknown | None = None,
        absent: bool = False,
    ) -> None:
        provided = sum(1 for v in (value is not None, unknown is not None, absent) if v)
        if provided != 1:
            raise LanguagePlaneViolation(
                f"OtherModelState({name}) requires exactly one of value|unknown|absent（三态互斥）"
            )
        self.name = name
        self.value = value
        self.unknown = unknown
        self.absent = absent

    def describe(self) -> str:
        if self.unknown is not None:
            return f"Unknown({self.unknown.reason.value})"
        if self.absent:
            return "ABSENT"
        return repr(self.value)


@dataclass(frozen=True, slots=True)
class OtherModel:
    """他者模型（L12 §2.2 lang.other_model；恒带 Unknown——禁确定性心智主张）。"""

    fields: tuple[OtherModelState, ...]
    cue_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        names = tuple(f.name for f in self.fields)
        if sorted(names) != sorted(_FIELDS):
            raise LanguagePlaneViolation(f"OtherModel fields mismatch（Q-L12-04①四字段）: {names!r}")
        if not self.cue_refs:
            raise LanguagePlaneViolation("OtherModel requires cue_refs（推断须有可见线索留证）")
        concrete = [f.name for f in self.fields if f.unknown is None and not f.absent]
        if len(concrete) == len(_FIELDS):
            raise LanguagePlaneViolation(
                "deterministic mind claim forbidden（全字段具体值 = 确定性心智主张——"
                "R-OTHERINFER 输出恒带 Unknown，Q-L12-04①）"
            )


def infer_other_model(
    cue_texts: tuple[str, ...], cue_refs: tuple[str, ...], replay: ReplayStore,
    *, typed_request_content: bool = False,
) -> OtherModel:
    """R-OTHERINFER 调用（推断 = 录制回放；封锁面 = 构造级机械强制）。

    回放输出合同（录制会话冻结）：{"existence": "present|absent|unknown",
    "intent_hypothesis": str|"unknown", "knowledge_estimate": float|"unknown",
    "commitment_estimate": float|"unknown"}——"unknown" → Unknown(CAPABILITY_LIMIT)
    默认（Q-L12-04②b）；intent_hypothesis 具体值仅当 typed_request_content=True
    （显式 typed 请求可获得的陈述性内容），否则构造即拒。
    """
    spec = get_role(RoleKind.R_OTHERINFER)
    payload = {"cues": list(cue_texts)}
    entry = replay.invoke(spec.kind.value, payload)
    try:
        out = cast(dict[str, Any], json.loads(entry.output_text))
    except (json.JSONDecodeError, TypeError) as exc:
        raise LanguagePlaneViolation(f"R-OTHERINFER output schema violation: {exc}") from exc

    def _state(name: str) -> OtherModelState:
        raw = out.get(name, "unknown")
        if raw == "unknown" or raw is None:
            return OtherModelState(name, unknown=Unknown(
                reason=UnknownReason.CAPABILITY_LIMIT, evidence_refs=cue_refs,
                detail=f"OtherModel.{name} not determinable in D-14 period（Q-L12-04②）",
                detected_by="language.other", virtual_time=0,
            ))
        if name == "intent_hypothesis" and not typed_request_content:
            raise LanguagePlaneViolation(
                "intent_hypothesis concrete value requires typed_request_content"
                "（仅显式 typed 请求内容可填——Q-L12-04②b）"
            )
        return OtherModelState(name, value=str(raw) if isinstance(raw, str) else float(raw))

    return OtherModel(fields=tuple(_state(n) for n in _FIELDS), cue_refs=cue_refs)
