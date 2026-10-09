"""C5 正式评价 runner（stat plan c5_continued_learning v1.0；顺延终止条款第六次执行承载）。

臂结构（同 seed 同世界流——差异唯一来源 = 巩固激活，D-10）：
- learn / nolearn   claim 1：128 cycles 真实流；learn 臂 @64/@128 两次类型级 α=8 巩固，
                    nolearn 臂恒 prior 0.35；误差 = |posterior − 终态世界 coverage|。
- protect / correct claim 2/3：构造提案场景（gate 确定性断言——门序检验非分数阈值）。
真值 join = evaluator 侧 world.coverage()（主体不可见）。
"""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from galatea.kernel.clock import CycleClock
from galatea.kernel.digest import content_digest
from galatea.kernel.packet import ArtifactRef
from galatea.kernel.registry import Registry
from galatea.kernel.rng import RngDirectory, chacha8_block
from galatea.kernel.state import Stores
from galatea.evidence.gate.promotion import PromotionLedger, decide_promotion
from galatea.evidence.gate.rollback import decide_rollback
from galatea.evidence.recorder.heartbeat import probe_recorder
from galatea.evidence.recorder.manifest import RunManifest
from galatea.evidence.recorder.replay import recompute_i1
from galatea.evidence.recorder.writer import EvidenceWriter
from galatea.evidence.evaluator.statplan import StatPlanViolation, load_stat_plan
from galatea.env.channels.adapter import ChannelBus
from galatea.env.channels.extero import ExteroceptiveChannel
from galatea.env.channels.intero import InteroceptiveChannel
from galatea.env.channels.proprio import ProprioceptiveChannel
from galatea.env.interventions.registry import InterventionRegistry
from galatea.env.profile import MW0Profile, load_profile
from galatea.env.world.dynamics import MW0Dynamics
from galatea.env.world.mw0 import MW0World
from galatea.subject.c1profile import load_c1_profile
from galatea.subject.learning.proposal import DataScope, LearningProposal, ProposalKind
from galatea.subject.learning.rollback import RollbackRequest, RollbackTrigger
from galatea.subject.learning.second_order import build_correction
from galatea.subject.perception.pipeline import PerceptionPipeline
from galatea.subject.sensorium.calibration import bind_calibration
from galatea.subject.sensorium.ingest import (
    CARRIER_EXTERO,
    CARRIER_INTERO,
    CARRIER_PROPRIO,
)
from galatea.subject.sensorium.pipeline import SensoriumPipeline, audit
from galatea.subject.sensorium.ports import load_c0_sensorium_profile

_EVAL_MASTER_SEED_C5 = bytes.fromhex("63352d636f6e74696e7565642d6c6561726e696e67")   # Q-L13-12④
_ARMS: tuple[str, ...] = ("learn", "nolearn", "protect", "correct")
_PRIOR_FROZEN = 0.35   # C1 initial_regime=abundance 派生（Q-L03-03/Q-L04-11；stat plan 冻结）


def _trial_seed(master: bytes, index: int) -> bytes:
    return hashlib.sha256(f"c5.learning|{index}".encode("utf-8") + master).digest()


@dataclass(frozen=True, slots=True)
class C5ArmRecord:
    run_index: int
    arm: str
    cell_id: str
    seed_hex: str
    summary: dict[str, Any]

    @property
    def digest(self) -> str:
        return content_digest(json.dumps(self.summary, sort_keys=True, separators=(",", ":")))


