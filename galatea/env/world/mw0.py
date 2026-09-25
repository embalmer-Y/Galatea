"""MW0 世界：几何、patch、身体、动作原语、regime 机（L01 §4.4/§10 mw0.py）。

合同：
- 世界推进为**表格/枚举**（M0 可手算复核，L01 §4.4）；RNG 只来自 L00 派生流（Q-T11）；
- 动作原语五类（move/forage/eat/rest/look）；torus 环形边界（Q-L01-02）；
- 觅食闭环与 floor 语义按 Q-L01-09④⑤；M0 无死亡/重生/自然回复；
- world 状态对主体不可见（EVIDENCE_ONLY 平面，静态隔离由 tests/env 探针看守）。
"""
import enum
from dataclasses import dataclass, replace

from galatea.env.profile import MW0Params, RegimeName
from galatea.env.world.truth import BodyTruth, Patch, WorldEvent, WorldState
from galatea.kernel.digest import content_digest
from galatea.kernel.rng import CounterStream, RngDirectory


class Primitive(enum.StrEnum):
    """MW0 五原语（f0_action_contract containment 白名单）。"""

    MOVE = "move"
    FORAGE = "forage"
    EAT = "eat"
    REST = "rest"
    LOOK = "look"


DIRECTIONS: dict[str, tuple[int, int]] = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}


@dataclass(frozen=True, slots=True)
class PrimitiveOutcome:
    """原语执行结果：世界侧效果描述 + 是否发生状态变化（EffectFact 的 requested/effective 素材）。"""

    effective: str
    state_changed: bool
    events: tuple[WorldEvent, ...] = ()


