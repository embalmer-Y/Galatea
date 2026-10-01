"""sealed 双类型隔离与流派生分割（L13 §4.3/§7；Q-L13-02；sealed_split_policy.yaml F0 合同）。

关键纪律：internal ≠ sealed（不同类型/token/命名空间）；分割确定性可复算；
token 仅 promotion_gate_evaluation 上下文可签发。
"""
from pathlib import Path

import pytest

from galatea.evidence.evaluator.sealed import (
    GridCell,
    InternalValidationSet,
    InternalValidationToken,
    SealedContamination,
    SealedEvaluationToken,
    SealedNamespace,
    SealedScientificEvaluationSet,
    generate_split,
    load_split_policy,
)
from galatea.kernel.clock import CycleClock
from galatea.kernel.registry import Registry
from galatea.kernel.state import Stores

_ROOT = Path(__file__).resolve().parents[3]
MASTER_SEED = bytes.fromhex("aa" * 32)


def _grid(regimes: tuple[str, ...] = ("abundance", "scarcity", "volatile"), seeds: int = 32) -> tuple[GridCell, ...]:
    return tuple(GridCell(cell_id=f"{r}:{i}", regime=r, seed_index=i) for r in regimes for i in range(seeds))


def _namespace(tmp_path: Path, split_digest: str) -> SealedNamespace:
    stores = Stores(tmp_path / "stores")
    return SealedNamespace(Registry(tmp_path / "registry", stores, CycleClock()), split_digest)


def test_split_deterministic_and_recomputable() -> None:
    policy = load_split_policy(_ROOT)
    a = generate_split(_grid(), MASTER_SEED, policy)
    b = generate_split(_grid(), MASTER_SEED, policy)
    c = generate_split(_grid(), bytes.fromhex("bb" * 32), policy)
    assert a.split_digest == b.split_digest                       # 同种子可复算（Q-L13-02）
    assert [x.cell_id for x in a.sealed.cells] == [x.cell_id for x in b.sealed.cells]
    assert a.split_digest != c.split_digest                       # 异种子分割不同
    assert {x.cell_id for x in a.sealed.cells}.isdisjoint({x.cell_id for x in a.internal.cells})
    assert len(a.sealed.cells) + len(a.internal.cells) == len(_grid())


def test_split_fraction_nominal_70_30() -> None:
    policy = load_split_policy(_ROOT)
    result = generate_split(_grid(seeds=100), MASTER_SEED, policy)   # 300 cell 大样本
    frac = len(result.sealed.cells) / 300
    assert 0.20 <= frac <= 0.40                                     # 名义 30%（粗界；小样本涨落容许）


def test_token_types_not_interchangeable() -> None:
    policy = load_split_policy(_ROOT)
    result = generate_split(_grid(), MASTER_SEED, policy)
    with pytest.raises(SealedContamination):
        InternalValidationSet(                                      # internal 集不得持 sealed token
            cells=result.internal.cells, token=result.sealed.token, split_digest=result.internal.split_digest
        )
    with pytest.raises(SealedContamination):
        SealedScientificEvaluationSet(                              # sealed 集不得持 internal token
            cells=result.sealed.cells, token=result.internal.token, split_digest=result.sealed.split_digest
        )
    with pytest.raises(SealedContamination):
        result.sealed.cells_view(result.internal.token)             # cells 读取仅收 sealed token
    with pytest.raises(SealedContamination):
        result.sealed.training_view()                               # 训练侧视图不存在（不变量 1）
    with pytest.raises(SealedContamination):
        result.sealed.cells_view(SealedEvaluationToken(result.sealed.split_digest, "training"))


def test_token_forgery_rejected() -> None:
    """非评价上下文签发 token = SealedContamination（read_policy.violation）。"""
    with pytest.raises(SealedContamination):
        SealedEvaluationToken("any", "training")
    with pytest.raises(SealedContamination):
        SealedEvaluationToken("any", "subject_session")


def test_split_digest_mismatch_rejected() -> None:
    policy = load_split_policy(_ROOT)
    result = generate_split(_grid(), MASTER_SEED, policy)
    with pytest.raises(SealedContamination):
        result.sealed.cells_view(SealedEvaluationToken("other-split", "promotion_gate_evaluation"))


def test_retired_sealed_set_never_reenters_evaluation() -> None:
    policy = load_split_policy(_ROOT)
    result = generate_split(_grid(), MASTER_SEED, policy)
    retired = result.sealed.retire()
    assert retired.status == "EVALUATION_RETIRED"
    token = SealedEvaluationToken(retired.split_digest, "promotion_gate_evaluation")
    with pytest.raises(SealedContamination):
        retired.cells_view(token)                # 退役集评价侧复用 = 拒
    assert result.internal.cells                 # internal 集不受轮换影响
