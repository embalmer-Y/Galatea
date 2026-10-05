"""OOD 消融测试（L03 §7 ablation 行：移除 OOD → abstain 率坍缩为可检出退化）。"""
import pytest

from galatea.subject.perception.fusion import (
    FusionDomainExit,
    build_likelihood_table,
    fuse_window,
    occupancy_posterior,
)
from galatea.subject.perception.ood import OodAssessment, should_abstain
from galatea.subject.c1profile import load_c1_profile


@pytest.fixture()
def params():
    return load_c1_profile().perception


def _ood(flag: bool) -> OodAssessment:
    return OodAssessment(ood_flag=flag, ood_score=1.0 if flag else 0.0, reasons=(), evidence_refs=())


def test_ablate_ood_collapses_abstain_rate(params):
    """移除 OOD 判定（ood=False 注入）：域出输入不再触发 abstain → 坍缩可见。"""
    top = 0.9  # 高后验
    assert not should_abstain(top, params, _ood(False))    # OOD 缺席 → 不弃权（退化态）
    assert should_abstain(top, params, _ood(True))         # OOD 在位 → 弃权（判据可见且能失败）


def test_second_line_of_defense_still_fails_loudly(params):
    """双防线：即使 OOD 判定被消融，融合面域出仍独立检出（注入可失败）。"""
    table = build_likelihood_table(params.gain_by_distance, params.render_noise_sigma, params.bin_edges)
    window = ((0.9, 0.9, 0.9, 0.9, 0.9), (0.9, 0.9, 0.9, 0.9, 0.9), (0.9, 0.9, 0.9, 0.9, 0.9),
              (0.9, 0.9, 0.9, 0.9, 0.9), (1.5, 0.9, 0.9, 0.9, 0.9))
    # 管线收集形态：域出非空（整窗 abstain 触发）；原始 occupancy_posterior 即抛
    _, failures = fuse_window(window, params.prior_resource_density, table, "sf.x")
    assert failures and any("1.5" in f for f in failures)
    with pytest.raises(FusionDomainExit):
        occupancy_posterior(1.5, 0, 0, params.prior_resource_density, table, "sf.x")


def test_low_evidence_abstain_requires_ood_or_threshold(params):
    """abstain 两触发源可分别归因：OOD 与 threshold 独立。"""
    assert should_abstain(None, params, _ood(False))       # 无候选 → 弃权
    assert should_abstain(0.4, params, _ood(False))        # 低于 0.5 → 弃权
    assert not should_abstain(0.6, params, _ood(False))    # 高于阈值且无 OOD → 不弃权
