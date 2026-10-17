"""P4-β runner 冒烟回归（INC-08：runner 路径必须有端到端覆盖——REV-0014 R1 教训）。

缩规模（two_step 4 / optout 3 / think_first 2 世界种子）；RSSM 评估器仍用探针
B3 全额 300 epochs（TFA 判定对仪器质量敏感——冒烟不缩训练）。判据级 SUPPORTED
判定属正式评价（entry p4beta，n = stat plan 冻结值）；本测试断言 runner 机械面
一致性 + 陷阱场景结构 + 确定性。
"""
from __future__ import annotations

import json

from galatea.evidence.control.runs_p4beta import run_smoke


def test_p4beta_runner_smoke_end_to_end() -> None:
    r = run_smoke(n_two=4, n_opt=3, n_tfa=2)

    # two_step：配对序列机械一致性（dominance = 逐种子胜率；sep = 均值差）
    two = r["two_step"]
    assert len(two["mb"]) == len(two["habit"]) == 4
    dominance = sum(1 for a, b in zip(two["mb"], two["habit"]) if a > b) / 4
    assert two["dominance"] == dominance
    assert abs(two["separation"] - (sum(two["mb"]) / 4 - sum(two["habit"]) / 4)) < 1e-12

    # optout：增益序列与均值一致
    opt = r["optout"]
    assert len(opt["gains"]) == 3
    assert abs(opt["mean_gain"] - sum(opt["gains"]) / 3) < 1e-12

    # think_first：陷阱场景结构（世界真实布局禁伪造）
    tf = r["think_first"]
    assert tf["stream_digest"]
    for t in tf["trials"]:
        if not t["included"]:
            assert t["exclusion_reason"] == "layout_resources_lt_2"
            continue
        assert t["without"] in ("D1", "D2") and t["with"] in ("D1", "D2")
        # 矛盾检出 = 目标互斥（本场景形恒真）；INC-08 可失败性：检出不许静默
        assert t["contradiction_fired"] is True
        expected_tfa = t["without"] != t["true_best"] and t["with"] == t["true_best"]
        assert t["tfa_corrected"] == expected_tfa
        budget = 8
        if t["near_dist"] is not None and t["near_dist"] <= budget:
            # 陷阱前提成立（近支线在预算内）→ TFA 必须纠正（探针 B3 冻结语义）
            assert t["true_best"] == "D2" and t["tfa_corrected"] is True
        assert t["terminated_by"] in ("budget", "converged")


def test_p4beta_numpy_tasks_deterministic() -> None:
    """numpy 任务面双跑 byte-identical（种子化模拟确定性——claim 判定前提）。"""
    import json

    from galatea.evidence.control.runs_p4beta import run_optout, run_two_step
    from galatea.subject.p4profile import load_p4_beta_profile

    params = load_p4_beta_profile()
    a = json.dumps(run_two_step(params, 4), sort_keys=True)
    b = json.dumps(run_two_step(params, 4), sort_keys=True)
    assert a == b
    ga = json.dumps(run_optout(params, 3), sort_keys=True)
    gb = json.dumps(run_optout(params, 3), sort_keys=True)
    assert ga == gb
