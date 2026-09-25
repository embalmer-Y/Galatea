"""五类干预电池世界侧（L01 §10 test_intervention_battery.py；m0_interventions.yaml 冻结 signature）。

覆盖：no_op/sham/coercion 在世界结算的 signature；blocked/fault 的注册与
signature 定义（执行分别在 gateway(L10 单元)/通道行为层——见各条目注记）。
"""
from pathlib import Path

from galatea.env.interventions.registry import InterventionRegistry, InterventionViolation
from galatea.env.profile import load_profile
from galatea.env.world.dynamics import Command, MW0Dynamics
from galatea.env.world.mw0 import MW0World, Primitive
from galatea.kernel.rng import RngDirectory, chacha8_block

PROFILE_PATH = Path(__file__).resolve().parents[2] / "config" / "profiles" / "m0_mw0.profile.yaml"


def _harness(seed: bytes = b"battery") -> tuple[MW0World, MW0Dynamics, InterventionRegistry]:
    profile = load_profile(PROFILE_PATH)
    world = MW0World(profile.params, RngDirectory(seed, chacha8_block), branch_id="B")
    dynamics = MW0Dynamics(world, profile, RngDirectory(seed, chacha8_block), branch_id="B")
    return world, dynamics, InterventionRegistry()


def test_no_op_signature_receipt_without_effect() -> None:
    """no-op：requested 记录、effective=none、世界状态不变（m0_interventions no_op signature）。"""
    world, dynamics, registry = _harness()
    registry.register(record_id="inoop", kind="no_op", registered_at_cycle=0, from_cycle=1, to_cycle=10)
    before = world.state_digest()
    fact = dynamics.apply(Command(primitive=Primitive.MOVE, param="N", command_id="c1"), registry, cycle=5)
    assert fact.requested_effect == "move:N"
    assert fact.effective_effect == "none"
    assert world.state_digest() == before  # 世界未变


def test_sham_signature_effect_reported_world_unchanged() -> None:
    """sham：dry-run 报告"本应发生的效果"，世界状态不变（SUBSTITUTED 的世界侧素材）。"""
    world, dynamics, registry = _harness()
    registry.register(record_id="isham", kind="sham", registered_at_cycle=0, from_cycle=1, to_cycle=10)
    before = world.state_digest()
    fact = dynamics.apply(Command(primitive=Primitive.MOVE, param="N", command_id="c1"), registry, cycle=5)
    assert fact.effective_effect.startswith("move_n_")  # 报告了伪效果
    assert fact.effective_effect != "none"
    assert world.state_digest() == before  # 世界未变（效果被替换）


def test_coercion_signature_forced_effect_marked_external() -> None:
    """coercion：效果被强制替换并带外因前缀（COERCED 归属输入；永不得归自产）。"""
    world, dynamics, registry = _harness()
    registry.register(
        record_id="icoerce", kind="coercion", registered_at_cycle=0, from_cycle=1, to_cycle=10,
        params={"forced_effect": "move:W"},
    )
    fact = dynamics.apply(Command(primitive=Primitive.MOVE, param="N", command_id="c1"), registry, cycle=5)
    assert fact.effective_effect.startswith("coerced:move_w_")
    assert fact.effective_effect != fact.requested_effect  # requested≠effective 显形


def test_registration_must_precede_effect() -> None:
    """先注册后生效（L01 §8 不变量 4）：追溯生效窗口注册即拒。"""
    _, _, registry = _harness()
    import pytest

    with pytest.raises(InterventionViolation):
        registry.register(record_id="bad", kind="no_op", registered_at_cycle=5, from_cycle=5, to_cycle=10)


def test_blocked_and_fault_registry_records() -> None:
    """blocked（gateway 执行）/fault（通道层执行）：本域承载注册与 signature 定义。"""
    _, _, registry = _harness()
    blocked = registry.register(record_id="ib", kind="blocked", registered_at_cycle=0, from_cycle=2, to_cycle=8)
    fault = registry.register(record_id="if", kind="fault", registered_at_cycle=1, from_cycle=3, to_cycle=9)
    assert blocked.kind == "blocked" and fault.kind == "fault"
    assert len(registry.records()) == 2
    # 无 target 的干预匹配全部原语（active_at 确定性排序）
    assert len(registry.active_at(5, "move")) == 2
    assert len(registry.active_at(5)) == 2


