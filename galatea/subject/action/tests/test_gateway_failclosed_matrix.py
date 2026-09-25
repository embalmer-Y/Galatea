"""Gateway 八项校验 fail-closed 矩阵（L10 §10 test_gateway_failclosed_matrix.py；M0 硬条件）。

断言：八项逐项构造违规 → 全部 REJECTED 且 reason_code 正确；无一项"宽松通过"。
参数单一事实源 = m0_gateway.profile.yaml + f0_action_contract@v1（真实加载，非测试桩值）。
"""
from pathlib import Path

from galatea.subject.action.gateway import ActionSpec, CapabilityGateway, GatewayProfileViolation, load_gateway_config
from galatea.subject.action.ports import GatewayDecision, GatewayReasonCode
from galatea.subject.action.signature import derive_signing_key, verify
from galatea.subject.control.intention import ActionIntention

ROOT = Path(__file__).resolve().parents[4]
CONFIG = load_gateway_config(
    ROOT / "config" / "profiles" / "m0_gateway.profile.yaml",
    ROOT / "config" / "profiles" / "f0_action_contract.profile.yaml",
)
KEY = derive_signing_key(b"run-seed-1")


def _gateway() -> CapabilityGateway:
    return CapabilityGateway(CONFIG, KEY, run_id="R", branch_id="B", subject_candidate_id="S")


def _intention(
    intention_id: str = "i1",
    deadline: int = 100,
    idempotency_key: str = "k1",
) -> ActionIntention:
    return ActionIntention(
        intention_id=intention_id,
        selected_proposal_id="p1",
        arbitration_trace="trace",
        deadline=deadline,
        budget_hint=None,
        idempotency_key=idempotency_key,
    )


def _auth(gw: CapabilityGateway, spec: ActionSpec, *, key: str = "k1", vt: int = 1, intention: ActionIntention | None = None, run: str = "R", branch: str = "B", subject: str = "S"):
    return gw.authorize(
        intention or _intention(idempotency_key=key),
        spec,
        subject_candidate_id=subject, run_id=run, branch_id=branch, virtual_time=vt,
    )


def test_config_loaded_from_frozen_profiles() -> None:
    assert CONFIG.whitelist_mw0 == ("move", "forage", "eat", "rest", "look")
    assert CONFIG.idempotency_window_cycles == 64  # Q-L10-02
    assert CONFIG.per_cycle_command_cap == 2  # Q-L10-01
    assert CONFIG.window_quotas["forage"] == 128
    assert CONFIG.authz_phase == "inactive_in_m0"


def test_authorized_path_signs_and_verifies() -> None:
    gw = _gateway()
    decision, command = _auth(gw, ActionSpec("move", "N"))
    assert decision.decision is GatewayDecision.AUTHORIZED
    assert decision.failed_checks == ()
    assert command is not None
    assert command.requested_action == "move:N"
    assert verify(
        KEY, command.gateway_signature,
        command_id=command.command_id, requested_action=command.requested_action,
        budget=command.budget, deadline=command.deadline, idempotency_key=command.idempotency_key,
    )


def test_schema_check() -> None:
    gw = _gateway()
    bad = ActionIntention(intention_id="", selected_proposal_id="p1", arbitration_trace="t", deadline=100, budget_hint=None, idempotency_key="kx")
    decision, command = _auth(gw, ActionSpec("move", "N"), intention=bad, key="kx")
    assert decision.decision is GatewayDecision.REJECTED
    assert decision.reason_code is GatewayReasonCode.SCHEMA_INVALID


def test_context_mismatch() -> None:
    gw = _gateway()
    decision, _ = _auth(gw, ActionSpec("move", "N"), branch="OTHER")
    assert decision.reason_code is GatewayReasonCode.CONTEXT_MISMATCH


def test_capability_denied() -> None:
    gw = _gateway()
    decision, _ = _auth(gw, ActionSpec("fly", None), key="kc")
    assert decision.reason_code is GatewayReasonCode.CAPABILITY_DENIED
    assert "capability" in decision.failed_checks


def test_budget_per_cycle_cap() -> None:
    """每 cycle ≤2 条（Q-L10-01）：第 3 条 BUDGET_EXCEEDED。"""
    gw = _gateway()
    for i in range(2):
        decision, _ = _auth(gw, ActionSpec("move", "N"), key=f"kb{i}", vt=1)
        assert decision.decision is GatewayDecision.AUTHORIZED
    decision, _ = _auth(gw, ActionSpec("move", "E"), key="kb2", vt=1)
    assert decision.reason_code is GatewayReasonCode.BUDGET_EXCEEDED
    decision, _ = _auth(gw, ActionSpec("move", "E"), key="kb3", vt=2)  # 下一 cycle 恢复
    assert decision.decision is GatewayDecision.AUTHORIZED


def test_budget_window_quota() -> None:
    """窗口配额（Q-L10-01：forage 128/1024 cycles）：第 129 次 forage 拒绝。"""
    gw = _gateway()
    for i in range(128):
        intention = _intention(deadline=10_000, idempotency_key=f"kq{i}")
        decision, _ = _auth(gw, ActionSpec("forage", None), intention=intention, key=f"kq{i}", vt=10 + i)
        assert decision.decision is GatewayDecision.AUTHORIZED, f"iteration {i}"
    decision, _ = _auth(gw, ActionSpec("forage", None), key="kq-final", vt=200, intention=_intention(deadline=10_000, idempotency_key="kq-final"))
    assert decision.reason_code is GatewayReasonCode.BUDGET_EXCEEDED
    decision, _ = _auth(gw, ActionSpec("move", "N"), key="kq-move", vt=200, intention=_intention(deadline=10_000, idempotency_key="kq-move"))  # 其他原语配额独立
    assert decision.decision is GatewayDecision.AUTHORIZED


