"""Q-L06-08② procedural 只读引用不产生权限变化（REV-0022 R1③；gateway 依赖测试
居 tests/ 根域——P13/P04：主体平面内禁 import action.gateway，leakage 探针在案）。"""
import json
from pathlib import Path

from galatea.kernel.clock import CycleClock
from galatea.kernel.packet import ArtifactRef
from galatea.kernel.registry import Registry
from galatea.kernel.state import Stores
from galatea.subject.action.gateway import ActionSpec, CapabilityGateway, load_gateway_config
from galatea.subject.action.signature import derive_signing_key
from galatea.subject.control.intention import ActionIntention
from galatea.subject.learning.executor import promote
from galatea.subject.learning.proposal import DataScope, LearningProposal, ProposalKind


def test_procedural_reference_grants_no_capability(tmp_path: Path) -> None:
    stores = Stores(tmp_path / "stores")
    registry = Registry(tmp_path / "registry", stores, CycleClock())
    procedural = LearningProposal(
        proposal_id="prop.proc.1", target_artifact="procedural.routines",
        kind=ProposalKind.TABLE, parent_digest="b" * 64,
        data_scope=DataScope(("r1",), ("B",), (0, 32), 4),
        seed=0, rng_stream_ref="(learning,replay,prop.proc.1)",
        metrics_snapshot={"coverage": 4.0, "type_dims": 2.0},
        content={"routine_digest": "x" * 8},
    )
    receipt = promote(procedural, registry, decision_ref="dec" * 16, accepted_at_cycle=32)
    entry = registry.get(ArtifactRef(digest=receipt.activated_digest, kind="learning:artifact"))
    payload = json.loads(entry.blob)
    assert not any(k.lower() in ("capability", "permission", "policy") for k in payload)
    root = Path(__file__).resolve().parents[2]
    gw = CapabilityGateway(
        load_gateway_config(root / "config" / "profiles" / "m0_gateway.profile.yaml",
                            root / "config" / "profiles" / "f0_action_contract.profile.yaml"),
        derive_signing_key(b"proc-test"), run_id="R", branch_id="B", subject_candidate_id="S")
    _, cmd_fly = gw.authorize(
        ActionIntention("i-fly", "t", "t", 16, None, "fly1"), ActionSpec("fly", None),
        subject_candidate_id="S", run_id="R", branch_id="B", virtual_time=0)
    _, cmd_move = gw.authorize(
        ActionIntention("i-move", "t", "t", 16, None, "mv1"), ActionSpec("move", "N"),
        subject_candidate_id="S", run_id="R", branch_id="B", virtual_time=0)
    assert cmd_fly is None                      # procedural 在库不改变能力判定
    assert cmd_move is not None
    stores.close()
