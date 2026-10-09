"""REV-0022 R1 硬前置三项闭环测试（E1 消费 promoted 工件前必须全绿）。"""
import json
from pathlib import Path

import pytest

from galatea.kernel.clock import CycleClock
from galatea.kernel.packet import ArtifactRef
from galatea.kernel.registry import Registry
from galatea.kernel.state import Stores
from galatea.subject.learning.executor import promote
from galatea.subject.learning.proposal import DataScope, LearningProposal, ProposalKind
from galatea.subject.memory.consolidate import TypeCounts, consolidate_types


@pytest.fixture()
def registry(tmp_path: Path) -> Registry:
    stores = Stores(tmp_path / "stores")
    reg = Registry(tmp_path / "registry", stores, CycleClock())
    yield reg
    stores.close()


def _proposal() -> LearningProposal:
    counts = TypeCounts(counts={"resource": 40, "empty": 60},
                        positives={"resource": 30, "empty": 10})
    return consolidate_types(counts, {"resource": 0.35, "empty": 0.65},
                             "prop.exec.1", "d" * 64, "r1", 63)


def test_accepted_executor_produces_receipt_and_registry_artifact(registry: Registry) -> None:
    """执行器三步：registry 入库（谱系 = parent）+ 回执三元组 + digest 稳定。"""
    proposal = _proposal()
    receipt = promote(proposal, registry, decision_ref="dec" * 16, accepted_at_cycle=128)
    assert receipt.proposal_digest == proposal.content_digest
    assert receipt.parent_digest == "d" * 64
    assert receipt.decision_ref == "dec" * 16
    entry = registry.get(ArtifactRef(digest=receipt.activated_digest, kind="learning:artifact"))
    parsed = json.loads(entry.blob)
    assert set(parsed) == set(proposal.content)   # 工件内容 = 提案 content 全量
    # 幂等：同提案再 promote → 同 activated digest（内容寻址）
    receipt2 = promote(proposal, registry, decision_ref="dec" * 16, accepted_at_cycle=129)
    assert receipt2.activated_digest == receipt.activated_digest


def test_consolidate_uses_frequency_semantics_end_to_end(registry: Registry) -> None:
    """频率面语义端到端（REV-0022 R1②：执行器消费的提案必须已是频率面）。"""
    proposal = _proposal()
    # R1②：执行器消费的提案须域内合法（类内 Laplace (8×0.35+30)/48 = 0.6833——
    # runs_c5 消费面已修频率面语义；此处钉死域保持 + 非循环定义（≠0.99 饱和面））
    assert 0.0 < proposal.content["resource"] < 1.0
    assert proposal.content["resource"] < 0.95   # 非类内循环定义饱和面
    receipt = promote(proposal, registry, decision_ref="dec" * 16, accepted_at_cycle=64)
    assert len(receipt.receipt_digest) == 64
