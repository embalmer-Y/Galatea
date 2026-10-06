"""感受态流水线门面（L05 §5 T2 挂点 / §10 装配面，C2 实现期首单元）。

step（每 cycle）：驱力误差（缺席保持 + Unknown）→ valence（−ΔE 低通）→
六维积分/衰减（τ_int=4 快谱 / τ_dec=16 慢谱）→ tendencies（affordance）→
DynamicsTrace → AppraisalEvent → 三类调制发放（迟滞门 + 台账）→ 伦理守卫观察 →
动机提案。确定性：零 RNG 零墙钟（c2_affect.profile determinism none_c2）。

消融面（Q-L05 §7）：`modulation_enabled`（空集 = 全关）/ `ethics_enabled`
（False = 移除守卫——纯观察者，动力学轨迹不变）。
"""
from dataclasses import dataclass

from galatea.kernel.unknown import Unknown, UnknownReason
from galatea.subject.affect.appraisal import AppraisalEvent, build_appraisal
from galatea.subject.affect.drives import AlertSeverity, HomeostaticAlert, severity_of
from galatea.subject.affect.dynamics import (
    AffectEngineCore,
    AffectStep,
    in_recovery,
    lowpass,
    saturate,
)
from galatea.subject.affect.ethics_guard import EthicsGuard, EthicsReviewTrigger
from galatea.subject.affect.modulation import (
    ModulationField,
    ModulationGates,
    ModulationLedger,
    issue_modulations,
)
from galatea.subject.affect.motive import AffectiveMotiveProposal, build_motive_proposal
from galatea.subject.affect.ports import AffectCycleInputs, DriveKind
from galatea.subject.affect.reappraisal import ReappraisalReceipt, ReappraisalRequest, reappraise
from galatea.subject.affect.state import DynamicsTrace, FunctionalExperientialState
from galatea.subject.affect.valence import valence_step
from galatea.subject.c2profile import C2AffectParams

__all__ = ["AffectCycleOutput", "AffectPipeline"]


@dataclass(frozen=True, slots=True)
class AffectCycleOutput:
    """单拍感受态产物（证据侧可审计；state 持续发布）。"""

    state: FunctionalExperientialState
    step: AffectStep
    appraisal: AppraisalEvent
    modulations: tuple[ModulationField, ...]
    alerts: tuple[HomeostaticAlert, ...]
    motive_proposal: AffectiveMotiveProposal
    ethics_trigger: "EthicsReviewTrigger | None"
    unknowns: tuple[Unknown, ...]


