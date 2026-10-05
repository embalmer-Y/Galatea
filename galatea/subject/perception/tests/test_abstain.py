"""abstain 与 OOD abstain 面测试（L03 §4.4/§7：abstain 一等输出；OOD → abstain）。"""
import pytest

from galatea.subject.perception.pipeline import PerceptionPipeline, UnauthorizedInput
from galatea.subject.perception.tests.conftest import frames_at, uniform_window


@pytest.fixture()
def pipeline():
    return PerceptionPipeline()


def test_low_evidence_abstains(pipeline):
    """全零窗：top posterior ≈ 0 < believe_threshold=0.5 → abstain + FIELD 低承诺。"""
    frames = frames_at(uniform_window(0.0), 7)
    out = pipeline.process_window(7, frames)
    assert len(out.abstains) == 1
    assert out.abstains[0].reason.reason.value == "INSUFFICIENT_OBSERVATION"
    assert not out.objects
    field = [b for b in out.beliefs if b.kind.value == "FIELD"]
    assert len(field) == 1


def test_ood_value_abstains(pipeline):
    """窗值越 [0,1] → OOD abstain（事件级域出），无对象信念，unknown 留痕。"""
    window = uniform_window(0.9)
    window[0][0] = 1.5
    out = pipeline.process_window(7, frames_at(window, 7))
    assert len(out.abstains) == 1
    assert out.abstains[0].reason.reason.value == "OOD"
    assert not out.objects
    assert any(u.reason.value == "OOD" for u in out.unknowns)


def test_ood_event_kind_abstains(pipeline):
    """事件种越冻结枚举 → OOD（Q-L01-08 M0 事件集域）。"""
    out = pipeline.process_window(7, frames_at(uniform_window(0.0), 7, events=["alien_event"]))
    assert out.abstains and out.abstains[0].reason.reason.value == "OOD"


def test_ood_orientation_abstains(pipeline):
    """朝向越冻结 token 域 → OOD。"""
    out = pipeline.process_window(7, frames_at(uniform_window(0.0), 7, orientation="X"))
    assert out.abstains and out.abstains[0].reason.reason.value == "OOD"


def test_strong_evidence_no_abstain(pipeline):
    """强观测：中心 0.9@d0 → 对象信念 + 无 abstain（后验 ≈1 ≥ 0.5）。"""
    out = pipeline.process_window(7, frames_at(uniform_window(0.9), 7))
    assert not out.abstains
    assert len(out.objects) == 1
    assert out.objects[0].cell == (0, 0)


def test_abstain_recomputable(pipeline):
    """abstain 可复算：candidates_considered + threshold_ref 完整留存（L03 §4.4）。"""
    out = pipeline.process_window(7, frames_at(uniform_window(0.0), 7))
    event = out.abstains[0]
    assert "believe_threshold=0.5" in event.threshold_ref
    assert event.candidates_considered


def test_non_formed_input_rejected_s0(pipeline):
    """非 SENSORY_FORMED 输入 = UnauthorizedInput（S0 面，L03 §6 行 8）。"""
    from types import SimpleNamespace

    fake = SimpleNamespace(
        frame_id="fake.1", representation_level=SimpleNamespace(value="RECEIVED"),
        modality=SimpleNamespace(value="EXT_LOCAL_OBS"), features=None,
    )
    with pytest.raises(UnauthorizedInput):
        pipeline.process_window(7, (fake,))