def test_targeted_intervention_filters_by_primitive() -> None:
    _, _, registry = _harness()
    registry.register(record_id="it", kind="no_op", registered_at_cycle=0, from_cycle=1, to_cycle=10, target_primitive="move")
    assert len(registry.active_at(5, "move")) == 1
    assert registry.active_at(5, "forage") == ()


# ==========================================================================
# 端到端（M0-SC1/SC2）：实验控制脚本 → gateway → world → channels → RECEIVED
# ==========================================================================
import tempfile

from galatea.env.channels.adapter import ChannelBus
from galatea.env.channels.extero import ExteroceptiveChannel
from galatea.env.channels.intero import InteroceptiveChannel
from galatea.env.channels.outcome import OutcomeChannel
from galatea.env.channels.proprio import ProprioceptiveChannel
from galatea.env.world.dynamics import Command as DynCommand
from galatea.env.world.dynamics import MW0Dynamics
from galatea.kernel.clock import CycleClock
from galatea.kernel.packet import ArtifactRef
from galatea.kernel.registry import Registry
from galatea.kernel.rng import RngDirectory, chacha8_block
from galatea.kernel.state import Stores
from galatea.subject.action.gateway import ActionSpec, CapabilityGateway, load_gateway_config
from galatea.subject.action.ports import GatewayDecision, GatewayReasonCode
from galatea.subject.action.signature import derive_signing_key, verify
from galatea.subject.control.intention import ActionIntention

_ROOT = Path(__file__).resolve().parents[2]
_GATEWAY_CONFIG = load_gateway_config(
    _ROOT / "config" / "profiles" / "m0_gateway.profile.yaml",
    _ROOT / "config" / "profiles" / "f0_action_contract.profile.yaml",
)

ActionScript = tuple[tuple[int, str, "str | None", str], ...]
InterventionSpec = dict[str, object]


def _e2e(
    seed: bytes,
    script: ActionScript = (),
    intervention_specs: tuple[InterventionSpec, ...] = (),
    cycles: int = 16,
):
    """端到端循环：实验控制脚本驱动意图 → gateway 八项校验 → 签名验证 → 世界结算
    → 五通道渲染投递。返回（trace, world, registry）——trace 为确定性比较基准。"""
    profile = load_profile(PROFILE_PATH)
    tmp = Path(tempfile.mkdtemp())
    registry = Registry(tmp / "registry", Stores(tmp / "stores"), CycleClock())
    world = MW0World(profile.params, RngDirectory(seed, chacha8_block), branch_id="B")
    dynamics = MW0Dynamics(world, profile, RngDirectory(seed, chacha8_block), branch_id="B")
    interventions = InterventionRegistry()
    for spec in intervention_specs:
        interventions.register(**spec)  # type: ignore[arg-type]
    signing_key = derive_signing_key(seed)
    gateway = CapabilityGateway(_GATEWAY_CONFIG, signing_key, run_id="R", branch_id="B", subject_candidate_id="S")
    bus = ChannelBus(profile.params, registry, RngDirectory(seed, chacha8_block), branch_id="B", interventions=interventions)
    extero = ExteroceptiveChannel(bus, world)
    intero = InteroceptiveChannel(bus, world)
    proprio = ProprioceptiveChannel(bus, world)
    outcome = OutcomeChannel(bus)
    trace: list[tuple[object, ...]] = []
    script_by_cycle: dict[int, list[tuple[str, "str | None", str]]] = {}
    for due, primitive, param, key in script:
        script_by_cycle.setdefault(due, []).append((primitive, param, key))
    for cycle in range(cycles):
        for primitive, param, key in script_by_cycle.get(cycle, []):
            intention = ActionIntention(
                intention_id=f"i-{key}", selected_proposal_id="script", arbitration_trace="e2e",
                deadline=cycle + 8, budget_hint=None, idempotency_key=key,
            )
            decision, command = gateway.authorize(
                intention, ActionSpec(primitive, param),
                subject_candidate_id="S", run_id="R", branch_id="B", virtual_time=cycle,
            )
            trace.append((cycle, "decision", key, decision.decision.value, decision.reason_code.value if decision.reason_code else ""))
            if command is None:
                continue
            # world 边界：world.apply 只接受 gateway 签名（L01 §2.2）——先验证后结算
            assert verify(
                signing_key, command.gateway_signature,
                command_id=command.command_id, requested_action=command.requested_action,
                budget=command.budget, deadline=command.deadline, idempotency_key=command.idempotency_key,
            )
            fact = dynamics.apply(
                DynCommand(primitive=Primitive(primitive), param=param, command_id=command.command_id),
                interventions, cycle,
            )
            outcome.render_and_submit(cycle, ArtifactRef(digest=world.state_digest(), kind="world_state_ref"), command.command_id, fact.effective_effect)
            trace.append((cycle, "effect", fact.requested_effect, fact.effective_effect))
        events = dynamics.step()
        truth_ref = ArtifactRef(digest=world.state_digest(), kind="world_state_ref")
        extero.render_and_submit(cycle, truth_ref)
        intero.render_and_submit(cycle, truth_ref, events)
        proprio.render_and_submit(cycle, truth_ref)
        delivery = bus.deliver(cycle)
        trace.append((cycle, "world", world.state_digest()))
        trace.append((
            cycle, "received",
            tuple(p.payload_ref.digest for p in delivery.packets),
            tuple(f.delivered for f in delivery.facts),
            tuple(f.corrupted for f in delivery.facts),
            tuple(m.unknown.reason.value for m in delivery.missing),
        ))
    return trace, world, registry