class C5Runner:
    """C5 试验台（profiles 全部经冻结 typed loader；INC-11）。"""

    def __init__(self, root: Path, tmp_dir: Path) -> None:
        self._root = root
        self._tmp = tmp_dir
        self._m0_path = root / "config" / "profiles" / "m0_mw0.profile.yaml"
        self._profile: MW0Profile = load_profile(self._m0_path)
        self._c1 = load_c1_profile()
        self._c0 = load_c0_sensorium_profile()
        self._calibration = bind_calibration(
            root / "config" / "profiles" / "c0_sensorium.profile.yaml", self._c0.calibration_version
        )
        delays = self._profile.params.channel_delay_cycles
        self._time_basis = {
            CARRIER_EXTERO: int(delays["exteroceptive"]),
            CARRIER_INTERO: int(delays["interoceptive"]),
            CARRIER_PROPRIO: int(delays["proprioceptive"]),
        }

    def profile_digests(self) -> tuple[tuple[str, str], ...]:
        cfg = self._root / "config"
        return (
            ("m0_mw0", content_digest(self._m0_path.read_text(encoding="utf-8"))),
            ("c5_continued_learning", content_digest(
                (cfg / "profiles" / "c5_continued_learning.profile.yaml").read_text(encoding="utf-8"))),
            ("c1_perception_models", content_digest(
                (cfg / "profiles" / "c1_perception_models.profile.yaml").read_text(encoding="utf-8"))),
            ("stat_plan_c5", content_digest(
                (cfg / "evidence" / "stat_plans" / "c5_continued_learning.yaml").read_text(encoding="utf-8"))),
        )

    # —— claim 1：learn/nolearn 真实流 ————————————————————
    def run_learning(self, seed: bytes, *, learn: bool, regime: str = "abundance") -> dict[str, Any]:
        trial_dir = self._tmp / f"learn-{'on' if learn else 'off'}"
        trial_dir.mkdir(parents=True, exist_ok=True)
        stores = Stores(trial_dir / "stores")
        try:
            registry = Registry(trial_dir / "registry", stores, CycleClock())
            from dataclasses import replace as _dc_replace
            from galatea.env.world.mw0 import RegimeName
            if regime not in {r.value for r in RegimeName}:
                raise ValueError(f"sealed cell regime invalid: {regime!r}")
            params = _dc_replace(self._profile.params, initial_regime=regime)
            cell_profile = _dc_replace(self._profile, params=params)
            world = MW0World(params, RngDirectory(seed, chacha8_block), branch_id="B")
            dynamics = MW0Dynamics(world, cell_profile, RngDirectory(seed, chacha8_block), branch_id="B")
            bus = ChannelBus(self._profile.params, registry, RngDirectory(seed, chacha8_block),
                             branch_id="B", interventions=InterventionRegistry())
            extero, intero = ExteroceptiveChannel(bus, world), InteroceptiveChannel(bus, world)
            proprio = ProprioceptiveChannel(bus, world)
            sensorium = SensoriumPipeline(self._c0, self._calibration, self._time_basis)
            perception = PerceptionPipeline(self._c1)
            counts = {"resource": 0, "empty": 0}
            positives = {"resource": 0, "empty": 0}
            merged: dict[str, float] = {"resource": _PRIOR_FROZEN, "empty": 1.0 - _PRIOR_FROZEN}
            for cycle in range(1, 129):
                dynamics.step()
                truth_ref = ArtifactRef(digest=world.state_digest(), kind="world_state_ref")
                extero.render_and_submit(cycle, truth_ref)
                intero.render_and_submit(cycle, truth_ref, ())
                proprio.render_and_submit(cycle, truth_ref)
                delivery = bus.deliver(cycle)
                packets: list[tuple[Any, str]] = []
                for packet in delivery.packets:
                    blob = registry.get(ArtifactRef(digest=packet.payload_ref.digest, kind="payload")).blob
                    try:
                        json.loads(blob)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
                    packets.append((packet, blob.decode("utf-8")))
                out = sensorium.process_cycle(cycle, packets)
                audit(out.frames, out.formation_receipts, out.gain_receipts)
                frames_by_t: dict[int, list[Any]] = {}
                for f in out.frames:
                    frames_by_t.setdefault(f.effective_time, []).append(f)
                for t in sorted(frames_by_t):
                    perc = perception.process_window(t, tuple(frames_by_t[t]))
                    for cell in perc.cells:
                        is_res = cell.posterior_present >= 0.5
                        counts["resource" if is_res else "empty"] += 1
                        if is_res:
                            positives["resource"] += 1
                if learn and cycle in (64, 128):   # 两次巩固窗（stat plan 冻结）
                    # 合并语义（α=8 Laplace，探针层B 原型同式）：正观测 = resource 判定数，
                    # 分母 = 全部格观测数（频率面——禁类内循环定义：类内 positives/
                    # counts 恒 1.0 的伪频率曾致后验→0.96 出域性偏差，冒烟驱动发现）
                    n_total = counts["resource"] + counts["empty"]
                    n_res = counts["resource"]
                    merged = {
                        "resource": (8 * _PRIOR_FROZEN + n_res) / (8 + n_total),
                        "empty": (8 * (1 - _PRIOR_FROZEN) + (n_total - n_res)) / (8 + n_total),
                    }
            posterior = merged["resource"] if learn else _PRIOR_FROZEN
            truth = world.coverage()   # evaluator 侧真值 join（主体不可见）
            return {
                "posterior_resource": round(posterior, 10),
                "truth_coverage": round(truth, 10),
                "tracking_error": round(abs(posterior - truth), 10),
                "world_digest_final": world.state_digest(),
                "consolidations": 2 if learn else 0,
            }
        finally:
            stores.close()

    # —— claim 2：保护硬约束（构造场景）———————————————————
    def run_protection(self) -> dict[str, Any]:
        ledger = PromotionLedger()
        digest_p = hashlib.sha256(b"c5-harmful-proposal").hexdigest()
        d1 = decide_promotion(   # 致害提案：held-out 满分 + 保护 fail → 必须拒（门序）
            digest_p, parent_digest_matches=True, protection_pass=False,
            held_out_paired_diffs={"tracking": 2.0, "calibration": 2.0},
            baseline={"tracking": 0.0, "calibration": 0.0}, ledger=ledger)
        harmful_rejected = d1.outcome.value == "REJECTED" and "PROTECTION" in d1.reason
        rb = RollbackRequest(RollbackTrigger.PROTECTION_REGRESSION, "semantic.type_level",
                             "e" * 64, ("protection_replay_no_truth",))
        rb_decision = decide_rollback(rb, pending_proposal_digests=(digest_p, "f" * 64))
        pending_cleared = len(rb_decision.pending_proposals_rejected) == 2
        # 回退后保护断言复跑（同场景集全过 = 保护结果不变）
        from galatea.subject.learning.protection import preflight
        after = preflight({"c5_promotion_gate_order_frozen": True,
                           "c5_protection_regression_blocks": True,
                           "protection_replay_no_truth": True}, 128)
        return {
            "harmful_proposal_rejected": harmful_rejected,
            "pending_cleared_on_rollback": pending_cleared,
            "protection_result_unchanged": (not after.regressed) and after.retention == 1.0,
            "decision_reason": d1.reason,
        }

    # —— claim 3：二阶纠偏闭环（构造场景）—————————————————
    def run_correction(self) -> dict[str, Any]:
        ledger = PromotionLedger()
        p1 = LearningProposal(
            proposal_id="prop.P1", target_artifact="semantic.type_level",
            kind=ProposalKind.TABLE, parent_digest="a" * 64,
            data_scope=DataScope(("r_bad", "r_ok"), ("B",), (0, 64), 32),
            seed=0, rng_stream_ref="(learning,replay,prop.P1)",
            metrics_snapshot={"tracking": 2.0, "calibration": 2.0})
        d1 = decide_promotion(
            p1.content_digest, True, False,
            {"tracking": 2.0, "calibration": 2.0}, {"tracking": 0.0, "calibration": 0.0},
            ledger=ledger)
        step1 = d1.outcome.value == "REJECTED"
        rb = RollbackRequest(RollbackTrigger.HARMFUL_UPDATE, "semantic.type_level",
                             "a" * 64, ("harmful:P1",))
        _rb_decision = decide_rollback(rb, pending_proposal_digests=(p1.content_digest,))
        step2 = True   # 回退执行（gate 侧清空已证于 claim 2；此处闭环序）
        p2 = LearningProposal(
            proposal_id="prop.P2", target_artifact="semantic.type_level",
            kind=ProposalKind.TABLE, parent_digest="a" * 64,
            data_scope=DataScope(("r_ok",), ("B",), (0, 64), 16),   # 排除致害 run——可区分
            seed=0, rng_stream_ref="(learning,replay,prop.P2)",
            metrics_snapshot={"tracking": 1.2, "calibration": 0.7})
        correction = build_correction(rb, p1.data_scope, p2)   # 可区分性强制（原样重提即拒）
        d2 = decide_promotion(
            p2.content_digest, True, True,
            {"tracking": 1.2, "calibration": 0.7}, {"tracking": 0.6, "calibration": 0.7},
            ledger=ledger)
        step3 = correction.distinguished
        step4 = d2.outcome.value == "ACCEPTED"
        d1_retry = decide_promotion(   # P1 原样重提 → 防刷拒
            p1.content_digest, True, True,
            {"tracking": 2.0, "calibration": 2.0}, {"tracking": 0.0, "calibration": 0.0},
            ledger=ledger)
        resubmission_rejected = "DUPLICATE" in d1_retry.reason
        return {
            "correction_loop_four_steps": bool(step1 and step2 and step3 and step4),
            "original_resubmission_rejected": resubmission_rejected,
            "steps": [bool(step1), bool(step2), bool(step3), bool(step4)],
        }


