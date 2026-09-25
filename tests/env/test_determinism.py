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
