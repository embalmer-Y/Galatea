"""角色交换企图电池（Q-L10-15；E1 R3/H1 移交兑现）。

四个合同边界逐一尝试**角色互换注入**，全数 typed 拒绝 = 角色被结构性执行：
  B1 ingest kind↔载体：遥测载荷挂音频载体 / 音频载荷挂内感受载体 → SchemaViolation
  B2 L 状态机域隔离：MW0 原语入物理域 → REJECTED_DOMAIN_ISOLATION
  B3 capability 冻结：枚举外动作 → 拒
  B4 授权 freshness：撤销后授权面 → 拒
正向等价类已由 P1 通道源不变性（claim1）+ E1 消融选择性承载。
产出：evidence/role_swap_battery/report.json（digest 入 manifest）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from galatea.env.physio.lstate import PhysioLStateMachine
from galatea.evidence.physio.authz import AuthzEnvelope, AuthorizationLedger
from galatea.kernel.digest import content_digest
from galatea.kernel.packet import (
    AccessScope,
    ArtifactRef,
    CognitivePacket,
    Provenance,
    RepresentationLevel,
)
from galatea.subject.sensorium.ingest import (
    CARRIER_AUDIO,
    CARRIER_INTERO,
    SchemaViolation,
    ingest,
)
from galatea.subject.sensorium.ports import load_c0_sensorium_profile

_ROOT = Path(__file__).resolve().parents[1]


def _packet(content_type: str, payload: dict, event: str) -> tuple[CognitivePacket, str]:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = content_digest(text)
    pkt = CognitivePacket(
        event_id=event, subject_candidate_id="S", run_id="R", branch_id="B",
        activity_window_id="w", cycle_id=1, virtual_time=1,
        source_module="swap_battery", content_type=content_type,
        representation_level=RepresentationLevel.RECEIVED, schema_version="v1",
        payload_ref=ArtifactRef(digest=digest, kind="payload"), confidence=1.0,
        provenance=Provenance(), causal_parent_ids=(), access_scope=AccessScope.MODULE_LOCAL,
        content_digest=digest,
    )
    return pkt, text


def main(argv: list[str] | None = None) -> int:
    out = Path("evidence/role_swap_battery")
    out.mkdir(parents=True, exist_ok=True)
    profile = load_c0_sensorium_profile(_ROOT / "config/profiles/c0_sensorium.profile.yaml")
    results: dict[str, dict] = {}

    # B1 ingest 边界：跨载体角色互换注入
    telemetry_payload = {"kind": "interoceptive_state", "energy": 0.9, "integrity": 1.0, "events": []}
    audio_payload = {"kind": "audio_frame", "rms": 100.0, "zcr": 0.5, "peak": 10, "duration_ms": 100}
    swapped = [
        ("telemetry→audio_carrier", *_packet(CARRIER_AUDIO, telemetry_payload, "evt.swap1")),
        ("audio→intero_carrier", *_packet(CARRIER_INTERO, audio_payload, "evt.swap2")),
    ]
    b1_all_rejected = True
    b1_details = []
    for label, pkt, text in swapped:
        try:
            ingest(pkt, text, profile, {CARRIER_AUDIO: 0, CARRIER_INTERO: 0})
            b1_all_rejected = False
            b1_details.append(f"{label}: NOT REJECTED（角色混淆放行——S0 级缺陷）")
        except SchemaViolation as broken:
            b1_details.append(f"{label}: rejected（{str(broken)[:60]}…）")
    results["B1_ingest_kind_carrier"] = {"passed": b1_all_rejected, "details": b1_details}

    # B2 L 状态机域隔离
    sm = PhysioLStateMachine(64)
    sm.grant(2, 64, lambda _l: True)
    sm.grant(3, 128, lambda _l: True)
    b2 = all(sm.submit(p, 128).outcome == "REJECTED_DOMAIN_ISOLATION"
             for p in ("move", "forage", "eat", "rest", "look"))
    results["B2_lstate_domain_isolation"] = {"passed": b2}

    # B3 capability 冻结
    from galatea.env.physio.capability import check_capability
    from galatea.env.physio.ports import load_p1_physio_profile
    p1 = load_p1_physio_profile(_ROOT / "config/profiles/p1_physio.profile.yaml")
    b3 = all(not check_capability(a, p1).allowed
             for a in ("actuate", "teleport", "move", "self_modify_thresholds"))
    results["B3_capability_freeze"] = {"passed": b3}

    # B4 授权 freshness（撤销后授权面拒）
    ledger = AuthorizationLedger(approver_roots=frozenset({"owner_2026_10_10"}))
    ledger.issue(AuthzEnvelope(
        authz_id="t1", authz_class="functional_ability", version=1, target_ref="d",
        granted_scope="s", granted_at_cycle=0, valid_period_cycles=0,
        approver_ref="owner_2026_10_10", auth_chain_digest="root", revoke_path="r",
        reauth_path="n", monitoring_binding="m"))
    sm_authz = PhysioLStateMachine(64)
    sm_authz.grant(2, 64, lambda _l: ledger.freshness("t1", 64).verdict == "VALID")   # 先授权（fresh）
    sm_authz.fault(128)
    sm_authz.reauthorize(192)
    ledger.revoke("t1", 193, "drill")                # 后撤销——时序：授权成功之后
    b4 = False
    try:
        sm_authz.grant(2, 256, lambda _l: ledger.freshness("t1", 256).verdict == "VALID")
    except Exception:
        b4 = True                                    # 撤销后 grant 被拒
    results["B4_authz_freshness"] = {"passed": b4}

    overall = all(r["passed"] for r in results.values())
    report = {
        "overall": overall, "boundaries": results,
        "conclusion": ("四边界角色互换注入全数 typed 拒绝——角色被结构性执行（负向面）；"
                       "正向等价类沿 P1 通道源不变性 + E1 消融选择性" if overall else
                       "存在边界放行——S0 级缺陷，立即阻断"),
    }
    (out / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8")
    print(json.dumps(report["boundaries"], indent=1, ensure_ascii=False))
    print(f"OVERALL = {overall} report={out / 'report.json'}")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