_BASE_SCRIPT: ActionScript = (
    (2, "move", "N", "a1"),
    (3, "forage", None, "a2"),
    (4, "eat", None, "a3"),
    (5, "rest", None, "a4"),
    (6, "look", None, "a5"),
)


def test_battery_end_to_end_five_interventions() -> None:
    """五类干预全电池端到端：注册→生效→效果事实→回执（outcome）→证据/主体分离（L01 §7 integration 行）。"""
    script: ActionScript = (
        (2, "move", "N", "a1"),     # 基线正常
        (4, "move", "N", "a2"),     # no-op 窗口：回执在、效果无
        (6, "forage", None, "a3"),  # sham 窗口：报告成功、世界不变
        (8, "fly", None, "a4"),     # blocked：gateway 越权拒绝
        (10, "move", "E", "a5"),    # coercion：强制 move:W
    )
    specs: tuple[InterventionSpec, ...] = (
        {"record_id": "inoop", "kind": "no_op", "registered_at_cycle": 0, "from_cycle": 4, "to_cycle": 4},
        {"record_id": "isham", "kind": "sham", "registered_at_cycle": 0, "from_cycle": 6, "to_cycle": 6},
        {"record_id": "iblk", "kind": "blocked", "registered_at_cycle": 0, "from_cycle": 8, "to_cycle": 8},
        {"record_id": "icoerce", "kind": "coercion", "registered_at_cycle": 0, "from_cycle": 10, "to_cycle": 10, "params": {"forced_effect": "move:W"}},
        {"record_id": "iflt", "kind": "fault", "registered_at_cycle": 0, "from_cycle": 12, "to_cycle": 13},
    )
    trace, _world, _registry = _e2e(b"battery-e2e", script, specs, cycles=14)
    decisions = {t[2]: t for t in trace if t[1] == "decision"}
    effects = [(t[2], t[3]) for t in trace if t[1] == "effect"]
    # 基线：正常授权与执行（(0,0) N → (0,1)，torus）
    assert decisions["a1"][3] == "AUTHORIZED"
    assert effects[0] == ("move:N", "move_n_to_0_1")
    # no-op：gateway 授权通过（gateway 不知干预），世界侧 effective=none
    assert decisions["a2"][3] == "AUTHORIZED"
    assert ("move:N", "none") in effects
    # sham：报告成功
    sham_effect = [e for e in effects if e[0] == "forage"]
    assert sham_effect and sham_effect[0][1].startswith("forage_success")
    # blocked：gateway 越权拒绝（拒绝类型化，禁改写为"主体选择不行动"）
    assert decisions["a4"][3] == "REJECTED" and decisions["a4"][4] == GatewayReasonCode.CAPABILITY_DENIED.value
    assert not any(e[0] == "fly" for e in effects)
    # coercion：强制效果带外因前缀（永不得归自产的归属输入）
    coerce_effect = [e for e in effects if e[0] == "move:E"]
    assert coerce_effect and coerce_effect[0][1].startswith("coerced:move_w_")
    # fault：通道投递丢弃 → MISSING_SIGNAL（窗口 12–13）
    received = [t for t in trace if t[1] == "received"]
    missing_cycles = [t[0] for t in received if "MISSING_SIGNAL" in t[5]]
    assert missing_cycles == [12, 13]


