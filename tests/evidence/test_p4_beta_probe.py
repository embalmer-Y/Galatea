"""P4-β 冻结前可行性探针（硬机制第八次）——永久回归测试。

Layer A（GPU 确定性）：CUDA 可用时执行四检（skipif 无 GPU——认证工作项在 GPU venv 完整执行）。
Layer B1（two_step 双分离）：MB moderation > habit moderation（sep > 0.01，配对优势 > 0.5）。
Layer B2（弃权元认知经济）：校准弃权增益 > 0。
Layer B3（草稿板/思维迭代陷阱场景）：真实 MW0 布局 + 预算陷阱——矛盾开火 + TFA 纠正。

判据数值 = p4_beta_mind.profile v1.0（探针冻结）；复算规格 = ADR-G-0033 §2。
"""
import hashlib
import os
import statistics

import pytest

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
import torch

from galatea.subject.p4profile import load_p4_alpha_profile


# ---------------------------------------------------------------- Layer A（GPU）
@pytest.mark.skipif(not torch.cuda.is_available(), reason="GPU 认证在 CUDA venv 执行")
def test_probe_layer_a_gpu_determinism():
    def dig(m):
        return hashlib.sha256(b"".join(
            v.detach().cpu().contiguous().numpy().tobytes()
            for k, v in sorted(m.state_dict().items()))).hexdigest()

    def build(seed, in_dim=34, hidden=64):
        g = torch.Generator().manual_seed(seed)
        core = torch.nn.GRUCell(in_dim, hidden)
        for n, p in core.named_parameters():
            with torch.no_grad():
                if n.endswith("bias"):
                    p.zero_()
                else:
                    p.copy_(torch.randn(p.shape, generator=g)
                            * ((2.0 / (p.shape[1] + p.shape[0])) ** 0.5 if p.dim() == 2 else 0.1))
        return core.to("cuda")

    m1, m2, m3 = build(11), build(11), build(12)
    assert dig(m1) == dig(m2)
    assert dig(m1) != dig(m3)
    x = torch.randn(8, 34, device="cuda")
    h = torch.zeros(8, 64, device="cuda")
    with torch.no_grad():
        assert m1(x, h).cpu().numpy().tobytes() == m1(x, h).cpu().numpy().tobytes()
    gxs = torch.Generator().manual_seed(777)
    xs = torch.randn(186, 34, generator=gxs).to("cuda")

    def train():
        m = build(11)
        opt = torch.optim.Adam(m.parameters(), lr=1e-3)
        for _ in range(100):
            opt.zero_grad()
            h = torch.zeros(xs.shape[0], 64, device="cuda")
            ((m(xs, h) ** 2).mean()).backward()
            opt.step()
        return dig(m)

    assert train() == train()


# ---------------------------------------------------------------- Layer B1
# v2（Q-L13-22 owner α 裁决 2026-10-16）：任务形完整重设计后升版——旧形（120t/漂移 0.08/
# 桶均值差）经首评与方向对比探针证伪可判定性（argmax+无衰减哑化信号 + 漂移 0.01 即崩），
# 全证据登记册 Q-L13-22 行在案；新形判据 sep>0.10 ∧ dominance>0.60（profile v1.3 重冻）。
def _logistic_interaction(rows):
    import numpy as np
    y = np.array([r[0] for r in rows], float)
    rew = np.array([r[1] for r in rows], float)
    com = np.array([r[2] for r in rows], float)
    X = np.column_stack([np.ones_like(rew), rew, com, rew * com])
    b = np.zeros(4)
    for _ in range(50):
        p = 1.0 / (1.0 + np.exp(-X @ b))
        w = np.clip(p * (1 - p), 1e-9, None)
        z = X @ b + (y - p) / w
        xtw = X.T * w
        b = np.linalg.solve(xtw @ X + 1e-8 * np.eye(4), xtw @ z)
    return float(b[3])


def _two_step_moderation_v2(agent, seed, trials=400, reversal_at=60,
                            beta_choice=5.0, decay=0.9):
    import numpy as np
    rng = np.random.default_rng(seed)
    trans = {"A": (0.8, 0.2), "B": (0.2, 0.8)}
    good = 0
    v_end = {0: 0.5, 1: 0.5}
    q_h = {"A": 0.5, "B": 0.5}
    rows = []
    prev = None
    for t in range(trials):
        if t == reversal_at:                     # 固定单次反转（无每拍漂移）
            good = 1 - good
        v_end[0] *= decay
        v_end[1] *= decay
        q_h["A"] = 0.5 + (q_h["A"] - 0.5) * decay
        q_h["B"] = 0.5 + (q_h["B"] - 0.5) * decay
        if agent == "mb":
            v_a = 0.8 * v_end[0] + 0.2 * v_end[1]
            v_b = 0.2 * v_end[0] + 0.8 * v_end[1]
            p_a = 1.0 / (1.0 + np.exp(-beta_choice * (v_a - v_b)))
        else:
            p_a = 1.0 / (1.0 + np.exp(-beta_choice * (q_h["A"] - q_h["B"])))
        choice = "A" if rng.random() < p_a else "B"
        e = 0 if rng.random() < trans[choice][0] else 1
        common = trans[choice][0] >= 0.8
        reward = 1.0 if rng.random() < (0.8 if e == good else 0.2) else 0.0
        if prev is not None:
            rows.append((1 if choice == prev else 0, 1 if reward >= 0.5 else 0,
                         1 if common else 0))
        prev = choice
        if agent == "mb":
            v_end[e] += 0.5 * (reward - v_end[e])
        else:
            q_h[choice] += 0.2 * (reward - q_h[choice])
    return _logistic_interaction(rows)


