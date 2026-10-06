"""ModulationField 发放、有界、TTL 与回执台账（L05 §4.4/§10 modulation.py，C2 实现期）。

合同（c2_affect.profile §modulation + Q-L02-02/Q-L07-02）：
- **有界**：调制因子界 [0.5, 2.0]（2 的幂，Q-G00-08；believe_threshold 界 =
  0.5 ± band = [0.4, 0.6]——域内平移带，零新常数）；越界由目标模块裁剪并记
  bound_check=CLIPPED（正常路径非错误）；requested/applied 必须成对呈现；
- **TTL**：全部 C2 调制 TTL = 4 cycles（Q-L07-04② 同锚：2×N2 竞争拍——帧
  生命期与调制生命期一致）；到期自动归零，禁常驻调制；
- **必回执**：TTL 内无回执 = 调制**未发生**（evaluator 不得采信——L05 §6 行 3）。

发放门（迟滞 center=0.5、band=0.1，ADR-G-0015 层A 迟滞算子应用面——防抖动）：
- SENSORIUM.gain：arousal 过门 ON → requested = 2.0（界端点，量化发放零自由参数）；
- PERCEPTION.believe_threshold：uncertainty 过门 ON → requested = 0.6（保守方向
  = 高不确定时**提高**承诺阈；重开条件 C3 元控制复核）；
- WORKSPACE.salience：novelty 过门 ON → affect 分量因子 2.0（消费面 = L07 C2 次单元）。

**唯一对外作用通道**（L05 §8 不变量 3）：本模块之外不存在 affect 对外写路径。
"""
import enum
from dataclasses import dataclass

from galatea.kernel.digest import content_digest
from galatea.subject.affect.dynamics import hysteresis

__all__ = [
    "ModulationTarget",
    "ModulationField",
    "ModulationReceiptRecord",
    "ModulationStatus",
    "ModulationLedger",
    "FACTOR_BOUND",
    "BELIEVE_THRESHOLD_BOUND",
    "MODULATION_TTL_CYCLES",
    "issue_modulations",
]


class ModulationTarget(enum.StrEnum):
    """调制目标六类（L05 §4.4 冻结枚举 = c2_affect.profile modulation_class_enum）。"""

    SENSORIUM = "SENSORIUM"
    PERCEPTION = "PERCEPTION"
    WORLD_MODEL = "WORLD_MODEL"
    MEMORY_ENCODER = "MEMORY_ENCODER"
    WORKSPACE = "WORKSPACE"
    METACONTROL = "METACONTROL"


#: 因子界（Q-L02-02①/Q-L07-02②：[0.5, 2.0]，2 的幂）
FACTOR_BOUND: tuple[float, float] = (0.5, 2.0)
#: believe_threshold 界 = 0.5 ± band（Q-L03-02 阈 0.5 + Q-L05-03③ band 0.1）
BELIEVE_THRESHOLD_BOUND: tuple[float, float] = (0.4, 0.6)
#: TTL（Q-L07-04② 同锚：2×N2=4 cycles；帧/去重/调制生命期一致）
MODULATION_TTL_CYCLES: int = 4

#: 发放门中心与带宽（ADR-G-0015 层A 迟滞算子：ON ≥ 0.55 / OFF ≤ 0.45）
GATE_CENTER: float = 0.5


@dataclass(frozen=True, slots=True)
class ModulationField:
    """单次调制发放（L05 §4.4：target/dimension/requested/bound_ref/ttl/reason）。"""

    modulation_id: str
    target: ModulationTarget
    dimension: str                  # "gain" | "believe_threshold" | "salience.affect"
    requested_value: float
    bound_ref: str
    ttl_cycles: int
    issued_at: int
    reason: tuple[str, ...]         # AppraisalEvidenceRefs
    receipt_expected: bool = True

    def __post_init__(self) -> None:
        if self.ttl_cycles < 1:
            raise ValueError("ttl_cycles must be >= 1（禁永久调制，L05 §4.4）")
        if not self.receipt_expected:
            raise ValueError("receipt_expected 恒 True（L05 §6 行 3：无回执调制 = 未发生）")
        if self.dimension == "believe_threshold":
            if not BELIEVE_THRESHOLD_BOUND[0] <= self.requested_value <= BELIEVE_THRESHOLD_BOUND[1]:
                raise ValueError(f"believe_threshold out of bound {BELIEVE_THRESHOLD_BOUND}")
        elif self.dimension in ("gain", "salience.affect"):
            if not FACTOR_BOUND[0] <= self.requested_value <= FACTOR_BOUND[1]:
                raise ValueError(f"factor out of bound {FACTOR_BOUND}")


class ModulationStatus(enum.StrEnum):
    """台账状态（回执核：TTL 内未回执 = 未发生）。"""

    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"           # applied 值回执在案（evaluator 可采信 applied）
    EXPIRED_UNCONFIRMED = "EXPIRED_UNCONFIRMED"   # TTL 尽无回执 → 未发生


@dataclass(frozen=True, slots=True)
class ModulationReceiptRecord:
    """回执记录（目标模块回执的 affect 侧登记）。"""

    modulation_id: str
    accepted: bool
    applied_value: float
    bound_check: str                  # IDENTITY | CLIPPED
    received_at: int


