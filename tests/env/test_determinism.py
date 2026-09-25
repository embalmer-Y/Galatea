"""MW0 世界确定性重放（L01 §10 test_determinism.py——M0 核心退出条件的世界侧）。

断言：同 (profile, seed, 命令/干预序列) ⇒ 世界状态轨迹 tick 级 bit-exact；异 seed 发散。
"""
import io
from pathlib import Path

from galatea.env.interventions.registry import InterventionRegistry
from galatea.env.profile import load_profile
from galatea.env.world.dynamics import Command, MW0Dynamics
from galatea.env.world.mw0 import MW0World, Primitive
from galatea.kernel.rng import RngDirectory, chacha8_block

PROFILE_PATH = Path(__file__).resolve().parents[2] / "config" / "profiles" / "m0_mw0.profile.yaml"

SCRIPT: tuple[tuple[int, Primitive, str | None], ...] = (
    (0, Primitive.MOVE, "N"),
    (1, Primitive.FORAGE, None),
    (2, Primitive.MOVE, "E"),
    (3, Primitive.FORAGE, None),
    (4, Primitive.EAT, None),
    (5, Primitive.LOOK, None),
    (6, Primitive.MOVE, "S"),
    (7, Primitive.REST, None),
)


def run_world(seed: bytes, cycles: int = 64) -> tuple[list[str], str]:
    profile = load_profile(PROFILE_PATH)
    world = MW0World(profile.params, RngDirectory(seed, chacha8_block), branch_id="B")
    dynamics = MW0Dynamics(world, profile, RngDirectory(seed, chacha8_block), branch_id="B")
    registry = InterventionRegistry()
    trace: list[str] = []
    commands = {cycle: (primitive, param) for cycle, primitive, param in SCRIPT}
    for cycle in range(cycles):
        if cycle in commands:
            primitive, param = commands[cycle]
            fact = dynamics.apply(Command(primitive=primitive, param=param, command_id=f"c{cycle}"), registry, cycle)
            trace.append(f"{cycle}:{fact.requested_effect}->{fact.effective_effect}")
        events = dynamics.step()
        trace.append(f"{cycle}:events=" + ",".join(sorted(f"{e.kind}@{e.pos[0]},{e.pos[1]}" for e in events)))
    return trace, world.state_digest()


def test_profile_loads_from_frozen_contract() -> None:
    profile = load_profile(PROFILE_PATH)
    assert profile.params.grid_size == 16
    assert profile.params.min_dwell_cycles == 256
    assert profile.params.channel_loss_rate == 0.0  # Q-L01-09⑦
    assert profile.digest != ""


def test_same_seed_bit_exact(tmp_path: Path) -> None:
    trace_a, digest_a = run_world(b"mw0-seed-A")
    trace_b, digest_b = run_world(b"mw0-seed-A")
    assert trace_a == trace_b
    assert digest_a == digest_b


def test_different_seed_diverges() -> None:
    _, digest_a = run_world(b"mw0-seed-A")
    _, digest_b = run_world(b"mw0-seed-B")
    assert digest_a != digest_b


def test_layout_derivation_matches_q_g00_09() -> None:
    """风暴带数量 = round(storm_rate × 256)（Q-G00-09①：abundance=1、volatile=8）。"""
    profile = load_profile(PROFILE_PATH)
    assert MW0World.expected_storm_bands(profile.params, "abundance") == 1
    assert MW0World.expected_storm_bands(profile.params, "volatile") == 8
    world = MW0World(profile.params, RngDirectory(b"s", chacha8_block), branch_id="B")
    size = profile.params.grid_size
    bands = sum(1 for y in range(size) for x in range(size) if world.grid_kind((x, y)) == "storm_band")
    assert bands == 1  # initial_regime = abundance


def test_torus_boundary_wraps() -> None:
    profile = load_profile(PROFILE_PATH)
    world = MW0World(profile.params, RngDirectory(b"s", chacha8_block), branch_id="B")
    world.apply_primitive(Primitive.MOVE, "W")  # (0,0) → (15,0)
    assert world.body_cell_pos() == (15, 0)
    world.apply_primitive(Primitive.MOVE, "S")  # (15,0) → (15,15)
    assert world.body_cell_pos() == (15, 15)


