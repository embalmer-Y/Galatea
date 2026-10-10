"""Tessera 感知面测试（Q-L01-12：power→INTERO 忠实映射过完整既有链；act 形成面 + 默认关锚）。"""
import json
from pathlib import Path

import json

import pytest

from galatea.subject.sensorium.calibration import bind_calibration
from galatea.subject.sensorium.ingest import CARRIER_INTERO, CARRIER_TESSERA_ACT, ingest
from galatea.subject.sensorium.pipeline import SensoriumPipeline
from galatea.subject.sensorium.ports import (
    GainState,
    SensoryModality,
    load_c0_sensorium_profile,
)
from galatea.subject.sensorium.tests.conftest import intero_packet, time_basis

_ROOT = Path(__file__).resolve().parents[4]
_PROFILE_PATH = _ROOT / "config" / "profiles" / "c0_sensorium.profile.yaml"


def _contract_packet(content_type: str, payload: dict, event: str, cycle: int):
    """手构合同包（P04：subject 测试禁 import env——桥映射的载荷合同逐字段手建）。"""
    from galatea.kernel.digest import content_digest
    from galatea.kernel.packet import (
        AccessScope, ArtifactRef, CognitivePacket, Provenance, RepresentationLevel,
    )
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = content_digest(text)
    pkt = CognitivePacket(
        event_id=event, subject_candidate_id="S", run_id="R", branch_id="B",
        activity_window_id="tessera", cycle_id=cycle, virtual_time=cycle,
        source_module="env.tessera_bridge.dav", content_type=content_type,
        representation_level=RepresentationLevel.RECEIVED, schema_version="v1",
        payload_ref=ArtifactRef(digest=digest, kind="payload"), confidence=1.0,
        provenance=Provenance(), causal_parent_ids=(), access_scope=AccessScope.MODULE_LOCAL,
        content_digest=digest,
    )
    return pkt, text


def _power_packet(used: int, cycle: int):
    """桥映射后的 power 合同载荷（Q-L01-12①：energy = 1 − used/budget，budget=500）。"""
    energy = round(max(0.0, 1.0 - used / 500.0), 6)
    return _contract_packet(
        CARRIER_INTERO,
        {"kind": "interoceptive_state", "energy": energy, "integrity": 1.0, "events": []},
        f"evt.tessera.dav.power.{cycle}", cycle)


def _act_packet(dev: int, value: int, cycle: int):
    return _contract_packet(
        CARRIER_TESSERA_ACT,
        {"kind": "tessera_act_state", "dev": dev, "value_u": value},
        f"evt.tessera.dav.act.{cycle}", cycle)


def _pipeline(tessera_act: bool) -> SensoriumPipeline:
    profile = load_c0_sensorium_profile(_PROFILE_PATH)
    return SensoriumPipeline(
        profile, bind_calibration(_PROFILE_PATH, profile.calibration_version), time_basis(),
        tessera_act_enabled=tessera_act)


def test_power_flows_full_existing_intero_chain() -> None:
    """power → 桥忠实映射 → ingest → **既有 form_intero** → energy 感觉（零新形成面实证）。"""
    profile = load_c0_sensorium_profile(_PROFILE_PATH)
    pipeline = SensoriumPipeline(profile, bind_calibration(_PROFILE_PATH, profile.calibration_version),
                                 time_basis())
    seen_energy: list[float] = []
    for i, used in enumerate((0, 125, 250, 375, 500, 250, 0, 125, 250, 375)):
        packet, text = _power_packet(used, i)
        out = pipeline.process_cycle(i, [(packet, text)])
        for frame in out.frames:
            energy = getattr(frame.features, "energy_level", None)
            if energy is not None:
                seen_energy.append(energy)
    # 忠实映射：能量感觉 = 电源余量比（due = t0 ≤ N−1−W_align → 前 6 窗出帧）
    assert seen_energy == [1.0, 0.75, 0.5, 0.25, 0.0, 0.5]
    # energy_rate 感觉（派生差分）也在形成——既有链完整消费
    pipeline2 = SensoriumPipeline(profile, bind_calibration(_PROFILE_PATH, profile.calibration_version),
                                  time_basis())
    rates = []
    for i, used in enumerate((0, 125, 250, 375, 500, 250, 0, 125, 250, 375)):
        packet, text = _power_packet(used, i)
        out = pipeline2.process_cycle(i, [(packet, text)])
        for frame in out.frames:
            rate = getattr(frame.features, "energy_rate", None)
            if isinstance(rate, (int, float)):
                rates.append(rate)
    assert rates == pytest.approx([-0.25, -0.25, -0.25, -0.25, 0.5])   # 派生差分（既有语义）


def test_act_formed_only_when_enabled() -> None:
    packet, text = _act_packet(2, 655360, 0)
    # 默认关：act 载荷收下但不成帧（机会型缺席 = 静默；6 拍流跨对齐窗）
    p_off = _pipeline(tessera_act=False)
    p_on = _pipeline(tessera_act=True)
    act_off, act_on = [], []
    for cycle in range(6):
        o_off = p_off.process_cycle(cycle, [(packet, text)])
        o_on = p_on.process_cycle(cycle, [(packet, text)])
        act_off += [f for f in o_off.frames if getattr(f.features, "dev", None) is not None]
        act_on += [f for f in o_on.frames if getattr(f.features, "dev", None) is not None]
    assert not act_off
    # 开：形成 PROPRIO 帧（忠实变换）
    assert act_on and act_on[0].features.dev == 2 \
        and act_on[0].features.value_u == 655360
    assert act_on[0].modality is SensoryModality.PROPRIO


def test_tessera_flag_off_bit_exact_with_intero_stream() -> None:
    p1 = _pipeline(tessera_act=False)
    p2 = _pipeline(tessera_act=True)
    d1, d2 = [], []
    for cycle in range(6):
        pkt, text = intero_packet(cycle)
        d1 += [r.digest for r in p1.process_cycle(cycle, [(pkt, text)]).formation_receipts]
        d2 += [r.digest for r in p2.process_cycle(cycle, [(pkt, text)]).formation_receipts]
    assert d1 == d2 and d1                        # 旗标只影响 act 载荷——既有流 bit-exact


def test_ingest_rejects_act_kind_on_intero_carrier() -> None:
    """角色混淆负向锚：act kind 挂 INTERO 载体 → ingest 拒（kind↔载体 1:1 合同）。"""
    profile = load_c0_sensorium_profile(_PROFILE_PATH)
    text = json.dumps({"kind": "tessera_act_state", "dev": 2, "value_u": 1})
    from galatea.subject.sensorium.ingest import ingest as do_ingest
    from galatea.kernel.packet import (
        AccessScope, ArtifactRef, CognitivePacket, Provenance, RepresentationLevel,
    )
    from galatea.kernel.digest import content_digest
    digest = content_digest(text)
    pkt = CognitivePacket(
        event_id="evt.swap", subject_candidate_id="S", run_id="R", branch_id="B",
        activity_window_id="w", cycle_id=1, virtual_time=1, source_module="x",
        content_type=CARRIER_INTERO, representation_level=RepresentationLevel.RECEIVED,
        schema_version="v1", payload_ref=ArtifactRef(digest=digest, kind="payload"),
        confidence=1.0, provenance=Provenance(), causal_parent_ids=(),
        access_scope=AccessScope.MODULE_LOCAL, content_digest=digest,
    )
    with pytest.raises(Exception, match="does not match carrier"):
        do_ingest(pkt, text, profile, {CARRIER_INTERO: 0})
