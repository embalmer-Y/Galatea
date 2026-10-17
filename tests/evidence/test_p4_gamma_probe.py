"""P4-γ 冻结前可行性探针（硬机制第九次）——永久回归测试。

复用 runs_p4gamma 核心（规格 ADR-G-0035 §2）：动作条件化 RSSM（input_dim=4）训练
一次，复用承载三断言面——① EFE-MPC 双跑 bit-exact + 对脚本基线优势（确定性种子）；
② 生成式重放睡眠增益（forget_a > forget_b ∧ 重放臂不退化）；③ 在线双域门合同面。
判据 = p4_gamma_mind.profile v1.0（探针冻结）；完整 8/16 种子扫描属正式 claim 运行
（stat plan p4_gamma_mind v1.0），本回归断言确定性种子子集的判据方向。
"""
import statistics

import os

import pytest
import yaml

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

from galatea.evidence.control.runs_p4gamma import (  # noqa: E402
    collect_conditioned,
    dream_samples,
    heldout_mse,
    run_episode,
    seed_for,
    to_tensors,
    train_conditioned,
)
from galatea.subject.brain.module import configure_deterministic_torch  # noqa: E402

configure_deterministic_torch()


def _repo():
    from pathlib import Path
    return Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def trained_model():
    rows = collect_conditioned(seed_for("p4.gamma|train"), cycles=256)
    assert {a for _, a in rows} == {0, 1, 2}, "脚本必须覆盖三动作（条件化前提）"
    xs = to_tensors(rows)
    return train_conditioned(xs[: len(xs) - 31], 300)


def test_mpc_double_run_bit_exact_and_advantage(trained_model) -> None:
    """EFE-MPC 规划确定性 + 对脚本基线优势（确定性种子子集——判据方向）。"""
    seed0 = seed_for("p4.gamma|world|0")
    r1 = run_episode(seed0, trained_model, mode="mpc")
    r2 = run_episode(seed0, trained_model, mode="mpc")
    assert r1["plans"] == r2["plans"] and r1["mean_energy"] == r2["mean_energy"]
    pairs = []
    for i in (0, 1):
        seed = seed_for(f"p4.gamma|world|{i}")
        pairs.append((run_episode(seed, trained_model, mode="mpc")["mean_energy"],
                      run_episode(seed, trained_model, mode="script")["mean_energy"]))
    advantage = (statistics.mean(a for a, _ in pairs)
                 - statistics.mean(b for _, b in pairs))
    assert advantage > 0, f"MPC 配对优势为负（探针前提破坏）：{advantage:+.4f}"


def test_dream_replay_sleep_gain(trained_model) -> None:
    """生成式重放睡眠增益：forget_a > forget_b ∧ forget_b ≤ 0.1×|pre|（冻结判据）。"""
    rows1 = collect_conditioned(seed_for("p4.gamma|phase1"), cycles=256)
    rows2 = collect_conditioned(seed_for("p4.gamma|phase2"), cycles=256)
    xs1, xs2 = to_tensors(rows1), to_tensors(rows2)
    half1, half2 = len(xs1) // 2, len(xs2) // 2

    model_p1 = train_conditioned(xs1[: half1 + 1], 300)
    pre = heldout_mse(model_p1, xs1[half1:])

    model_a = _finetune_from(model_p1, xs2[: half2 + 1])
    forget_a = heldout_mse(model_a, xs1[half1:]) - pre
    dream = dream_samples(model_p1, xs1[: half1 + 1], steps=600)
    model_b = _finetune_from(model_p1, xs2[: half2 + 1] + dream)
    forget_b = heldout_mse(model_b, xs1[half1:]) - pre
    assert forget_a > forget_b, f"重放未减少遗忘（探针前提破坏）：a={forget_a:+.6f} b={forget_b:+.6f}"
    assert forget_b <= 0.1 * abs(pre), f"重放臂退化超容差：forget_b={forget_b:+.6f} pre={pre:.6f}"


def _finetune_from(parent, mix):
    """在线学习语义：从父权重起步微调（Q-L11-09①——非重训）。"""
    from galatea.subject.brain.world_model import RSSMWorldModel
    from galatea.subject.p4profile import load_p4_alpha_profile
    params = load_p4_alpha_profile(_repo() / "config/profiles/p4_alpha_brain.profile.yaml")
    m = RSSMWorldModel(params, parent_digest="root", init_seed=params.init_seed, input_dim=4)
    m.load_state(parent.state_dict())
    m.train_on_sequence(mix, lr=params.lr, epochs=100, target_dims=(0,))
    return m


def test_online_gate_contract_surface() -> None:
    """在线双域门合同面（profile 冻结承载——判别计算属 claim 运行）。"""
    doc = yaml.safe_load(
        (_repo() / "config/profiles/p4_gamma_mind.profile.yaml").read_text(encoding="utf-8"))
    assert doc["online_learning"]["gate"] == "dual_domain_no_regression"
    assert doc["online_learning"]["ewc_lambda"] == 0.0
    assert doc["profile"]["ruling_refs"][0] == "Q-L04-16"
    assert doc["probe_anchors"]["probe_verdict"] == "PASS"
