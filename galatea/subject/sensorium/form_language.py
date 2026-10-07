"""语言模态形成算子（L02 §9 C4 + L12 §4.3 唯一合法路径 / form_language.py；C4 新增）。

ReceivedSignal(EXTERNAL_STATEMENT) → SensoryFrame(modality=LANGUAGE)。纯确定性、
无 RNG；同一载荷 → 同帧 digest。LANGUAGE 帧**不入知觉融合**（Q-L12-06① 零后验
权重的形成面承载：帧只供 R-PARSE 消费与验证行为触发）——perception 管线无
LANGUAGE 消费点（结构面，REV-0019 已核）。增益面：语言为分类面，缩放豁免
（帧级 GainState 透传调用方恒等增益）。
"""
from galatea.subject.sensorium.ingest import CARRIER_LANGUAGE, IngestedSignal
from galatea.subject.sensorium.ports import (
    GainState,
    LanguageFeatures,
    QualityMetrics,
    SensoryFrame,
    SensoryModality,
)

__all__ = ["form_language"]


def form_language(
    signal: IngestedSignal, formed_time: int, calibration_version: str, gain: GainState,
    *, revision_of: str | None = None,
) -> SensoryFrame:
    """语言帧形成（载荷合同 = L01 language_stub typed 陈述四字段）。

    level 非 EXTERNAL_STATEMENT 即拒（层级永不提升，L12 §4.1）；text/requester
    空即拒（禁空陈述帧）。
    """
    if signal.carrier != CARRIER_LANGUAGE:
        raise ValueError("form_language requires language carrier")
    payload = signal.payload
    level = str(payload.get("level", ""))
    if level != "EXTERNAL_STATEMENT":
        raise ValueError(
            f"language payload level must be EXTERNAL_STATEMENT, got {level!r}（层级永不提升）"
        )
    text = str(payload.get("text", ""))
    requester = str(payload.get("requester", ""))
    if not text or not requester:
        raise ValueError("language payload requires non-empty text and requester（禁空陈述）")
    features = LanguageFeatures(
        statement_text=text, requester=requester, statement_level=level,
    )
    quality = QualityMetrics(completeness=1.0, corruption_flags=())   # 四字段齐全
    return SensoryFrame(
        frame_id=f"sf.LANG.{signal.effective_time}.{signal.packet.event_id}",
        modality=SensoryModality.LANGUAGE,
        source_received_ids=signal.source_received_ids,
        effective_time=signal.effective_time,
        formed_time=formed_time,
        alignment_offset=formed_time - signal.effective_time,
        alignment_confidence=1.0,
        calibration_version=calibration_version,
        features=features,
        quality=quality,
        gain=gain,
        revision_of=revision_of,
    )
