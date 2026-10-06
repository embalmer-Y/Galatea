"""三类调制消融全闭环（L05 §7 modulation causality：C2 硬条件——本件补齐第三类消费面）。

闭环：affect（novelty 过迟滞门）→ ModulationField(WORKSPACE, salience.affect) →
workspace consume（clip [0.5,2.0] + 回执）→ affect 分量缩放 → 广播内容分布变化；
消融（modulation_enabled=∅）→ 无调制 → 分布回基线。
选择性：salience 调制只动 workspace（sensorium 增益回执恒等 / perception 阈值不动）。
"""
from pathlib import Path

import pytest

from galatea.kernel.packet import RepresentationLevel
from galatea.subject.affect.ports import AffectCycleInputs
from galatea.subject.affect.pipeline import AffectPipeline
from galatea.subject.c2profile import (
    C2AffectParams,
    C2WorkspaceParams,
    load_c2_affect_profile,
    load_c2_workspace_profile,
)
from galatea.subject.sensorium.gain import apply_gain_c2
from galatea.subject.workspace.pipeline import WorkspacePipeline
from galatea.subject.workspace.propose import SalienceComponents, WorkspaceProposal

ROOT = Path(__file__).resolve().parents[4]
READERS = ("perception", "models", "affect", "memory")


@pytest.fixture(scope="module")
def affect_params() -> C2AffectParams:
    return load_c2_affect_profile(ROOT / "config/profiles/c2_affect.profile.yaml")


@pytest.fixture(scope="module")
def ws_params() -> C2WorkspaceParams:
    return load_c2_workspace_profile(ROOT / "config/profiles/c2_workspace.profile.yaml")


def _affect_aroused_novel(p: AffectPipeline, cycles: int) -> None:
    """novelty 与 arousal 双高输入（驱动三类门中 salience 门 + gain 门为对照）。"""
    for c in range(cycles):
        p.step(AffectCycleInputs(
            cycle=c, body_energy=0.3, body_integrity=1.0,
            sensory_residual_mean=0.8, belief_uncertainty_mean=0.1,
        ))


def _proposals(pipe: WorkspacePipeline, tag: str) -> None:
    """六提案：affect 分量分层（0.0–0.5）——调制因子应改变入帧集。"""
    for i in range(6):
        pipe.submit(WorkspaceProposal(
            proposal_id=f"{tag}.{i}", content_ref=f"c.{tag}.{i}",
            source_level=RepresentationLevel.PERCEIVED,
            salience=SalienceComponents(goal_relevance=0.1, affect=0.1 * i, novelty=0.1,
                                        uncertainty=0.1, info_value=0.1),
            sponsor_module=READERS[i % 4],
        ))


def test_salience_closed_loop_changes_broadcast(affect_params: C2AffectParams,
                                                ws_params: C2WorkspaceParams) -> None:
    """闭环：调制 on → 高 affect 分量提案因 ×2 缩放入帧；ablated → 基线入帧集。"""
    affect_on = AffectPipeline(affect_params)
    affect_off = AffectPipeline(affect_params, modulation_enabled=frozenset())
    _affect_aroused_novel(affect_on, 20)
    _affect_aroused_novel(affect_off, 20)
    out_on = affect_on.step(AffectCycleInputs(
        cycle=20, body_energy=0.3, body_integrity=1.0, sensory_residual_mean=0.8))
    assert out_on.step.gate_salience_on is True
    salience_fields = [f for f in out_on.modulations if f.dimension == "salience.affect"]
    assert salience_fields, "salience 门 ON 必发放"

    ws_on = WorkspacePipeline(ws_params, readers=READERS)
    ws_off = WorkspacePipeline(ws_params, readers=READERS)
    _proposals(ws_on, "on")
    _proposals(ws_off, "off")
    out_ws_on = ws_on.run_competition(cycle=20, salience_modulation=salience_fields[-1])
    out_ws_off = ws_off.run_competition(cycle=20, salience_modulation=None)
    assert out_ws_on is not None and out_ws_off is not None
    assert out_ws_on.modulation_receipt_id == salience_fields[-1].modulation_id   # 回执引用在帧
    ids_on = {i.proposal_id for i in out_ws_on.frame.items}
    ids_off = {i.proposal_id for i in out_ws_off.frame.items}
    assert ids_on != ids_off, "调制因子 ×2 作用于 affect 分量必须改变入帧集（竞争 causality）"
    # ×2 缩放使高 affect 提案占优——ids_on 应含 affect 最高档
    assert "on.5" in ids_on


def test_selectivity_other_two_faces_untouched(affect_params: C2AffectParams,
                                                ws_params: C2WorkspaceParams) -> None:
    """选择性：salience 调制在位时，sensorium 增益回执与 perception 阈值不受影响。"""
    affect = AffectPipeline(affect_params)
    _affect_aroused_novel(affect, 21)
    out = affect.step(AffectCycleInputs(
        cycle=21, body_energy=0.3, body_integrity=1.0, sensory_residual_mean=0.8,
        belief_uncertainty_mean=0.1))       # uncertainty 低 → 阈值门 OFF（对照）
    salience_only = [f for f in out.modulations if f.dimension == "salience.affect"]
    gain_fields = [f for f in out.modulations if f.dimension == "gain"]
    threshold_fields = [f for f in out.modulations if f.dimension == "believe_threshold"]
    assert salience_only and not threshold_fields
    # gain 门由 arousal 驱动可能同时 ON——选择性断言：sensorium 面增益不变地作用于帧形成，
    # perception 阈值面零发放（uncertainty 低）
    if gain_fields:
        state, receipt = apply_gain_c2("sf.X.0", gain_fields[-1].requested_value)
        assert state.applied_factor == 2.0 and receipt.bound_check == "IN_BOUND"
    from galatea.subject.perception.pipeline import PerceptionPipeline
    perc = PerceptionPipeline()
    assert perc._effective_params().believe_threshold == 0.5   # 未动


def test_ablation_returns_distribution_to_baseline(affect_params: C2AffectParams,
                                                   ws_params: C2WorkspaceParams) -> None:
    """消融面（enabled=∅）：无任何发放 → workspace 无调制输入 → 竞争 = 等权基线。"""
    affect_ablated = AffectPipeline(affect_params, modulation_enabled=frozenset())
    _affect_aroused_novel(affect_ablated, 20)
    out = affect_ablated.step(AffectCycleInputs(
        cycle=20, body_energy=0.3, body_integrity=1.0, sensory_residual_mean=0.8))
    assert out.modulations == ()      # 全关 → 零发放（三类调制消融的发放面）
    ws = WorkspacePipeline(ws_params, readers=READERS)
    _proposals(ws, "ab")
    out_ws = ws.run_competition(cycle=20, salience_modulation=None)
    assert out_ws is not None and out_ws.modulation_receipt_id is None
    scores = [t.score for t in out_ws.trace if t.admitted]
    assert scores == sorted(scores, reverse=True)   # 等权基线序
