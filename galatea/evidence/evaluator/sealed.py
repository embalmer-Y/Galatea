"""InternalValidationSet vs SealedScientificEvaluationSet 双类型隔离（L13 §4.3/§10 evaluator/sealed.py）。

合同：config/evidence/sealed_split_policy.yaml（Q-L13-02 CONFIRMED，F0 冻结 ADR-G-0002）。
- 分割：MW0 场景配置网格（regime × 种子）70% internal / 30% sealed，RNG 流
  ("l13","sealed-split") 一次性生成并记 digest（REV-0009 R3 缺口在本模块兑现；
  流派生 ⇒ 生成时刻不影响内容，digest 入册后可复算）；
- 隔离：独立命名空间 registry://sealed/ + 独立 token 类型（类型系统层面不可互换；
  Pydantic discriminated union 的等效机械形式 = 构造期 isinstance 断言）；
- 不回流：候选 data_scope digest 集 ∩ sealed digest 集 = ∅（promotion 第①步强制，
  归 C5 流程；本模块交付机械判据 check_no_backflow）；
- read policy：sealed 内容仅 promotion_gate_evaluation 上下文可读，违规 =
  SealedContamination（S1）；轮换仅门边界，退役转 EVALUATION_RETIRED 永久退出训练侧。
"""
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

import yaml

from galatea.kernel.digest import content_digest
from galatea.kernel.packet import ArtifactRef
from galatea.kernel.registry import Registry, RegistryEntry
from galatea.kernel.rng import RngDirectory, chacha8_block

__all__ = [
    "GridCell",
    "InternalValidationToken",
    "SealedEvaluationToken",
    "InternalValidationSet",
    "SealedScientificEvaluationSet",
    "SplitResult",
    "SealedNamespace",
    "SealedContamination",
    "generate_split",
    "load_split_policy",
    "check_no_backflow",
]

SEALED_KIND_PREFIX = "sealed:"
ALLOWED_READ_CONTEXT = "promotion_gate_evaluation"   # read_policy.allowed_context（合同原文）
_STATUS_ACTIVE = "ACTIVE"
_STATUS_RETIRED = "EVALUATION_RETIRED"               # rotation.retired_to（合同原文）
_POLICY_PATH = Path("config") / "evidence" / "sealed_split_policy.yaml"


class SealedContamination(RuntimeError):
    """sealed 隔离违规（Q-L13-02：S1——非评价上下文读取/类型混用/回流检出/退役复用）。"""


@dataclass(frozen=True, slots=True)
class GridCell:
    """MW0 场景配置网格单元（unit: mw0_scenario_config）= regime × 种子槽位。"""

    cell_id: str        # f"{regime}:{seed_index}"
    regime: str
    seed_index: int

    def digest_input(self) -> dict[str, Any]:
        return {"cell_id": self.cell_id, "regime": self.regime, "seed_index": self.seed_index}


@dataclass(frozen=True, slots=True)
class InternalValidationToken:
    """internal 集 token（与 sealed token 不同类型——混用即 SealedContamination）。"""

    split_digest: str


@dataclass(frozen=True, slots=True)
class SealedEvaluationToken:
    """sealed 评价 token：仅 promotion_gate_evaluation 上下文可签发（read_policy）。"""

    split_digest: str
    context: str

    def __post_init__(self) -> None:
        if self.context != ALLOWED_READ_CONTEXT:
            raise SealedContamination(
                f"sealed token context must be {ALLOWED_READ_CONTEXT!r}, got {self.context!r}（read_policy.violation）"
            )


@dataclass(frozen=True, slots=True)
class InternalValidationSet:
    """internal 70% 集（训练侧可见）。token 类型错误 = SealedContamination（类型不可互换）。"""

    cells: tuple[GridCell, ...]
    token: InternalValidationToken
    split_digest: str
    status: str = _STATUS_ACTIVE

    def __post_init__(self) -> None:
        if type(self.token) is not InternalValidationToken:   # 精确类型（禁子类别名混用）
            raise SealedContamination(
                f"InternalValidationSet requires InternalValidationToken, got {type(self.token).__name__}"
            )
        if self.token.split_digest != self.split_digest:
            raise SealedContamination("token split_digest mismatch")


