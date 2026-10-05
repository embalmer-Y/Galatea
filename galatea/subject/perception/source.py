"""来源判断（L03 §4.2/§10 source.py；SELF/EXTERNAL/AMBIGUOUS/UNKNOWN）。

C1 可区分面（L03 §9 C1 行"自我/外部来源可区分"）= 载体级归因：
- INTERO/PROPRIO（身体载体，efference 可用）→ SELF——证据 = 载体身份 + 帧引用
  （构造性证据，非默认归因：载体合同即身体边界）；
- EXT_EVENT（外感受载体渲染身体事件，Q-G00-12①）→ AMBIGUOUS（外通道承载身体
  事件——MW0 冻结设计下的真实歧义面）；
- EXT_LOCAL_OBS 窗内容变化的自产/外产归因 → UNKNOWN（efference 关联归 C4
  EfferenceCopy 闭环，L04 §9 C4 行——禁 C1 伪装归因，L03 §8 不变量 3）。
证据不足恒 AMBIGUOUS/UNKNOWN，禁默认 SELF/EXTERNAL。
"""
from dataclasses import dataclass
from enum import StrEnum

from galatea.subject.sensorium.ports import SensoryModality, SensoryFrame


class SourceKind(StrEnum):
    """来源判断枚举（L03 §2.2）。"""

    SELF = "SELF"
    EXTERNAL = "EXTERNAL"
    AMBIGUOUS = "AMBIGUOUS"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class SourceJudgement:
    """来源判断（L03 §2.2；kind + 证据引用，禁默认归因）。"""

    kind: SourceKind
    evidence_refs: tuple[str, ...]
    basis: str


def judge_frame_source(frame: SensoryFrame) -> SourceJudgement:
    """载体级来源判断（确定性；逐帧——信念级 judgement 由调用方聚合）。"""
    refs = (frame.frame_id,)
    if frame.modality in (SensoryModality.INTERO, SensoryModality.PROPRIO):
        return SourceJudgement(
            kind=SourceKind.SELF,
            evidence_refs=refs,
            basis="body-bound carrier（INTERO/PROPRIO 载体合同 = 身体边界证据）",
        )
    if frame.modality is SensoryModality.EXT_EVENT:
        return SourceJudgement(
            kind=SourceKind.AMBIGUOUS,
            evidence_refs=refs,
            basis="extero carrier renders body events（Q-G00-12①：歧义面，禁默认归因）",
        )
    return SourceJudgement(
        kind=SourceKind.UNKNOWN,
        evidence_refs=refs,
        basis="window content self/external attribution requires efference loop（C4，L04 §9）",
    )
