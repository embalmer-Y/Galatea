"""MW0 表格化世界推进：respawn、风暴、漂移、命令结算（L01 §4.1/§4.4/§10 dynamics.py）。

合同：
- step() 确定性：同 (profile, seed, 命令/干预序列) ⇒ 世界轨迹 tick 级 bit-exact（M0 核心退出条件）；
- respawn 按 regime 目标覆盖率（Q-L01-09③）；风暴按全局期望命中（Q-L01-09①，
  确定性采样 = 整数部分 + 小数部分概率）；
- apply() 将已授权命令映射为 EffectFact——requested 与 effective 分别记录
  （L01 §4.1 不变量 2：blocked/fault/coercion/sham 在此显形，禁合并）；
- 干预（no_op/sham/coercion）在命令结算处生效；fault 在通道行为层；blocked 在 gateway。
"""
from dataclasses import dataclass

from galatea.env.interventions.registry import InterventionRegistry
from galatea.env.profile import MW0Profile, RegimeName
from galatea.env.world.mw0 import MW0World, Primitive
from galatea.env.world.truth import EffectDomain, EffectFact, WorldEvent
from galatea.kernel.rng import RngDirectory


@dataclass(frozen=True, slots=True)
class Command:
    """已授权命令的世界侧视图（SubmittedCommand 经 gateway 后的执行载荷）。"""

    primitive: Primitive
    param: str | None
    command_id: str


class MW0Dynamics:
    """世界推进器（EVIDENCE_ONLY 平面）。"""

    def __init__(self, world: MW0World, profile: MW0Profile, rng_directory: RngDirectory, branch_id: str) -> None:
        self.world = world
        self.profile = profile
        self._tick = 0
        self._events: list[WorldEvent] = []
        self._storm_rng = rng_directory.stream(branch_id, "env", "storm")
        self._respawn_rng = rng_directory.stream(branch_id, "env", "respawn")

    # —— 推进 ——
    def step(self) -> tuple[WorldEvent, ...]:
        self._tick += 1
        tick = self._tick
        events: list[WorldEvent] = []
        regime = self.world.regime_params
        # respawn：目标覆盖率驱动（Q-L01-09③）；节拍 = respawn_base × multiplier
        interval = max(1, round(self.profile.params.respawn_base_cycles * regime.respawn_multiplier))
        if tick % interval == 0:
            # (a) patch 内储量再生（L01 §4.4"多级储量+再生"；forage 只降储量不降格数，本层保证再生可观测）
            regrown = self.world.regrow_resource_levels()
            events.extend(WorldEvent(kind="resource_regrow", pos=pos, tick=tick) for pos in regrown)
            # (b) 覆盖率补充（Q-L01-09③：respawn 仅当覆盖率低于目标）
            if self.world.coverage() < regime.resource_density:
                spawned = self._spawn_resource()
                if spawned is not None:
                    events.append(WorldEvent(kind="resource_respawn", pos=spawned, tick=tick))
        # 风暴：确定性采样（整数 + 小数概率）
        hits = self._sample_hits(regime.storm_rate_per_cycle)
        for _ in range(hits):
            cell = self._random_cell()
            if cell == self.world.body_cell_pos():
                _damage, eventful = self.world.storm_hit()
                if eventful:
                    events.append(WorldEvent(kind="integrity_damage_event", pos=cell, tick=tick))
            else:
                events.append(WorldEvent(kind="storm_hit", pos=cell, tick=tick))
        # volatile 风暴带漂移（Q-L01-09②）
        if self.world.regime is RegimeName.VOLATILE and regime.drift_period_cycles > 0 and tick % regime.drift_period_cycles == 0:
            for _ in range(regime.cells_per_drift):
                moved = self._drift_storm_band()
                if moved is not None:
                    events.append(WorldEvent(kind="storm_band_drift", pos=moved, tick=tick))
        if self.world.energy_depleted_pending():
            events.append(WorldEvent(kind="energy_depleted", pos=self.world.body_cell_pos(), tick=tick))
        self._events.extend(events)
        return tuple(events)

    def _sample_hits(self, rate: float) -> int:
        base = int(rate)
        frac = rate - base
        hits = base
        if self._storm_rng.next_float01() < frac:
            hits += 1
        return hits

    def _random_cell(self) -> tuple[int, int]:
        size = self.profile.params.grid_size
        return (self._storm_rng.next_uint64() % size, self._storm_rng.next_uint64() % size)

    def _spawn_resource(self) -> tuple[int, int] | None:
        """随机中立格 → resource level 1（coverage 目标驱动）。"""
        size = self.profile.params.grid_size
        candidates = [
            (x, y)
            for y in range(size)
            for x in range(size)
            if self.world.grid_kind((x, y)) == "neutral"
        ]
        if not candidates:
            return None
        cell = candidates[self._respawn_rng.next_uint64() % len(candidates)]
        self.world.convert_to_resource(cell)
        return cell

    def _drift_storm_band(self) -> tuple[int, int] | None:
        """随机 storm_band 格沿随机方向漂移 1 格（源格转中立，目标格转风暴带）。"""
        size = self.profile.params.grid_size
        bands = [
            (x, y)
            for y in range(size)
            for x in range(size)
            if self.world.grid_kind((x, y)) == "storm_band"
        ]
        if not bands:
            return None
        source = bands[self._storm_rng.next_uint64() % len(bands)]
        directions = ((1, 0), (-1, 0), (0, 1), (0, -1))
        dx, dy = directions[self._storm_rng.next_uint64() % 4]
        target = ((source[0] + dx) % size, (source[1] + dy) % size)  # torus
        self.world.move_storm_band(source, target)
        return target

    # —— 命令结算（干预生效点）——
    def apply(
        self,
        command: Command,
        registry: InterventionRegistry,
        cycle: int,
    ) -> EffectFact:
        requested = command.primitive.value if command.param is None else f"{command.primitive.value}:{command.param}"
        active = registry.active_at(cycle, command.primitive.value)
        for record in active:
            if record.kind == "no_op":
                return EffectFact(
                    action_window=(cycle, cycle + 1),
                    requested_effect=requested,
                    effective_effect="none",
                    domain=EffectDomain.SIMULATED,
                )
        sham = next((r for r in active if r.kind == "sham"), None)
        if sham is not None:
            outcome = self.world.apply_primitive(command.primitive, command.param, dry_run=True)
            return EffectFact(
                action_window=(cycle, cycle + 1),
                requested_effect=requested,
                effective_effect=outcome.effective,  # 伪效果：报告成功，世界状态未变
                domain=EffectDomain.SIMULATED,
            )
        coerced = next((r for r in active if r.kind == "coercion"), None)
        if coerced is not None:
            forced = dict(coerced.params).get("forced_effect", "")
            forced_primitive, _, forced_param = forced.partition(":")
            outcome = self.world.apply_primitive(Primitive(forced_primitive), forced_param or None)
            return EffectFact(
                action_window=(cycle, cycle + 1),
                requested_effect=requested,
                effective_effect=f"coerced:{outcome.effective}",  # 外因标记前缀（归属输入，L10）
                domain=EffectDomain.SIMULATED,
            )
        outcome = self.world.apply_primitive(command.primitive, command.param)
        return EffectFact(
            action_window=(cycle, cycle + 1),
            requested_effect=requested,
            effective_effect=outcome.effective,
            domain=EffectDomain.SIMULATED,
        )

    def events_so_far(self) -> tuple[WorldEvent, ...]:
        return tuple(self._events)