@dataclass(frozen=True, slots=True)
class SealedScientificEvaluationSet:
    """sealed 30% 集：训练侧永不可见；cells 仅凭本集 token 在评价上下文读出。"""

    cells: tuple[GridCell, ...]
    token: SealedEvaluationToken
    split_digest: str
    status: str = _STATUS_ACTIVE

    def __post_init__(self) -> None:
        if type(self.token) is not SealedEvaluationToken:   # 精确类型（禁子类别名混用）
            raise SealedContamination(
                f"SealedScientificEvaluationSet requires SealedEvaluationToken, got {type(self.token).__name__}"
            )
        if self.token.split_digest != self.split_digest:
            raise SealedContamination("token split_digest mismatch")

    def cells_view(self, token: SealedEvaluationToken) -> tuple[GridCell, ...]:
        """评价上下文读取（token 重呈 + 状态校验；退役集任何读取 = SealedContamination）。"""
        if type(token) is not SealedEvaluationToken:
            raise SealedContamination(
                f"sealed cells view requires SealedEvaluationToken, got {type(token).__name__}"
            )
        if token.split_digest != self.split_digest or token.context != ALLOWED_READ_CONTEXT:
            raise SealedContamination("sealed read token mismatch（read_policy.violation）")
        if self.status != _STATUS_ACTIVE:
            raise SealedContamination(
                f"sealed set status {self.status}: retired sets never re-enter evaluation（rotation.retired_reuse）"
            )
        return self.cells

    def training_view(self) -> None:
        """训练侧读取 = 一律 SealedContamination（internal ≠ sealed，L13 不变量 1）。"""
        raise SealedContamination("sealed set has no training-side view（no_backflow）")

    def retire(self) -> "SealedScientificEvaluationSet":
        """轮换（仅门边界，调用方纪律）：转 EVALUATION_RETIRED，永久退出训练与评价侧。"""
        return replace(self, status=_STATUS_RETIRED)


@dataclass(frozen=True, slots=True)
class SplitResult:
    """一次分割的产物：两集 + 分割身份 digest（入 registry 的 digest_recorded 载体）。"""

    internal: InternalValidationSet
    sealed: SealedScientificEvaluationSet
    split_digest: str
    manifest_ref: ArtifactRef | None = None   # SealedNamespace.put 成功后回填


def load_split_policy(root: Path) -> dict[str, Any]:
    """加载 F0 冻结分割策略（fail-closed：缺关键节即拒）。"""
    path = root / _POLICY_PATH
    if not path.is_file():
        raise SealedContamination(f"sealed split policy not found: {path}")
    raw = cast(dict[str, Any], yaml.safe_load(path.read_text(encoding="utf-8")))
    for key in ("split", "generation", "isolation", "no_backflow", "read_policy"):
        if key not in raw:
            raise SealedContamination(f"sealed split policy missing section: {key}")
    return raw


def generate_split(
    grid: tuple[GridCell, ...], master_seed: bytes, policy: dict[str, Any]
) -> SplitResult:
    """流派生分割（generation.rng_stream 合同）：确定性、可复算、先于一切评价。

    分割身份 digest = 网格 + 种子 + 比例 + 流名的 canonical JSON（digest_recorded 的
    被记录对象）；sealed 成员判定 = 流 uint64 % 100 < sealed%×100（合同 split.sealed）。
    """
    internal_frac = float(cast(dict[str, Any], policy["split"])["internal"])
    sealed_frac = float(cast(dict[str, Any], policy["split"])["sealed"])
    stream_name = tuple(
        cast(list[str], cast(dict[str, Any], policy["generation"])["rng_stream"])
    )
    if abs(internal_frac + sealed_frac - 1.0) > 1e-9:
        raise SealedContamination("split fractions must sum to 1")
    sealed_pct = round(sealed_frac * 100)
    rng = RngDirectory(master_seed, chacha8_block)
    stream = rng.stream("B", stream_name[0], stream_name[1])
    sealed_cells: list[GridCell] = []
    internal_cells: list[GridCell] = []
    for cell in grid:
        if stream.next_uint64() % 100 < sealed_pct:
            sealed_cells.append(cell)
        else:
            internal_cells.append(cell)
    split_digest = content_digest(
        {
            "master_seed_hex": master_seed.hex(),
            "stream": list(stream_name),
            "sealed_fraction": sealed_frac,
            "grid": [c.digest_input() for c in grid],
            "sealed_cells": [c.cell_id for c in sealed_cells],
            "internal_cells": [c.cell_id for c in internal_cells],
        }
    )
    internal = InternalValidationSet(
        cells=tuple(internal_cells), token=InternalValidationToken(split_digest), split_digest=split_digest
    )
    sealed = SealedScientificEvaluationSet(
        cells=tuple(sealed_cells),
        token=SealedEvaluationToken(split_digest, ALLOWED_READ_CONTEXT),
        split_digest=split_digest,
    )
    return SplitResult(internal=internal, sealed=sealed, split_digest=split_digest)