@dataclass
class ModulationLedger:
    """调制发放台账（L05 §3 单写者 = Affect Dynamics；evaluator 只读）。"""

    _fields: dict[str, ModulationField]
    _receipts: dict[str, ModulationReceiptRecord]

    def __init__(self) -> None:
        self._fields = {}
        self._receipts = {}

    def issue(self, field_obj: ModulationField) -> ModulationField:
        """登记发放（重复 id 即拒——确定性 id 纪律）。"""
        if field_obj.modulation_id in self._fields:
            raise ValueError(f"duplicate modulation_id: {field_obj.modulation_id!r}")
        self._fields[field_obj.modulation_id] = field_obj
        return field_obj

    def record_receipt(self, rec: ModulationReceiptRecord) -> None:
        """回执登记（未知 id = 违约——目标模块只能回执已发放调制）。"""
        if rec.modulation_id not in self._fields:
            raise ValueError(f"receipt for unknown modulation: {rec.modulation_id!r}")
        self._receipts[rec.modulation_id] = rec

    def settle(self, cycle: int) -> dict[str, ModulationStatus]:
        """TTL 结算：CONFIRMED（TTL 内回执）/ EXPIRED_UNCONFIRMED（TTL 尽无回执 = 未发生）。

        过期后补回执不复活（Q-L07-03③ 禁重试同源——received_at > issued+ttl−1 的
        回执只作审计留痕，不改变"未发生"结算）。
        """
        out: dict[str, ModulationStatus] = {}
        for mid, f in self._fields.items():
            rec = self._receipts.get(mid)
            in_time = rec is not None and rec.received_at < f.issued_at + f.ttl_cycles
            if in_time:
                out[mid] = ModulationStatus.CONFIRMED
            elif cycle >= f.issued_at + f.ttl_cycles:
                out[mid] = ModulationStatus.EXPIRED_UNCONFIRMED
            else:
                out[mid] = ModulationStatus.PENDING
        return out

    def confirmed_fields(self, cycle: int) -> tuple[ModulationField, ...]:
        """已确认调制（evaluator 可采信集——只有这些"发生过"）。"""
        st = self.settle(cycle)
        return tuple(f for mid, f in sorted(self._fields.items()) if st[mid] is ModulationStatus.CONFIRMED)

    def digest(self) -> str:
        """台账 digest（checkpoint/重放载体）。"""
        return content_digest({
            "fields": {mid: [f.target.value, f.dimension, f.requested_value, f.ttl_cycles, f.issued_at]
                       for mid, f in sorted(self._fields.items())},
            "receipts": {mid: [r.accepted, r.applied_value, r.bound_check, r.received_at]
                         for mid, r in sorted(self._receipts.items())},
        })


@dataclass(frozen=True, slots=True)
class ModulationGates:
    """三类发放门状态（迟滞保持跨拍——AffectPipeline 持有）。"""

    gain_on: bool = False
    threshold_on: bool = False
    salience_on: bool = False


def issue_modulations(
    gates: ModulationGates,
    arousal: float,
    uncertainty: float,
    novelty: float,
    band: float,
    cycle: int,
    evidence_refs: tuple[str, ...],
    ledger: ModulationLedger | None = None,
    enabled: frozenset[str] = frozenset({"gain", "believe_threshold", "salience"}),
) -> tuple[ModulationGates, tuple[ModulationField, ...]]:
    """单拍发放决策（确定性；enabled = 消融面——空集即全关，Q-L05 §7 modulation causality）。

    门 = 迟滞算子（center 0.5 / band——层A 规格同参）；ON 时发放界端点量化值。
    """
    new_gates = ModulationGates(
        gain_on=hysteresis(gates.gain_on, arousal, band, GATE_CENTER),
        threshold_on=hysteresis(gates.threshold_on, uncertainty, band, GATE_CENTER),
        salience_on=hysteresis(gates.salience_on, novelty, band, GATE_CENTER),
    )
    bound_ref = "c2_affect.profile@v1.0/modulation"
    issued: list[ModulationField] = []
    if "gain" in enabled and new_gates.gain_on:
        issued.append(ModulationField(
            modulation_id=f"mod.gain.{cycle}", target=ModulationTarget.SENSORIUM,
            dimension="gain", requested_value=FACTOR_BOUND[1], bound_ref=bound_ref,
            ttl_cycles=MODULATION_TTL_CYCLES, issued_at=cycle, reason=evidence_refs,
        ))
    if "believe_threshold" in enabled and new_gates.threshold_on:
        issued.append(ModulationField(
            modulation_id=f"mod.threshold.{cycle}", target=ModulationTarget.PERCEPTION,
            dimension="believe_threshold", requested_value=BELIEVE_THRESHOLD_BOUND[1],
            bound_ref=bound_ref, ttl_cycles=MODULATION_TTL_CYCLES, issued_at=cycle,
            reason=evidence_refs,
        ))
    if "salience" in enabled and new_gates.salience_on:
        issued.append(ModulationField(
            modulation_id=f"mod.salience.{cycle}", target=ModulationTarget.WORKSPACE,
            dimension="salience.affect", requested_value=FACTOR_BOUND[1], bound_ref=bound_ref,
            ttl_cycles=MODULATION_TTL_CYCLES, issued_at=cycle, reason=evidence_refs,
        ))
    if ledger is not None:
        for f in issued:
            ledger.issue(f)
    return new_gates, tuple(issued)
