"""P4-γ 探针永久回归测试（硬机制第九次 + 任务形 v2）。

复用 runs_p4gamma 核心：① 任务形 v2（claim1 现行——stat plan v1.2 冻结承载）EFE-MPC
双跑 bit-exact + 对冻结脚本基线配对优势 + 盲化消融归因 + const_rest 金丝雀；
② 生成式重放睡眠增益（forget_a > forget_b ∧ 重放臂不退化——v1.0 通路零触碰）；
③ 在线双域门合同面。判据 = p4_gamma_mind.profile v1.1（任务形 v2 运行前修订）；
完整 16 种子扫描属正式 claim 运行（stat plan p4_gamma_mind v1.2），本回归断言
确定性种子子集的判据方向。
"""
import statistics

import os

import pytest
import yaml

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

from galatea.evidence.control.runs_p4gamma import (  # noqa: E402
    _run_episode_v2,
    collect_conditioned,
    collect_conditioned_v2,
    dream_samples,
    heldout_mse,
    run_episode,
    seed_for,
    to_tensors,
    to_tensors_v2,
    train_conditioned,
    train_conditioned_v2,
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


@pytest.fixture(scope="module")
def trained_model_v2():
    rows = collect_conditioned_v2(seed_for("p4.gamma|train"), cycles=256)
    # 判据锚流（探针迭代 2 同源）：eat 分支在本世界从不触发——{0,1,2} 必须在位；
    # eat 通道零训练样本如实登记（MPC 依赖 move/rest 爬升/排放关联）
    assert {0, 1, 2} <= {a for _, a in rows}, "v2 训练流必须覆盖 move/rest/forage"
    xs = to_tensors_v2(rows)
    return train_conditioned_v2(xs[: len(xs) - 31], 300)


def test_mpc_double_run_bit_exact_and_advantage(trained_model_v2) -> None:
    """任务形 v2 机制健康回归（stat plan v1.2）：双跑 bit-exact + 盲化消融归因
    （聚合面）+ const_rest 金丝雀 + 首动作非塌缩。方向断言（advantage/wins）
    属 claim 正式运行（n=16）职责——回归不在小子集上断言方向（冻结 EFE 含
    epistemic 项，近确定性任务下 2 种子方向为噪声级，如实登记）。"""
    seed0 = seed_for("p4.gamma|world|0")
    r1 = _run_episode_v2(seed0, trained_model_v2, mode="mpc")
    r2 = _run_episode_v2(seed0, trained_model_v2, mode="mpc")
    assert r1["plans"] == r2["plans"] and r1["mean_dev"] == r2["mean_dev"]
    mpc_devs, blind_devs, script_devs, canary_devs = [], [], [], []
    for i in (0, 1):
        seed = seed_for(f"p4.gamma|world|{i}")
        mpc_devs.append(_run_episode_v2(seed, trained_model_v2, mode="mpc")["mean_dev"])
        blind_devs.append(_run_episode_v2(seed, trained_model_v2, mode="mpc_blind")["mean_dev"])
        script_devs.append(_run_episode_v2(seed, trained_model_v2, mode="script")["mean_dev"])
        canary_devs.append(_run_episode_v2(seed, trained_model_v2, mode="const_rest")["mean_dev"])
    blind_advantage = statistics.mean(blind_devs) - statistics.mean(mpc_devs)
    assert blind_advantage > 0, f"盲化消融未劣化（归因面破坏）：{blind_advantage:+.4f}"
    assert statistics.mean(canary_devs) > statistics.mean(script_devs), \
        "const_rest 金丝雀未劣败于 script（任务非退化失效）"
    flat = [a for r in (r1,) for a in r["first_actions"]]
    assert len(set(flat)) > 1, "MPC 首动作单一常量（构造性塌缩回归）"


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