class SealedNamespace:
    """registry://sealed/ 命名空间视图（isolation.namespace 合同）。

    put 仅接受 `sealed:` 前缀 kind（命名空间纪律）；get 必须呈交合法
    SealedEvaluationToken（非评价上下文读取 = SealedContamination）；retire 后
    整个命名空间封闭（旧 sealed 永久退出训练侧，retired_reuse: never）。
    """

    def __init__(self, registry: Registry, split_digest: str) -> None:
        self._registry = registry
        self._split_digest = split_digest
        self._status = _STATUS_ACTIVE
        self._digests: frozenset[str] = frozenset()

    @property
    def split_digest(self) -> str:
        return self._split_digest

    @property
    def data_digests(self) -> frozenset[str]:
        """sealed digest 集（no_backflow 判据右边的集合；put 后累积）。"""
        return self._digests

    def put(self, blob: bytes, kind: str, parent_digests: tuple[str, ...] = ()) -> ArtifactRef:
        if self._status != _STATUS_ACTIVE:
            raise SealedContamination("sealed namespace is retired: no further writes")
        if not kind.startswith(SEALED_KIND_PREFIX):
            raise SealedContamination(
                f"sealed namespace accepts only {SEALED_KIND_PREFIX!r}-prefixed kinds, got {kind!r}"
            )
        ref = self._registry.put(blob, kind, parent_digests)
        self._digests = frozenset(set(self._digests) | {ref.digest})
        return ref

    def get(self, ref: ArtifactRef, token: SealedEvaluationToken) -> RegistryEntry:
        if self._status != _STATUS_ACTIVE:
            raise SealedContamination(
                f"sealed namespace retired ({self._status}): retired sets never re-enter evaluation"
            )
        if type(token) is not SealedEvaluationToken:
            raise SealedContamination(
                f"sealed read requires SealedEvaluationToken, got {type(token).__name__}"
            )
        if token.split_digest != self._split_digest or token.context != ALLOWED_READ_CONTEXT:
            raise SealedContamination("sealed read token mismatch（read_policy.violation）")
        entry = self._registry.get(ref)
        if not str(entry.manifest.get("kind", "")).startswith(SEALED_KIND_PREFIX):
            raise SealedContamination(f"non-sealed kind under sealed namespace: {entry.manifest.get('kind')!r}")
        return entry

    def retire(self) -> None:
        """门边界轮换：命名空间封闭（读/写均拒）。"""
        self._status = _STATUS_RETIRED


def check_no_backflow(candidate_scope_digests: frozenset[str] | set[str], sealed_digests: frozenset[str] | set[str]) -> None:
    """不回流机械判据（no_backflow.criterion：data_scope digest 交集 = ∅）。

    promotion 流程第①步（registry 查询）在 C5 接线；任何交集 = SealedContamination
    （S1，作废该 promotion）。R0 起所有引用 sealed 数据的评价在签发前必须过本判据。
    """
    intersection = set(candidate_scope_digests) & set(sealed_digests)
    if intersection:
        sample = ", ".join(sorted(intersection)[:3])
        raise SealedContamination(
            f"no_backflow violated: candidate data_scope shares {len(intersection)} digest(s) with sealed set [{sample}…]"
        )