class MW0World:
    """MW0 世界状态机（内部可变；snapshot() 出冻结 WorldState）。"""

    def __init__(self, params: MW0Params, rng_directory: RngDirectory, branch_id: str) -> None:
        self.params = params
        self._rng = rng_directory.stream(branch_id, "env", "dynamics")
        self._layout_rng = rng_directory.stream(branch_id, "env", "layout")
        self._grid: list[list[Patch]] = []
        self._body_pos: tuple[int, int] = (0, 0)
        self._orientation = "N"
        self._energy = params.energy_max
        self._integrity = params.integrity_max
        self._load = 0.0
        self._stored_food = 0
        self._regime = RegimeName(params.initial_regime)
        self._energy_depleted_seen = False
        self._layout()

    # —— 布局（Q-G00-09 派生规则）——
    def _layout(self) -> None:
        size = self.params.grid_size
        cells = size * size
        regime = self.params.regime(self._regime.value)
        n_resource = round(regime.resource_density * cells)
        n_storm = round(regime.storm_rate_per_cycle * cells)  # Q-G00-09① 派生
        kinds: list[str] = (
            ["resource"] * n_resource + ["storm_band"] * n_storm
            + ["neutral"] * (cells - n_resource - n_storm)
        )
        # 确定性洗牌（Fisher–Yates，layout 流）
        for i in range(len(kinds) - 1, 0, -1):
            j = self._layout_rng.next_uint64() % (i + 1)
            kinds[i], kinds[j] = kinds[j], kinds[i]
        self._grid = [
            [Patch(kind=kinds[y * size + x], resource_level=0, respawn_timer=0) for x in range(size)]
            for y in range(size)
        ]
        for row in self._grid:
            for x, patch in enumerate(row):
                if patch.kind == "resource":
                    row[x] = replace(patch, resource_level=self.params.resource_max_level)

    # —— 状态快照 ——
    def snapshot(self, tick: int) -> WorldState:
        grid = tuple(tuple(col for col in row) for row in self._grid)
        body = BodyTruth(
            pos=self._body_pos, orientation=self._orientation,
            energy=self._energy, integrity=self._integrity, load=self._load,
        )
        return WorldState(grid=grid, body=body, events=())

    def state_digest(self) -> str:
        return content_digest(
            {
                "grid": [[p.kind, p.resource_level] for row in self._grid for p in row],
                "pos": self._body_pos,
                "orientation": self._orientation,
                "energy": self._energy,
                "integrity": self._integrity,
                "stored_food": self._stored_food,
                "regime": self._regime.value,
            }
        )

    # —— regime 机 ——
    @property
    def regime(self) -> RegimeName:
        return self._regime

    def set_regime(self, name: str) -> None:
        self._regime = RegimeName(name)  # 越界即 ValueError（StrEnum）

    @property
    def regime_params(self):
        return self.params.regime(self._regime.value)

    def coverage(self) -> float:
        """resource patch 当前覆盖率（respawn 目标对比用，Q-L01-09③）。"""
        total = self.params.grid_size * self.params.grid_size
        count = sum(1 for row in self._grid for p in row if p.kind == "resource")
        return count / total

    # —— 动作原语（dry_run 供 sham 使用：同计算、不落状态）——
    def apply_primitive(self, primitive: Primitive, param: str | None, dry_run: bool = False) -> PrimitiveOutcome:
        if primitive is Primitive.MOVE:
            return self._move(param, dry_run)
        if primitive is Primitive.FORAGE:
            return self._forage(dry_run)
        if primitive is Primitive.EAT:
            return self._eat(dry_run)
        if primitive is Primitive.REST:
            return self._rest(dry_run)
        return PrimitiveOutcome(effective="look_done", state_changed=False)

    def _mutate(self, dry_run: bool) -> bool:
        return not dry_run

    def _move(self, param: str | None, dry_run: bool) -> PrimitiveOutcome:
        if param not in DIRECTIONS:
            return PrimitiveOutcome(effective="move_invalid_direction", state_changed=False)
        dx, dy = DIRECTIONS[param]
        size = self.params.grid_size
        x, y = self._body_pos
        new_pos = ((x + dx) % size, (y + dy) % size)  # torus（Q-L01-02）
        if self._mutate(dry_run):
            self._body_pos = new_pos
            self._orientation = param
            self._spend_energy(self.params.action_energy_delta["move"])
        return PrimitiveOutcome(effective=f"move_{param.lower()}_to_{new_pos[0]}_{new_pos[1]}", state_changed=True)

    def _forage(self, dry_run: bool) -> PrimitiveOutcome:
        x, y = self._body_pos
        patch = self._grid[y][x]
        if patch.kind != "resource" or patch.resource_level < 1:
            return PrimitiveOutcome(effective="forage_nothing_here", state_changed=False)
        if self._stored_food >= self.params.food_storage_max:
            return PrimitiveOutcome(effective="forage_failed_storage_full", state_changed=False)
        stored_after = self._stored_food + self.params.forage_yield
        if self._mutate(dry_run):
            self._grid[y][x] = replace(patch, resource_level=patch.resource_level - 1)
            self._stored_food = stored_after
            self._spend_energy(self.params.action_energy_delta["forage"])
        return PrimitiveOutcome(effective=f"forage_success_stored_{stored_after}", state_changed=True)

    def _eat(self, dry_run: bool) -> PrimitiveOutcome:
        if self._stored_food < 1:
            return PrimitiveOutcome(effective="eat_failed_no_food", state_changed=False)
        if self._mutate(dry_run):
            self._stored_food -= 1
            self._gain_energy(self.params.action_energy_delta["eat"])
        return PrimitiveOutcome(effective="eat_success", state_changed=True)

    def _rest(self, dry_run: bool) -> PrimitiveOutcome:
        if self._mutate(dry_run):
            self._gain_energy(self.params.action_energy_delta["rest"])
        return PrimitiveOutcome(effective="rest_success", state_changed=True)

    # —— 能量/损伤与 floor 语义（Q-L01-09⑤）——
    def _spend_energy(self, delta: float) -> None:
        self._energy = max(0.0, self._energy + delta)  # clamp 0
        if self._energy == 0.0 and not self._energy_depleted_seen:
            self._energy_depleted_seen = True  # 首次触 0 事件由 dynamics 记录（body 内仅置位）

    def _gain_energy(self, delta: float) -> None:
        self._energy = min(self.params.energy_max, self._energy + delta)

    def storm_hit(self) -> tuple[float, bool]:
        """风暴命中当前格：shelter 豁免；返回 (实际损伤, 是否记 damage_event)。"""
        x, y = self._body_pos
        if self._grid[y][x].kind == "shelter":
            return (0.0, False)
        damage = min(self.params.storm_damage_per_hit, self._integrity)
        self._integrity = max(0.0, self._integrity - damage)  # M0 无再生（Q-L01-09⑤）
        return (damage, damage >= self.params.damage_event_min_delta)

    def body_cell_kind(self) -> str:
        x, y = self._body_pos
        return self._grid[y][x].kind

    # —— dynamics 协作面（世界内部操作，均为 EVIDENCE_ONLY）——
    def body_cell_pos(self) -> tuple[int, int]:
        return self._body_pos

    def grid_kind(self, cell: tuple[int, int]) -> str:
        x, y = cell
        return self._grid[y][x].kind

    def convert_to_resource(self, cell: tuple[int, int]) -> None:
        x, y = cell
        self._grid[y][x] = Patch(kind="resource", resource_level=1, respawn_timer=0)

    def move_storm_band(self, source: tuple[int, int], target: tuple[int, int]) -> None:
        sx, sy = source
        tx, ty = target
        self._grid[sy][sx] = Patch(kind="neutral", resource_level=0, respawn_timer=0)
        self._grid[ty][tx] = Patch(kind="storm_band", resource_level=0, respawn_timer=0)

    def energy_depleted_pending(self) -> bool:
        """energy 首次触 0 的待报事件位（读取即清除——dynamics 记录 WorldEvent 用）。"""
        if self._energy_depleted_seen:
            self._energy_depleted_seen = False
            return True
        return False

    def stored_food(self) -> int:
        return self._stored_food

    def energy_fraction(self) -> float:
        return self._energy / self.params.energy_max

    def integrity_fraction(self) -> float:
        return self._integrity / self.params.integrity_max

    def orientation(self) -> str:
        return self._orientation

    # —— 观测渲染素材（channel 行为层消费；本方法不泄露真值坐标）——
    def render_window(self, stream: CounterStream) -> dict[tuple[int, int], float]:
        """5×5 egocentric 观测窗（Q-L01-01）：资源强度 × 距离增益 + 噪声（σ 固定，Q-L01-09⑥）。"""
        gains = self.params.observation_gain
        sigma = self.params.render_noise_sigma
        size = self.params.grid_size
        cx, cy = self._body_pos
        out: dict[tuple[int, int], float] = {}
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                x, y = (cx + dx) % size, (cy + dy) % size  # torus 视野
                patch = self._grid[y][x]
                strength = patch.resource_level / self.params.resource_max_level if patch.kind == "resource" else 0.0
                noise = (stream.next_float01() * 2.0 - 1.0) * sigma
                distance = max(abs(dx), abs(dy))
                value = max(0.0, min(1.0, strength * gains[f"d{distance}"] + noise))
                out[(dx, dy)] = value
        return out

    @staticmethod
    def expected_storm_bands(params: MW0Params, regime: str) -> int:
        """Q-G00-09① 派生：round(storm_rate × cells)（测试对照用）。"""
        regime_params = params.regime(regime)
        return round(regime_params.storm_rate_per_cycle * params.grid_size * params.grid_size)
