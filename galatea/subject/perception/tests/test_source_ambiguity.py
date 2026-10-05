"""来源判断测试（L03 §7：来源不可判 → AMBIGUOUS/UNKNOWN；禁默认归因）。"""
import pytest

from galatea.subject.perception.pipeline import PerceptionPipeline
from galatea.subject.perception.source import SourceKind, judge_frame_source
from galatea.subject.perception.tests.conftest import frames_at, uniform_window


@pytest.fixture()
def sources():
    frames = frames_at(uniform_window(0.9), 7, events=["integrity_damage_event"])
    pipeline = PerceptionPipeline()
    out = pipeline.process_window(7, frames)
    return out.sources, {f.modality.value: f for f in frames}


def test_body_carriers_attributed_self(sources):
    """INTERO/PROPRIO（身体载体）→ SELF（载体合同证据，非默认归因）。"""
    judged, by_modality = sources
    for modality in ("INTERO", "PROPRIO"):
        match = next(s for s in judged if s.evidence_refs == (by_modality[modality].frame_id,))
        assert match.kind is SourceKind.SELF
        assert by_modality[modality].frame_id in match.evidence_refs


def test_ext_event_carrier_ambiguous(sources):
    """EXT_EVENT（外感受载体渲染身体事件）→ AMBIGUOUS（MW0 冻结歧义面）。"""
    judged, by_modality = sources
    assert "EXT_EVENT" in by_modality, "事件流应产生 EXT_EVENT 帧"
    match = next(s for s in judged if s.evidence_refs == (by_modality["EXT_EVENT"].frame_id,))
    assert match.kind is SourceKind.AMBIGUOUS


def test_window_content_unknown_source(sources):
    """窗内容自产/外产归因 = UNKNOWN（efference 闭环归 C4，禁 C1 伪装归因）。"""
    judged, by_modality = sources
    match = next(s for s in judged if s.evidence_refs == (by_modality["EXT_LOCAL_OBS"].frame_id,))
    assert match.kind is SourceKind.UNKNOWN


def test_no_default_external_attribution(sources):
    """禁默认 EXTERNAL：任何 judgement 均有 basis 证据说明。"""
    judged, _ = sources
    for s in judged:
        assert s.basis
        assert s.kind is not SourceKind.EXTERNAL or s.evidence_refs


def test_source_ablation_detectable():
    """消融检出面：来源判断层整体缺席 → 判定集为空（可检，非静默）。"""
    frames = frames_at(uniform_window(0.9), 7)
    pipeline = PerceptionPipeline()
    out = pipeline.process_window(7, frames)
    assert len(out.sources) == len(frames)          # 有帧即有判定
    assert all(s.kind is not None for s in out.sources)