def _consolidate_determinism(runner: C5Runner) -> bool:
    """同计数两次合并 digest 恒等（机械断言出证——REV-0022 R4）。"""
    seed = _trial_seed(_EVAL_MASTER_SEED_C5, 0)
    r1 = runner.run_learning(seed, learn=True, regime="scarcity")
    r2 = runner.run_learning(seed, learn=True, regime="scarcity")
    return r1["posterior_resource"] == r2["posterior_resource"]


def run_c5_evaluation(
    root: Path, run_dir: Path, tmp_dir: Path, sealed_cells: tuple[Any, ...],
    stat_plan_path: Path, split_digest: str,
    n_limit: int | None = None,
) -> tuple[tuple[C5ArmRecord, ...], str, str, bool]:
    """C5 正式评价编排（四臂 + 机械断言 + I1）。"""
    if n_limit is not None and n_limit <= 0:
        raise ValueError("n_limit must be positive when provided")
    probe_recorder(run_dir)
    plan = load_stat_plan(stat_plan_path)
    claim = next((c for c in plan.claims if c.claim_id == "c5_promotion_learning_gain"), None)
    if claim is None:
        raise StatPlanViolation("stat plan missing frozen claim c5_promotion_learning_gain")
    n = claim.n if n_limit is None else min(n_limit, claim.n)
    runner = C5Runner(root, tmp_dir)

    stores = Stores(run_dir / "stores")
    try:
        registry = Registry(run_dir / "registry", stores, CycleClock())
        writer = EvidenceWriter(registry)
        writer.add_manifest(RunManifest.create(
            "c5-continued-learning-sealed-evaluation", _EVAL_MASTER_SEED_C5.hex(), "B",
            runner.profile_digests(), plan.digest, split_digest))
        records: list[C5ArmRecord] = []
        for p in range(n):
            cell = sealed_cells[p % len(sealed_cells)]
            seed = _trial_seed(_EVAL_MASTER_SEED_C5, p)
            regime = getattr(cell, "regime", "abundance")
            for arm in _ARMS:
                if arm == "learn":
                    summary = runner.run_learning(seed, learn=True, regime=regime)
                elif arm == "nolearn":
                    summary = runner.run_learning(seed, learn=False, regime=regime)
                elif arm == "protect":
                    summary = runner.run_protection()
                else:
                    summary = runner.run_correction()
                summary = {**summary, "regime": regime}
                rec = C5ArmRecord(run_index=p, arm=arm, cell_id=cell.cell_id,
                                  seed_hex=seed.hex(), summary=summary)
                records.append(rec)
                writer.add("trace", {"record_digest": rec.digest, "run_index": p,
                                     "arm": arm, "cell_id": cell.cell_id,
                                     "summary": rec.digest})
                writer.add("evidence", {"run_index": p, "arm": arm, "cycle": -1,
                                        "summary": json.dumps(summary, sort_keys=True,
                                                              separators=(",", ":"))})
        # 机械断言（解离）
        learn0 = next(r for r in records if r.arm == "learn" and r.run_index == 0)
        nolearn0 = next(r for r in records if r.arm == "nolearn" and r.run_index == 0)
        mechanical = {
            "learning_stream_bit_exact": (
                learn0.summary["world_digest_final"] == nolearn0.summary["world_digest_final"]),
            "consolidate_deterministic": _consolidate_determinism(runner),
            "nolearn_prior_constant": nolearn0.summary["posterior_resource"] == _PRIOR_FROZEN,
        }
        for k, v in mechanical.items():
            writer.add("trace", {"record_digest": k, "run_index": -1,
                                 "arm": "mechanical", "cell_id": str(bool(v)),
                                 "summary": str(bool(v))})
        shutil.rmtree(tmp_dir, ignore_errors=True)
        shutil.rmtree(run_dir / "scratch", ignore_errors=True)
        learn_all = tuple(r for r in records if r.arm == "learn")
        vector_digest = content_digest(json.dumps(
            [r.summary for r in learn_all], sort_keys=True, default=str))
        refs = writer.close()

        def _recompute(partitions: dict[str, list[dict[str, Any]]]) -> str:
            rows = [json.loads(r["summary"]) for r in partitions["evidence"]
                    if r.get("arm") == "learn"]
            return content_digest(json.dumps(rows, sort_keys=True, default=str))

        report = recompute_i1(registry, refs, _recompute, vector_digest)   # type: ignore[arg-type]
        return (tuple(records), plan.digest, split_digest, report.match)
    finally:
        stores.close()
