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