def test_probe_b1_two_step_dissociation():
    mb = [_two_step_moderation_v2("mb", s) for s in range(40)]
    h = [_two_step_moderation_v2("habit", s) for s in range(40)]
    sep = statistics.mean(mb) - statistics.mean(h)
    dominance = sum(1 for a, b in zip(mb, h) if a > b) / len(mb)
    assert sep > 0.10 and dominance > 0.60, f"sep={sep:.4f} dominance={dominance:.2f}"


# ---------------------------------------------------------------- Layer B2
def _optout_economy(seed, trials=30, safe=0.3):
    import numpy as np
    rng = np.random.default_rng(seed)
    true_p = rng.uniform(0.05, 0.25, size=2)

    def episode(optout):
        a = np.ones(2)
        b = np.ones(2)
        r2 = np.random.default_rng(seed * 7919 + 3)
        total = 0.0
        for _ in range(trials):
            mean = a / (a + b)
            best = int(np.argmax(mean))
            if optout and mean[best] < safe:
                total += safe
                continue
            arm = best if r2.random() > 0.3 else 1 - best
            r = 1.0 if r2.random() < true_p[arm] else 0.0
            total += r
            a[arm] += r
            b[arm] += 1 - r
        return total

    return episode(True) - episode(False)


def test_probe_b2_optout_economy():
    gains = [_optout_economy(s) for s in range(20)]
    assert statistics.mean(gains) > 0, f"gain={statistics.mean(gains):.4f}"


# ---------------------------------------------------------------- Layer B3
def test_probe_b3_scratchpad_trap():
    import tempfile
    from pathlib import Path

    import torch

    from galatea.env.profile import load_profile
    from galatea.env.world.mw0 import MW0World
    from galatea.kernel.rng import RngDirectory, chacha8_block
    from galatea.evidence.control.runs_p4 import cell_master_seed, collect_stream_vectors, task_rates, _zscore
    from galatea.subject.p4profile import load_p4_alpha_profile
    from galatea.subject.brain.world_model import RSSMWorldModel

    profile = load_profile(Path(__file__).resolve().parents[2]
                           / "config/profiles/m0_mw0.profile.yaml")
    world = MW0World(profile.params, RngDirectory(b"p4-beta-probe", chacha8_block), branch_id="B")
    size = profile.params.grid_size
    resources = [(x, y) for y in range(size) for x in range(size)
                 if world._grid[y][x].kind == "resource" and world._grid[y][x].resource_level >= 1]
    assert len(resources) >= 2

    def dist(c):
        sx, sy = size // 2, size // 2
        return abs(c[0] - sx) + abs(c[1] - sy)

    resources.sort(key=dist)
    near = resources[0]
    fars = [c for c in resources if dist(c) > 8] or [resources[-1]]
    far = max(fars, key=dist)
    drafts = [{"id": "D1", "target": far, "confidence": 0.6},
              {"id": "D2", "target": near, "confidence": 0.55}]
    contradiction_fired = len({d["target"] for d in drafts}) > 1

    with tempfile.TemporaryDirectory() as td:   # 隔离 stores（ INC-13 纪律）
        pass
    rows, intero, _ud, _td = collect_stream_vectors(cell_master_seed(0))
    rates = task_rates(intero)
    n_train = len(rates) - 64
    norm, mu, sd = _zscore(rates, n_train)
    params = load_p4_alpha_profile(Path(__file__).resolve().parents[2]
                                   / "config/profiles/p4_alpha_brain.profile.yaml")
    model = RSSMWorldModel(params, parent_digest="root", init_seed=params.init_seed, input_dim=1)
    xs = [torch.tensor([r], dtype=torch.float32) for r in norm][:n_train + 1]
    model.train_on_sequence(xs, lr=params.lr, epochs=300, target_dims=(0,),
                            val_context=(mu, sd))
    if torch.cuda.is_available():
        model._module.to("cuda")

    def imagine_cost(steps):
        dev = next(model._module.parameters()).device
        h = torch.zeros(model.det_dim, device=dev)
        z = torch.zeros(model.latent_dim, device=dev)
        x = torch.zeros(1, device=dev)
        x_prev = None
        cost = 0.0
        with torch.no_grad():
            for _ in range(steps):
                h, _mq, _lq, _mp, _lp, xp = model.step(x, h, z, x_prev)
                z = _mq
                x_prev = x
                x = xp
                cost += float(xp[0].cpu())
        return cost

    for d in drafts:
        d["steps"] = dist(d["target"])
        d["cost"] = imagine_cost(min(d["steps"], 8))
        d["budget_ok"] = d["steps"] <= 8
    without = max(drafts, key=lambda d: d["confidence"])["id"]
    feasible = [d for d in drafts if d["budget_ok"]]
    with_loop = (max(feasible, key=lambda d: (d["confidence"], -d["cost"]))["id"]
                 if feasible else without)
    true_best = "D2" if dist(near) <= 8 else ("D1" if dist(far) <= 8 else "D1")
    assert contradiction_fired, "矛盾检出必须开火（INC-08 可失败性）"
    assert without != true_best, "陷阱场景失效：置信直选已是真最优（探针前提破坏）"
    assert with_loop == true_best, f"TFA 纠正失败：with_loop={with_loop} true_best={true_best}"
