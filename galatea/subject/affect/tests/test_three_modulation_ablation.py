"""三类因果调制消融——选择性（L05 §7 modulation causality：C2 硬条件）。

本单元覆盖 SENSORIUM_gain / PERCEPTION_believe_threshold 两面（真实接收面 +
发放门 + 消融）；WORKSPACE_salience 消费面 = L07 C2 次单元（发放面在本单元
测试：门控 + 有界 + 台账——consumption 在 issue 侧已留接口）。
选择性断言：① 增益调制只动 sensorium 面（阈值不动）；② 阈值调制只动 perception
面（增益不动）；③ 消融（enabled=∅）→ 两面全部不受情感状态影响。
"""
import pytest

from galatea.subject.affect.ports import AffectCycleInputs
from galatea.subject.affect.pipeline import AffectPipeline
from galatea.subject.c2profile import C2AffectParams
from galatea.subject.perception.pipeline import PerceptionPipeline
from galatea.subject.sensorium.gain import apply_gain_c2


def _drive_arousal(pipe: AffectPipeline, cycles: int) -> None:
    """深耗能协议：energy → 0.3（e_max = 0.7 → arousal 过迟滞门 0.55）。"""
    for c in range(cycles):
        pipe.step(AffectCycleInputs(cycle=c, body_energy=0.3, body_integrity=1.0))


def test_gain_gate_issues_and_ablation_stops(affect_params: C2AffectParams) -> None:
    """① 增益门：arousal 过门 → gain 调制发放；消融 → 零发放（且其他类不发放）。"""
    pipe = AffectPipeline(affect_params)
    _drive_arousal(pipe, 16)
    assert pipe.step(AffectCycleInputs(cycle=16, body_energy=0.3, body_integrity=1.0)
                     ).step.gate_gain_on is True
    # 消融：全关 → 无任何发放
    ablated = AffectPipeline(affect_params, modulation_enabled=frozenset())
    _drive_arousal(ablated, 16)
    out16 = ablated.step(AffectCycleInputs(cycle=16, body_energy=0.3, body_integrity=1.0))
    assert out16.modulations == ()
    assert ablated.ledger.confirmed_fields(16) == ()


def test_gain_modulation_selective_for_sensorium(affect_params: C2AffectParams) -> None:
    """增益调制 → sensorium 面 applied=2.0 回执在案；perception 阈值不受影响。"""
    pipe = AffectPipeline(affect_params)
    _drive_arousal(pipe, 17)
    gain_fields = [f for f in pipe.ledger._fields.values() if f.dimension == "gain"]
    assert gain_fields, "arousal 过门后必须有增益调制发放"
    state, receipt = apply_gain_c2("sf.TEST.0", gain_fields[-1].requested_value)
    assert state.applied_factor == 2.0 and receipt.bound_check == "IN_BOUND"
    # 选择性：无 uncertainty 驱动 → perception 阈值调制零发放
    threshold_fields = [f for f in pipe.ledger._fields.values()
                        if f.dimension == "believe_threshold"]
    assert threshold_fields == []


def test_threshold_gate_and_perception_face(affect_params: C2AffectParams) -> None:
    """② 阈值门：uncertainty 过门 → believe_threshold=0.6 发放；接收面生效 + 归零恢复。"""
    pipe = AffectPipeline(affect_params)
    for c in range(16):
        pipe.step(AffectCycleInputs(cycle=c, body_energy=1.0, body_integrity=1.0,
                                    belief_uncertainty_mean=0.7))
    out = pipe.step(AffectCycleInputs(cycle=16, body_energy=1.0, body_integrity=1.0,
                                      belief_uncertainty_mean=0.7))
    assert out.step.gate_threshold_on is True
    fields = [f for f in out.modulations if f.dimension == "believe_threshold"]
    assert fields and fields[0].requested_value == 0.6
    # 真实接收面：override 生效 → abstain 判定随阈值上移；clear → 恢复冻结 0.5
    perc = PerceptionPipeline()
    base = perc._effective_params().believe_threshold
    assert base == 0.5
    receipt = perc.apply_threshold_modulation(fields[0].requested_value)
    assert receipt.accepted and perc._effective_params().believe_threshold == 0.6
    from galatea.subject.perception.ood import OodAssessment
    from galatea.subject.perception.ood import should_abstain
    ood = OodAssessment(ood_flag=False, ood_score=0.0, reasons=(), evidence_refs=())
    assert should_abstain(0.55, perc._effective_params(), ood) is True    # 0.55 < 0.6
    perc.clear_threshold_modulation()
    assert should_abstain(0.55, perc._effective_params(), ood) is False   # 0.55 ≥ 0.5
    # 选择性：uncertainty 驱动不触发增益门（arousal 未过门）
    assert out.step.gate_gain_on is False


def test_salience_gate_issues_bounded(affect_params: C2AffectParams) -> None:
    """③ 显著性发放面：novelty 过门 → salience.affect=2.0 有界发放（消费面 = L07 次单元）。"""
    pipe = AffectPipeline(affect_params)
    for c in range(16):
        pipe.step(AffectCycleInputs(cycle=c, body_energy=1.0, body_integrity=1.0,
                                    sensory_residual_mean=0.8))
    out = pipe.step(AffectCycleInputs(cycle=16, body_energy=1.0, body_integrity=1.0,
                                      sensory_residual_mean=0.8))
    assert out.step.gate_salience_on is True
    fields = [f for f in out.modulations if f.dimension == "salience.affect"]
    assert fields and fields[0].requested_value == 2.0
    assert fields[0].target.value == "WORKSPACE"
    # 选择性：novelty 驱动不触发增益/阈值门
    assert out.step.gate_gain_on is False and out.step.gate_threshold_on is False


def test_gain_does_not_change_formation(affect_params: C2AffectParams) -> None:
    """形成义务无条件：增益只缩放特征，不改变是否形成（L02 §8 不变量 6）——
    sensorium 形成管线消费 apply_gain(frame, None) 恒等路径不受调制存在与否影响。"""
    from galatea.subject.sensorium.gain import apply_gain

    _, receipt = apply_gain("sf.X.0", None)
    assert receipt.bound_check == "IDENTITY_C0" and receipt.applied_gain == 1.0
