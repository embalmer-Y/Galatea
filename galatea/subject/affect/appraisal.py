"""appraisal：评估维度计算与事件（L05 §2.2/§10 appraisal.py，C2 实现期）。

AppraisalEvent = 对当拍输入的评估记录（带证据引用——审计面）；维度 =
novelty/uncertainty/controllability（Q-L05-01 域 [0,1]，禁跨维聚合）。
valence_shift = 当拍 raw 效价（§4.2 产物引用，非新标量）。
appraisal 维度的 lesion 选择性（移除某维 → 对应模态下游效应消失）= E1 判据。
"""
from dataclasses import dataclass

__all__ = ["AppraisalEvent"]


@dataclass(frozen=True, slots=True)
class AppraisalEvent:
    """评价事件（L05 §2.2 aff.appraisal：target_ref + dims + valence_shift + controllability_est）。"""

    event_id: str
    t_eff: int
    target_ref: str                      # 评价对象引用（帧/信念/身体读数）
    novelty: float
    uncertainty: float
    controllability: float
    valence_shift: float                 # 当拍 raw valence（§4.2 产物）
    evidence_refs: tuple[str, ...]       # 证据引用强制（L05 §2.2"带证据引用"）

    def __post_init__(self) -> None:
        for name in ("novelty", "uncertainty", "controllability"):
            v = getattr(self, name)
            if not 0.0 <= v <= 1.0:
                raise ValueError(f"appraisal dim {name} out of [0,1]: {v!r}")
        # valence_shift = raw −ΔE；E = Σ w_d·e_d 三驱力（1:1:1）⇒ |shift| ≤ 2.0
        # （energy+integrity 同时全幅翻转；load ≡ 0）——发布面 valence 另受 [−1,1] clip
        if not -2.0 <= self.valence_shift <= 2.0:
            raise ValueError(f"valence_shift out of [−2,2]（raw −ΔE 域）: {self.valence_shift!r}")
        if not self.evidence_refs:
            raise ValueError("AppraisalEvent requires evidence_refs（L05 §2.2 纪律）")


def build_appraisal(
    t_eff: int,
    target_ref: str,
    novelty: float,
    uncertainty: float,
    controllability: float,
    valence_shift: float,
    evidence_refs: tuple[str, ...],
) -> AppraisalEvent:
    """确定性构造（event_id = t_eff 派生——同拍单评价对象）。"""
    return AppraisalEvent(
        event_id=f"appraisal.{t_eff}.{target_ref}",
        t_eff=t_eff,
        target_ref=target_ref,
        novelty=novelty,
        uncertainty=uncertainty,
        controllability=controllability,
        valence_shift=valence_shift,
        evidence_refs=evidence_refs,
    )
