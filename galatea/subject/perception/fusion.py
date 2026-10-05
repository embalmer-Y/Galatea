"""多模态表格后验融合（L03 §4.2/§10 fusion.py；C1 表格贝叶斯）。

似然表派生（Q-L03-03，全部来源冻结；与 ADR-G-0013 可复算探针规格同式）：
  对每 (state, d)：μ = present ? g(d) : 0.0；
  P(bin_i) = Φ((edge_{i+1}−μ)/σ) − Φ((edge_i−μ)/σ)，左右尾并入端 bin。
后验（逐窗格，Chebyshev 距离由窗结构已知）：
  posterior = π·L(present,d)[b] / (π·L(present,d)[b] + (1−π)·L(absent,d)[b])
π = initial_regime 覆盖率恒定（Q-L04-11；loader 从 m0 冻结初始条件派生）。
禁从数据学先验/似然（Q-L03-03 learning_from_data forbidden）。
确定性：全 float64（Q-T10）、无 RNG（c1 profile determinism none_c1）。
"""
from dataclasses import dataclass

from galatea.subject.c1profile import C1PerceptionParams, normal_cdf


class FusionDomainExit(ValueError):
    """观测越出冻结定义域（值越 [0,1]/距离键不存在）——事件级 OOD（Q-L03-02）。"""


@dataclass(frozen=True, slots=True)
class LikelihoodTable:
    """冻结似然表（Q-L03-03：手算可复核；行和 = 1 公差 1e-6）。"""

    bin_edges: tuple[float, ...]
    rows: dict[tuple[str, str], tuple[float, ...]]   # (state, dist_key) → P(bin)

    def row(self, state: str, dist_key: str) -> tuple[float, ...]:
        try:
            return self.rows[(state, dist_key)]
        except KeyError:
            raise FusionDomainExit(f"no likelihood row for (state={state}, {dist_key})") from None

    def quantize(self, value: float) -> int:
        """确定性量化：内点边数计数（v ≥ 内点 edge → 下一 bin；端 bin 闭合含尾）。"""
        interior = self.bin_edges[1:-1]
        return max(0, min(len(interior), sum(1 for e in interior if value >= e)))


def build_likelihood_table(
    gain_by_distance: dict[str, float], sigma: float, bin_edges: tuple[float, ...]
) -> LikelihoodTable:
    """似然表构建（μ/σ/edges 全部冻结参数；行和校验 fail closed）。"""
    if sigma <= 0.0:
        raise ValueError("render_noise_sigma must be positive（冻结合同）")
    edges = tuple(float(e) for e in bin_edges)
    rows: dict[tuple[str, str], tuple[float, ...]] = {}
    for dist_key in sorted(gain_by_distance):
        for state, mu in (("present", gain_by_distance[dist_key]), ("absent", 0.0)):
            probs = [
                normal_cdf((edges[i + 1] - mu) / sigma) - normal_cdf((edges[i] - mu) / sigma)
                for i in range(len(edges) - 1)
            ]
            # 左右尾并入端 bin（探针规格：P(bin_0) 从 −∞、P(bin_last) 到 +∞）
            probs[0] = normal_cdf((edges[1] - mu) / sigma)
            probs[-1] = 1.0 - normal_cdf((edges[-2] - mu) / sigma)
            total = sum(probs)
            if abs(total - 1.0) > 1e-6:
                raise ValueError(f"likelihood row ({state}, {dist_key}) sums to {total}（须 1±1e-6）")
            rows[(state, dist_key)] = tuple(probs)
    return LikelihoodTable(bin_edges=edges, rows=rows)


@dataclass(frozen=True, slots=True)
class OccupancyPosterior:
    """单窗格占据后验（egocentric 偏移 + 距离键；世界模型消费的规范化输出）。"""

    dx: int
    dy: int
    dist_key: str
    posterior_present: float
    bin_index: int
    evidence_frame_id: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.posterior_present <= 1.0:
            raise ValueError(f"posterior out of [0,1]: {self.posterior_present}")


def occupancy_posterior(
    value: float, dx: int, dy: int, prior: float, table: LikelihoodTable,
    evidence_frame_id: str,
) -> OccupancyPosterior:
    """单窗格贝叶斯更新（Q-L03-03 公式；value ∈ [0,1] 由形成层保证，越域即事件级 OOD）。"""
    if not 0.0 <= value <= 1.0:
        raise FusionDomainExit(f"window value {value!r} outside [0,1]（event-level OOD，Q-L03-02）")
    dist_key = f"d{max(abs(dx), abs(dy))}"
    b = table.quantize(value)
    lp = table.row("present", dist_key)[b]
    la = table.row("absent", dist_key)[b]
    num = prior * lp
    den = num + (1.0 - prior) * la
    if den <= 0.0:
        # 两假设下均零概率质量（float 下溢极尾）——事件级域出
        raise FusionDomainExit(f"zero likelihood mass at bin {b} ({dist_key})（OOD）")
    return OccupancyPosterior(
        dx=dx, dy=dy, dist_key=dist_key, posterior_present=num / den,
        bin_index=b, evidence_frame_id=evidence_frame_id,
    )


def fuse_window(
    window: tuple[tuple[float, ...], ...], prior: float, table: LikelihoodTable,
    evidence_frame_id: str,
) -> tuple[tuple[OccupancyPosterior, ...], tuple[str, ...]]:
    """整窗逐格融合（窗载荷约定 = 冻结渲染器序：window[r][c] ↔ egocentric
    (dx = c−offset, dy = r−offset)，N=(0,+1)（L01 §4 extero 载荷 schema））。

    返回 (cells, domain_exit_reasons)：双假设概率质量同时下溢的格（float64 极尾，
    如 d2 远格观测 0.9——冻结渲染模型下极端不可能）记域出并整窗 abstain（事件级
    纪律，Q-L03-02），不中断整窗批处理。"""
    cells: list[OccupancyPosterior] = []
    failures: list[str] = []
    offset = (len(window) - 1) // 2
    for r, row_values in enumerate(window):
        for c, value in enumerate(row_values):
            try:
                cells.append(occupancy_posterior(
                    float(value), c - offset, r - offset, prior, table, evidence_frame_id
                ))
            except FusionDomainExit as broken:
                failures.append(f"cell(r={r},c={c})={value!r}: {broken}")
    return tuple(cells), tuple(failures)


def collapse_decision(
    posterior: float, alternatives: tuple[float, ...], params: C1PerceptionParams
) -> bool:
    """塌缩判定（Q-L03-05：单假设后验 ≥0.9 或窗关闭首尾差 ≥0.6；tie 保留至容量）。

    首尾差分量由调用方传入 alternatives 序列（首=窗内首后验、尾=当前后验）；
    返回 True = 塌缩为单信念（alternatives 清空）；塌缩后新证据可重开（信念非承诺）。
    """
    if posterior >= params.collapse_confidence:
        return True
    if alternatives:
        if abs(alternatives[0] - posterior) >= params.collapse_margin:
            return True
    return False