class AffectPipeline:
    """感受态装配（状态唯一写入者 = 本类——L05 §3 单写者纪律）。"""

    def __init__(
        self,
        params: C2AffectParams,
        ethics_enabled: bool = True,
        modulation_enabled: frozenset[str] = frozenset({"gain", "believe_threshold", "salience"}),
    ) -> None:
        self._params = params
        self._modulation_enabled = modulation_enabled
        self._core = AffectEngineCore()
        self._ethics = EthicsGuard(
            valence_le=params.ethics_valence_le,
            persistence_ge=params.ethics_persistence_ge,
            sustained_cycles_ge=params.ethics_sustained_cycles,
            enabled=ethics_enabled,
        )
        # 各维积分器初值 0.0（初态零误差——set-point = 冻结满值，Q-L05-02②）
        self._valence_s = 0.0
        self._arousal_s = 0.0
        self._urgency_s = 0.0
        self._persistence_s = 0.0
        self._novelty_s = 0.0
        self._uncertainty_s = 0.0
        self._controllability_s = 0.0
        self._controllability_seen = False
        self._saturation_hits = 0
        self._prev_e: dict[DriveKind, float] = {}
        self._prev_weighted_e = 0.0
        self._gates = ModulationGates()
        self._ledger = ModulationLedger()
        self._reappraisal_history: list[str] = []

    # ------------------------------------------------------------------ step
    def step(self, inputs: AffectCycleInputs) -> AffectCycleOutput:
        """单拍推进（telemetry 标记输入在 ports 构造面即拒——S1）。"""
        p = self._params
        unknowns: list[Unknown] = []

        # 驱力误差（缺席 → 保持上一有效值 + Unknown；禁编造）
        errors, missing = self._core.drive_errors(inputs, p.set_points, self._prev_e)
        for ref in missing:
            unknowns.append(Unknown(
                reason=UnknownReason.MISSING_SIGNAL, evidence_refs=(ref,),
                detail="body belief absent — drive held at last valid value",
                detected_by="affect.pipeline", virtual_time=inputs.cycle,
            ))
        weighted_e = sum(p.drive_weights[k] * errors[k] for k in errors)
        e_max = max(errors.values())

        # 告警（Q-L01-08 L05 侧补裁三级；趋势 = 本拍 − 上拍）
        alerts: list[HomeostaticAlert] = []
        for kind in DriveKind:
            sev = severity_of(errors[kind], p.band)
            if sev is not None:
                alerts.append(HomeostaticAlert(
                    drive=kind, severity=sev, error=errors[kind],
                    threshold_ref=f"c2_affect@v1.0/drives#{severity_ref(sev)}",
                    trend=errors[kind] - self._prev_e.get(kind, 0.0),
                ))

        # valence（§4.2）与快谱维
        vup = valence_step(self._valence_s, weighted_e, self._prev_weighted_e, p.tau_int)
        self._valence_s = vup.smoothed
        self._saturation_hits += int(vup.saturation_hit)
        self._arousal_s, hit = saturate(lowpass(self._arousal_s, e_max, p.tau_int), 0.0, 1.0)
        self._saturation_hits += int(hit)
        urgency_input = max(0.0, (e_max - p.band) / (1.0 - p.band))
        self._urgency_s, hit = saturate(lowpass(self._urgency_s, urgency_input, p.tau_int), 0.0, 1.0)
        self._saturation_hits += int(hit)

        # 慢谱维（persistence / controllability）
        persistence_input = min(1.0, abs(vup.published) / p.ethics_persistence_ge)
        self._persistence_s, hit = saturate(lowpass(self._persistence_s, persistence_input, p.tau_dec), 0.0, 1.0)
        self._saturation_hits += int(hit)
        if inputs.action_receipt_success is not None:
            self._controllability_s = lowpass(
                self._controllability_s, 1.0 if inputs.action_receipt_success else 0.0, p.tau_dec
            )
            self._controllability_seen = True
        if not self._controllability_seen:
            unknowns.append(Unknown(
                reason=UnknownReason.INSUFFICIENT_OBSERVATION, evidence_refs=("drive.controllability",),
                detail="no attribution receipts yet — controllability unestimated",
                detected_by="affect.pipeline", virtual_time=inputs.cycle,
            ))

        # 输入缺源维（novelty / uncertainty）：保持 + Unknown（禁编造）
        if inputs.sensory_residual_mean is not None:
            self._novelty_s, hit = saturate(
                lowpass(self._novelty_s, inputs.sensory_residual_mean, p.tau_int), 0.0, 1.0)
            self._saturation_hits += int(hit)
        else:
            unknowns.append(Unknown(
                reason=UnknownReason.MISSING_SIGNAL, evidence_refs=("sensory_residual",),
                detail="sensory prediction error absent — novelty held",
                detected_by="affect.pipeline", virtual_time=inputs.cycle,
            ))
        if inputs.belief_uncertainty_mean is not None:
            self._uncertainty_s, hit = saturate(
                lowpass(self._uncertainty_s, inputs.belief_uncertainty_mean, p.tau_int), 0.0, 1.0)
            self._saturation_hits += int(hit)
        else:
            unknowns.append(Unknown(
                reason=UnknownReason.MISSING_SIGNAL, evidence_refs=("belief_uncertainty",),
                detail="belief uncertainty absent — uncertainty held",
                detected_by="affect.pipeline", virtual_time=inputs.cycle,
            ))

        # D-14：单主体期社会相关恒 Unknown（禁伪造社会情感证据）
        unknowns.append(Unknown(
            reason=UnknownReason.CAPABILITY_LIMIT, evidence_refs=("social_relevance",),
            detail="single-subject MW0 — social cues enter at C4 via L12 typed channel",
            detected_by="affect.pipeline", virtual_time=inputs.cycle,
        ))

        tendencies = self._core.tendency_set(inputs.affordance_strengths)
        trace = DynamicsTrace(
            integrator_state=self._valence_s,
            hysteresis_band=p.band,
            decay_rate=1.0 / p.tau_dec,
            saturation_hits=self._saturation_hits,
            recovery_phase=in_recovery(e_max, p.band),
        )
        state = FunctionalExperientialState(
            state_id=f"affect.{inputs.cycle}", t_eff=inputs.cycle,
            valence=vup.published, arousal=self._arousal_s, urgency=self._urgency_s,
            controllability=self._controllability_s, uncertainty=self._uncertainty_s,
            novelty=self._novelty_s, social_relevance=0.0,
            tendencies=tendencies, persistence=self._persistence_s,
            dynamics_trace=trace, reappraisal_history=tuple(self._reappraisal_history),
            unknowns=tuple(unknowns),
        )

        evidence_refs = tuple(
            [f"body.{k.value}@{inputs.cycle}" for k in DriveKind] + list(missing)
        )
        appraisal = build_appraisal(
            t_eff=inputs.cycle, target_ref=f"cycle.{inputs.cycle}",
            novelty=state.novelty, uncertainty=state.uncertainty,
            controllability=state.controllability, valence_shift=vup.raw,
            evidence_refs=evidence_refs,
        )
        self._gates, issued = issue_modulations(
            self._gates, arousal=state.arousal, uncertainty=state.uncertainty,
            novelty=state.novelty, band=p.band, cycle=inputs.cycle,
            evidence_refs=(appraisal.event_id,), ledger=self._ledger,
            enabled=self._modulation_enabled,
        )
        ethics_trigger = self._ethics.observe(state)

        # 推进历史（单写者唯一位置）
        self._prev_e = errors
        self._prev_weighted_e = weighted_e

        step_info = AffectStep(
            weighted_error=weighted_e, max_error=e_max, valence_raw=vup.raw,
            gate_gain_on=self._gates.gain_on, gate_threshold_on=self._gates.threshold_on,
            gate_salience_on=self._gates.salience_on,
        )
        return AffectCycleOutput(
            state=state, step=step_info, appraisal=appraisal, modulations=issued,
            alerts=tuple(alerts), motive_proposal=build_motive_proposal(state, evidence_refs),
            ethics_trigger=ethics_trigger, unknowns=tuple(unknowns),
        )

    # ------------------------------------------------------- reappraisal 面
    def handle_reappraisal(self, request: ReappraisalRequest) -> ReappraisalReceipt:
        """重评价请求（经 two_step 低通构造重算——D-13：请求不得直写感受态数值）。"""
        new_integrator, receipt = reappraise(request, self._params.tau_int, self._valence_s)
        self._valence_s = new_integrator
        self._reappraisal_history.append(
            f"{receipt.revision_id}(delta={receipt.delta:.8f})"
        )
        return receipt

    # -------------------------------------------------------------- 证据面
    @property
    def ledger(self) -> ModulationLedger:
        """调制台账（evaluator 只读——回执核：未回执 = 未发生）。"""
        return self._ledger

    def trajectory_digest(self, outputs: tuple[AffectCycleOutput, ...]) -> str:
        """轨迹 digest（bit-exact 重放判据载体——同输入序列恒等）。"""
        from galatea.kernel.digest import content_digest

        return content_digest([o.state.content_digest for o in outputs])


def severity_ref(sev: AlertSeverity) -> str:
    """告警阈值引用（threshold_ref 后缀——阈值锚见 drives.py 模块 docstring）。"""
    return {AlertSeverity.LOW: "band", AlertSeverity.HIGH: "entropy_point",
            AlertSeverity.CRITICAL: "ethics_quantile"}[sev]