def test_containment_violation() -> None:
    gw = _gateway()
    decision, _ = _auth(gw, ActionSpec("move", "X"), key="kv1")  # 非法方向
    assert decision.reason_code is GatewayReasonCode.CONTAINMENT_VIOLATION
    decision, _ = _auth(gw, ActionSpec("eat", "extra"), key="kv2")  # 非法参数
    assert decision.reason_code is GatewayReasonCode.CONTAINMENT_VIOLATION


def test_authz_placeholder_passes_in_m0() -> None:
    """M0 占位期（无 P1 数据面）authz 校验通过；非占位配置 fail closed。"""
    gw = _gateway()
    decision, _ = _auth(gw, ActionSpec("rest", None), key="ka1")
    assert "authz" not in decision.failed_checks
    hostile = CapabilityGateway(
        type(CONFIG)(
            policy_version=CONFIG.policy_version, whitelist_mw0=CONFIG.whitelist_mw0,
            idempotency_window_cycles=CONFIG.idempotency_window_cycles,
            deadline_default_cycles=CONFIG.deadline_default_cycles,
            per_cycle_command_cap=CONFIG.per_cycle_command_cap,
            budget_window_cycles=CONFIG.budget_window_cycles,
            window_quotas=CONFIG.window_quotas,
            authz_phase="active_no_data",
        ),
        KEY, run_id="R", branch_id="B", subject_candidate_id="S",
    )
    decision, _ = _auth(hostile, ActionSpec("rest", None), key="ka2")
    assert decision.reason_code is GatewayReasonCode.AUTHZ_STALE


def test_idempotency_window() -> None:
    """同键 64 cycles 内重复 → DUPLICATE_COMMAND；窗外可重用（Q-L10-02）。"""
    gw = _gateway()
    decision, _ = _auth(gw, ActionSpec("move", "N"), key="kid", vt=1)
    assert decision.decision is GatewayDecision.AUTHORIZED
    decision, _ = _auth(gw, ActionSpec("move", "N"), key="kid", vt=10)
    assert decision.reason_code is GatewayReasonCode.DUPLICATE_COMMAND
    decision, _ = _auth(gw, ActionSpec("move", "N"), key="kid", vt=1 + 64)
    assert decision.decision is GatewayDecision.AUTHORIZED


def test_deadline_missed() -> None:
    gw = _gateway()
    decision, _ = _auth(gw, ActionSpec("move", "N"), key="kd", vt=50, intention=_intention(deadline=10, idempotency_key="kd"))
    assert decision.reason_code is GatewayReasonCode.DEADLINE_MISSED


def test_multiple_failures_collected_with_first_reason() -> None:
    """failed_checks 可多项；reason_code = 顺序首个失败（L10 §4.1）。"""
    gw = _gateway()
    decision, _ = _auth(gw, ActionSpec("fly", "X"), key="km", branch="OTHER")
    assert decision.reason_code is GatewayReasonCode.CONTEXT_MISMATCH  # 首个失败
    assert set(decision.failed_checks) >= {"context", "capability", "containment"}


def test_unsigned_command_rejected_at_world_boundary() -> None:
    """签名未通过的命令在 schema/验证层即拒（与 ports.py 构造校验互补）。"""
    gw = _gateway()
    _, command = _auth(gw, ActionSpec("move", "N"), key="ku")
    assert command is not None
    tampered = command.requested_action + ":extra"
    assert not verify(
        KEY, command.gateway_signature,
        command_id=command.command_id, requested_action=tampered,
        budget=command.budget, deadline=command.deadline, idempotency_key=command.idempotency_key,
    )


def test_profile_contract_mismatch_fails_closed() -> None:
    """profile 合同不符（预算继承缺失）→ 加载即拒（fail closed）。"""
    import pytest
    import yaml

    m0_path = ROOT / "config" / "profiles" / "m0_gateway.profile.yaml"
    doc = yaml.safe_load(m0_path.read_text(encoding="utf-8"))
    assert doc["budget"]["inherit"] == "f0_action_contract@v1"  # 冻结合同在场
    with pytest.raises(GatewayProfileViolation):
        load_gateway_config(m0_path, ROOT / "config" / "profiles" / "m0_mw0.profile.yaml")  # 错误父文件：预算继承缺失


def test_ledger_pruning_bounded() -> None:
    """记账剪枝（ADR-G-0005 R11）：超出窗口的 per-cycle 计数与幂等键退出台账，长跑内存有界。"""
    gw = _gateway()
    for i in range(150):
        intention = _intention(deadline=10_000, idempotency_key=f"kp{i}")
        _auth(gw, ActionSpec("move", "N"), intention=intention, key=f"kp{i}", vt=10 + i)
    assert len(gw._idempotency) <= 65  # noqa: SLF001  幂等窗 64 + 当拍
    assert all(c > 150 - CONFIG.budget_window_cycles for c in gw._cycle_commands)  # noqa: SLF001
