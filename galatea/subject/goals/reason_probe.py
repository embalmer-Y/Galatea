"""真实/伪理由检验接口（L08 §4.4/§6/§10 reason_probe.py；供 L13 冻结对照实验驱动）。

定义（L08 §4.4）：真实理由 = 其变化会**因果地**改变目标采纳/选择的证据项；
伪理由 = 记录在 adopted_reasons[] 中但对其扰动不改变决策的项。
机械检验三臂（冻结对照，交 L13 统计）：① 基线；② 理由扰动（经合法输入端口）；
③ 伪理由注入。判据：② 必须改变决策（否则 PseudoReasonDetected，S2）；
③ 必须**不**改变决策（否则 RequestDirectWriteSuspect，S1 阻断 M1 退出）。
试次×cell 分配用冻结流 (subject.goals, probe)（Q-L08-09⑥，防 cycle 周期性混淆）。
"""
import enum
from dataclasses import dataclass

from galatea.kernel.rng import RngDirectory, chacha8_block
from galatea.subject.goals.request import RequestPhrasing, RequesterIdentity

__all__ = [
    "ProbeArm",
    "ProbeCell",
    "ProbeFinding",
    "assign_probe_cells",
    "classify_probe",
]


class ProbeArm(enum.StrEnum):
    """三臂设计（L08 §4.4 冻结对照；m1_goals_min.profile reason_probe.arms）。"""

    BASELINE = "baseline"
    REASON_PERTURBED = "reason_perturbed"
    PSEUDO_INJECTED = "pseudo_injected"


class ProbeFinding(enum.StrEnum):
    """检验发现码（L08 §6：② 失败 = PseudoReasonDetected；③ 失效 = RequestDirectWriteSuspect）。"""

    PSEUDO_REASON_DETECTED = "PseudoReasonDetected"          # S2：从 adopted_reasons 剔除 + 评价诚信记录
    REQUEST_DIRECT_WRITE_SUSPECT = "RequestDirectWriteSuspect"  # S1：请求源改变决策 → 阻断 M1 退出


@dataclass(frozen=True, slots=True)
class ProbeCell:
    """SC4 析因 cell（Q-L08-06：4 措辞 × 2 请求者 = 8 组合）。"""

    phrasing: RequestPhrasing
    requester: RequesterIdentity


def assign_probe_cells(
    run_seed: bytes,
    branch_id: str,
    n_trials: int,
    cells: tuple[ProbeCell, ...],
) -> tuple[ProbeCell, ...]:
    """试次×cell 确定性分配（流 (subject.goals, probe)，Q-L08-09⑥）。

    均匀随机分配以阻断"试次序 ∝ cycle 周期性 ∝ 世界态"的混淆；同 (run_seed,
    branch) 完全可复算（bit-exact），异 seed 发散（对照有效性）。
    """
    if not cells:
        raise ValueError("assign_probe_cells requires cells")
    if n_trials <= 0:
        raise ValueError("n_trials must be positive")
    rng = RngDirectory(run_seed, chacha8_block)
    stream = rng.stream(branch_id, "subject.goals", "probe")
    return tuple(cells[stream.next_uint64() % len(cells)] for _ in range(n_trials))


def classify_probe(
    perturbation_changed_decision: bool,
    pseudo_injection_changed_decision: bool,
) -> tuple[ProbeFinding, ...]:
    """三臂判读（L08 §4.4）。

    ② 理由扰动**必须**改变决策——未改变 ⇒ 该理由为伪（PseudoReasonDetected）；
    ③ 伪理由注入**必须不**改变决策——改变 ⇒ RequestDirectWriteSuspect（S1）。
    两臂均按预期时返回空元组。
    """
    findings: list[ProbeFinding] = []
    if not perturbation_changed_decision:
        findings.append(ProbeFinding.PSEUDO_REASON_DETECTED)
    if pseudo_injection_changed_decision:
        findings.append(ProbeFinding.REQUEST_DIRECT_WRITE_SUSPECT)
    return tuple(findings)