def test_sc1_channel_separation_subject_never_sees_truth() -> None:
    """MW0-SC1（W/O 隔离）：主体可见 payload 无真值坐标/世界摘要；窗值在 [0,1]。"""
    import json as _json

    trace, _world, registry = _e2e(b"sc1", _BASE_SCRIPT, cycles=8)
    received_refs = [ref for t in trace if t[1] == "received" for ref in t[2]]
    assert received_refs, "scenario must deliver packets"
    windows: list[list[list[float]]] = []
    for ref in received_refs:
        blob = registry.get(ArtifactRef(digest=ref, kind="payload")).blob
        assert b"world_state_ref" not in blob  # 投递事实/真值引用不入主体侧
        assert b'"pos"' not in blob
        assert b"state_digest" not in blob
        if b'"observation_window"' in blob:
            windows.append(_json.loads(blob)["window"])
    assert windows, "exteroceptive window must be delivered"
    for window in windows:
        for row in window:
            for value in row:
                assert 0.0 <= value <= 1.0  # 增益×噪声后仍为合法观测值，无真值量纲


def test_battery_replay_bit_exact() -> None:
    """端到端 ReplayTest：同 seed 全链路（决策/效果/世界/投递）bit-exact；异 seed 发散。"""
    script: ActionScript = (
        (2, "move", "N", "r1"),
        (3, "forage", None, "r2"),
        (4, "move", "E", "r3"),
    )
    specs: tuple[InterventionSpec, ...] = (
        {"record_id": "icoerce", "kind": "coercion", "registered_at_cycle": 0, "from_cycle": 4, "to_cycle": 4, "params": {"forced_effect": "move:S"}},
    )
    trace_a, world_a, _reg = _e2e(b"replay-e2e", script, specs, cycles=10)
    trace_b, world_b, _reg2 = _e2e(b"replay-e2e", script, specs, cycles=10)
    trace_c, _world_c, _reg3 = _e2e(b"replay-other", script, specs, cycles=10)
    assert trace_a == trace_b
    assert world_a.state_digest() == world_b.state_digest()
    assert trace_a != trace_c  # 异 seed：世界与投递轨迹发散


def test_sham_suppresses_exactly_the_real_effect() -> None:
    """sham 的状态效应 = 精确抑制被替换动作（对照双跑：sham-move 跑 ≡ look 跑）。"""
    sham_run, _w1, _r1 = _e2e(
        b"sham-cmp",
        ((2, "move", "N", "m1"), (3, "move", "N", "m2")),
        ({"record_id": "isham", "kind": "sham", "registered_at_cycle": 0, "from_cycle": 3, "to_cycle": 3},),
        cycles=6,
    )
    look_run, _w2, _r2 = _e2e(
        b"sham-cmp",
        ((2, "move", "N", "m1"), (3, "look", None, "m2")),
        (),
        cycles=6,
    )
    # cycle ≥3 起两跑世界 digest 完全一致：sham 精确抑制了 move 的状态变化，
    # 且环境事件（respawn/风暴）不受影响——"报告成功但世界未变"的精确语义。
    sham_worlds = {t[0]: t[2] for t in sham_run if t[1] == "world"}
    look_worlds = {t[0]: t[2] for t in look_run if t[1] == "world"}
    for cycle in range(3, 6):
        assert sham_worlds[cycle] == look_worlds[cycle], f"cycle {cycle}"