def test_forage_eat_chain_and_floor() -> None:
    """觅食闭环（Q-L01-09④）：空地 forage 无效；floor clamp（Q-L01-09⑤）。"""
    profile = load_profile(PROFILE_PATH)
    world = MW0World(profile.params, RngDirectory(b"s", chacha8_block), branch_id="B")
    outcome = world.apply_primitive(Primitive.FORAGE, None)
    assert outcome.effective in ("forage_nothing_here", "forage_success_stored_1")  # 取决于出生点地形（确定性）
    for _ in range(120):  # 大量移动消耗 → 触及 energy floor
        world.apply_primitive(Primitive.MOVE, "N")
        world.apply_primitive(Primitive.MOVE, "E")
    assert world.energy_fraction() >= 0.0  # clamp 生效


# ==========================================================================
# regime 机：volatile/drift/min_dwell（ADR-G-0005 R6/R7 收尾）
# ==========================================================================
import pytest as _pytest

from galatea.env.world.mw0 import RegimeDwellViolation


def _fresh_world(seed: bytes = b"regime"):
    profile = load_profile(PROFILE_PATH)
    world = MW0World(profile.params, RngDirectory(seed, chacha8_block), branch_id="B")
    dynamics = MW0Dynamics(world, profile, RngDirectory(seed, chacha8_block), branch_id="B")
    return profile, world, dynamics


def test_min_dwell_enforced() -> None:
    """最小驻留（Q-L01-04）：256 cycles 内切换即拒；驻留期满可切换（R7 消费点）。"""
    _p, world, _d = _fresh_world()
    with _pytest.raises(RegimeDwellViolation):
        world.set_regime("volatile", at_tick=100)
    world.set_regime("volatile", at_tick=256)  # 驻留期满
    assert world.regime.value == "volatile"


def test_volatile_regime_changes_dynamics() -> None:
    """volatile：风暴率升高（全局期望 0.030 vs 0.005）——切换后命中数显著高于 abundance 同窗。"""
    _p, world, dynamics = _fresh_world()
    for _ in range(256):  # 走满 abundance 最小驻留（min_dwell 强制的正确测试姿势）
        dynamics.step()
    world.set_regime("volatile", at_tick=256)
    hits_volatile = sum(
        1
        for _ in range(256)
        for e in [dynamics.step()]
        if any(ev.kind in ("storm_hit", "integrity_damage_event") for ev in e)
    )
    _p2, _world_a, dynamics_a = _fresh_world(b"regime")  # abundance 基线（同 seed 同 256 拍窗）
    for _ in range(256):
        dynamics_a.step()
    hits_abundance = sum(
        1
        for _ in range(256)
        for e in [dynamics_a.step()]
        if any(ev.kind in ("storm_hit", "integrity_damage_event") for ev in e)
    )
    assert hits_volatile > hits_abundance


def test_storm_band_drift_in_volatile() -> None:
    """volatile 漂移（Q-L01-09②）：每 64 cycles 风暴带移动（数量守恒）。"""
    _p, world, dynamics = _fresh_world()
    for _ in range(256):
        dynamics.step()
    world.set_regime("volatile", at_tick=256)
    size = _p.params.grid_size
    def bands():
        return frozenset((x, y) for y in range(size) for x in range(size) if world.grid_kind((x, y)) == "storm_band")
    before = bands()
    for _ in range(64):
        dynamics.step()
    after = bands()
    assert len(after) == len(before)  # 数量守恒（漂移非增删）
    # 64-cycle 边界恰好触发一次漂移；格位是否变化取决于随机方向（可能原地等效），故只断言守恒 + 事件在案
    drift_events = [e for e in dynamics.events_so_far() if e.kind == "storm_band_drift"]
    assert len(drift_events) == 1


def test_respawn_level_regrow_observable() -> None:
    """储量再生（L01 §4.4"多级储量+再生"）：forage 降级后，respawn 节拍使储量回升（R6）。"""
    _p, world, dynamics = _fresh_world()
    size = _p.params.grid_size
    resource_cells = [(x, y) for y in range(size) for x in range(size) if world.grid_kind((x, y)) == "resource"]
    assert resource_cells, "abundance layout must contain resource patches"
    x, y = resource_cells[0]
    from galatea.env.world.mw0 import Patch, replace as _replace  # noqa: PLC0415
    level_before = world.snapshot(0).grid[y][x].resource_level
    world._grid[y][x] = _replace(world._grid[y][x], resource_level=1)  # 模拟耗损（noqa: SLF001）
    for _ in range(16):  # respawn_base 8 × multiplier 0.5 → interval 4；16 拍内必再生
        dynamics.step()
    level_after = world.snapshot(16).grid[y][x].resource_level
    assert level_after > 1
