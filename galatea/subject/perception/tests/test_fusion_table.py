"""表格后验融合测试（L03 §7 unit：确定性、可手算复核）。"""
import pytest

from galatea.subject.c1profile import load_c1_profile, normal_cdf
from galatea.subject.perception.fusion import (
    FusionDomainExit,
    build_likelihood_table,
    fuse_window,
    occupancy_posterior,
)


@pytest.fixture()
def profile():
    return load_c1_profile()


@pytest.fixture()
def table(profile):
    return build_likelihood_table(
        profile.perception.gain_by_distance, profile.perception.render_noise_sigma,
        profile.perception.bin_edges,
    )


def test_likelihood_row_sums_to_one(table):
    for (state, dist_key), row in table.rows.items():
        assert abs(sum(row) - 1.0) < 1e-6, (state, dist_key, sum(row))


def test_likelihood_matches_probe_spec_bit_exact(table):
    """探针规格（ADR-G-0013 可复算）：d0-present bin4 = 0.999968（评审逐位复现）。"""
    row = table.row("present", "d0")
    assert row[4] == pytest.approx(0.999968, abs=1e-6)
    assert row[0] == pytest.approx(0.0, abs=1e-12)


def test_top_bin_mass_monotone_decreasing_with_distance(table):
    """顶 bin 质量随 d 单调递减（探针判别质量判据）。"""
    tops = [table.row("present", f"d{d}")[4] for d in (0, 1, 2)]
    assert tops[0] > tops[1] > tops[2]


def test_quantization_deterministic(table):
    assert table.quantize(0.0) == 0
    assert table.quantize(0.2) == 1
    assert table.quantize(0.9) == 4
    assert table.quantize(1.0) == 4


def test_posterior_equals_prior_when_likelihoods_equal(table, profile):
    """手算可复核锚：d1 观测 0.3 → 两假设似然相等（各 3.17e-5）→ 后验 = 先验 0.35。"""
    cell = occupancy_posterior(0.3, 1, 0, profile.perception.prior_resource_density, table, "sf.x")
    lp = table.row("present", "d1")[1]
    la = table.row("absent", "d1")[1]
    assert lp == pytest.approx(la, rel=1e-3)
    assert cell.posterior_present == pytest.approx(profile.perception.prior_resource_density, rel=1e-3)


def test_posterior_extremes(table, profile):
    """d0 强观测 → 后验 ≈ 1（absent 顶 bin 为 16σ 尾，float64 下确零）。"""
    cell = occupancy_posterior(0.9, 0, 0, profile.perception.prior_resource_density, table, "sf.x")
    assert cell.posterior_present > 0.999
    zero = occupancy_posterior(0.0, 0, 0, profile.perception.prior_resource_density, table, "sf.x")
    assert zero.posterior_present < 0.001


def test_domain_exit_out_of_range(table, profile):
    """值越 [0,1] = 事件级 OOD（Q-L03-02 零连续阈值）。"""
    with pytest.raises(FusionDomainExit):
        occupancy_posterior(1.5, 0, 0, 0.35, table, "sf.x")
    with pytest.raises(FusionDomainExit):
        occupancy_posterior(-0.1, 0, 0, 0.35, table, "sf.x")


def test_fuse_window_convention_and_domain_exit_collection(table, profile):
    """窗约定 = 渲染器序 window[r][c] ↔ (dx=c−2, dy=r−2)；极端远格域出收集不中断。"""
    window = [[0.0] * 5 for _ in range(5)]
    window[2][2] = 0.9          # 中心 (0,0) @ d0
    window[0][0] = 0.9          # 角 (-2,-2) @ d2 → 双假设质量下溢 → 域出
    cells, failures = fuse_window(tuple(tuple(r) for r in window), 0.35, table, "sf.x")
    assert len(failures) == 1 and "r=0,c=0" in failures[0]
    center = next(c for c in cells if c.dx == 0 and c.dy == 0)
    assert center.posterior_present > 0.999


def test_fusion_deterministic_double_run(table, profile):
    """同输入双跑逐位恒等（c1 determinism none_c1）。"""
    window = tuple(tuple(0.6 if (r + c) % 3 == 0 else 0.1 for c in range(5)) for r in range(5))
    a = fuse_window(window, profile.perception.prior_resource_density, table, "sf.x")
    b = fuse_window(window, profile.perception.prior_resource_density, table, "sf.x")
    assert a == b


def test_normal_cdf_reference_points():
    assert normal_cdf(0.0) == 0.5
    assert normal_cdf(1.959963984540054) == pytest.approx(0.975, abs=1e-6)
