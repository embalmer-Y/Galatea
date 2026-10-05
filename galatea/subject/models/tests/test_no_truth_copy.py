"""禁真值拷贝测试（L04 §7 leakage 行 + Q-L04-09/Q-L04-10；oracle 泄漏主防线）。"""
import pytest

from pathlib import Path

from galatea.subject.models.tests.conftest import profile, world_with_observation


def test_world_model_imports_no_env_module():
    """转移模型不是环境真值拷贝（L04 §8 不变量 6）：import 图零 env 依赖。"""
    models_dir = Path(__file__).resolve().parents[1]
    for path in sorted(models_dir.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        assert "galatea.env" not in source, f"{path.name} imports env（真值拷贝面）"


def test_transition_semantics_is_persistence_not_simulation():
    """C1 转移语义 = 持续性（Q-L04-09）：无观测批 → 占据图逐位不变（不模拟
    respawn/风暴/漂移——信念不因隐藏过程改变）。"""
    prof, model, belief, _ = world_with_observation(7, 0.9)
    before = belief.digest()
    after_belief = model.update(11, (), move_receipts=(), forage_receipts=(), requested_moves=())
    occupied_before = dict(belief.occupancy)
    occupied_after = dict(after_belief.occupancy)
    assert set(occupied_before) == set(occupied_after)
    for cell, b in occupied_before.items():
        assert occupied_after[cell] == b     # 无事件 → 无变化（禁隐藏过程模拟）
    assert before != after_belief.digest()   # t_eff/unknowns 推进（ belief 版本化）


def test_transition_version_declared():
    """转移语义版本化（L04 §4.1；Q-L04-09 成文身份）。"""
    _, _, belief, _ = world_with_observation(7, 0.9)
    assert "persistence" in belief.transition_model_version
    assert "Q-L04-09" in belief.transition_model_version


def test_no_respawn_or_storm_constants_in_world_model():
    """无源常量防线（REV-0013 R4）：世界模型无世界侧参数标识/数值（禁从世界
    profile 反推——适应表零计数起步，Q-L04-10）。"""
    world_source = Path(__file__).resolve().parents[1].joinpath("world.py").read_text(encoding="utf-8")
    for banned in (
        "respawn_multiplier", "storm_rate_per_cycle", "storm_band_drift",
        "resource_density", "0.005", "0.030", "min_dwell",
    ):
        assert banned not in world_source, f"world.py contains world-truth constant: {banned}"


def test_prediction_prior_source_declared():
    """窗预测的未观测格 = 声明先验 × g(d)（值空间；Q-L04-11 声明来源，非真值）。"""
    from galatea.subject.models.prediction import predict_window
    from galatea.subject.models.world import WorldModel

    prof = profile()
    fresh = WorldModel(prof, run_id="R")
    belief = fresh.update(0, (), (), (), requested_moves=())
    preds = predict_window(belief, prof, 1)
    assert len(preds) == 1
    window = preds[0].expected_window
    assert window is not None
    assert len(window) == 5 and all(len(r) == 5 for r in window)
    prior = prof.perception.prior_resource_density
    gain = prof.perception.gain_by_distance
    # 零观测世界：值 = 先验 × g(d)（d2 角 = 0.35×0.2 = 0.07；d0 中心 = 0.35）
    assert window[0][0] == pytest.approx(prior * gain["d2"])
    assert window[2][2] == pytest.approx(prior * gain["d0"])
    assert window[0][2] == pytest.approx(prior * gain["d2"])   # (0,-2): d = max(0,2) = 2


def test_unreadable_receipt_keeps_predictions_flowning():
    """回执不可读 → 位移合同积分、预测继续发布（Q-L04-09③⁺；Unknown 留痕可审计）。"""
    from galatea.subject.models.prediction import predict_window

    prof, model, _, _ = world_with_observation(7, 0.9)
    belief_gap = model.update(11, (), (), (), requested_moves=("N", "E", "S"))
    assert any("unreadable" in u.detail for u in belief_gap.unknowns)   # 不可读留痕可审计
    assert len(model.pose) == 1                      # 合同积分 → 无分支
    belief = model.update(15, (), (), (), requested_moves=())
    preds = predict_window(belief, prof, 16)
    assert len(preds) == 1                           # 预测流不被中断
