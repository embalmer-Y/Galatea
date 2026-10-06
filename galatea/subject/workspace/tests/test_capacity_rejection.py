"""容量约束与淘汰留痕（L07 §4.1/§7 capacity——Q-L07-01）。"""
from pathlib import Path

import pytest

from galatea.kernel.packet import RepresentationLevel
from galatea.subject.c2profile import C2WorkspaceParams
from galatea.subject.workspace.pipeline import WorkspacePipeline
from galatea.subject.workspace.ports import RejectionReason
from galatea.subject.workspace.propose import SalienceComponents, WorkspaceProposal

READERS = ("perception", "models", "affect", "memory")


def _prop(pid: str, goal: float, sponsor: str = "perception",
          level: RepresentationLevel = RepresentationLevel.PERCEIVED) -> WorkspaceProposal:
    return WorkspaceProposal(
        proposal_id=pid, content_ref=f"c.{pid}", source_level=level,
        salience=SalienceComponents(goal_relevance=goal, affect=0.2, novelty=0.2,
                                    uncertainty=0.1, info_value=0.2),
        sponsor_module=sponsor,
    )


def test_k_enforced_and_rejections_logged(ws_params: C2WorkspaceParams) -> None:
    """K=4 硬约束：6 提案 → 4 帧内 2 淘汰 OVER_CAPACITY（禁静默丢弃）。"""
    assert ws_params.capacity_k == 4
    pipe = WorkspacePipeline(ws_params, readers=READERS)
    for i in range(6):
        pipe.submit(_prop(f"p{i}", 0.1 * i, sponsor=READERS[i % 4]))
    out = pipe.run_competition(cycle=0)
    assert out is not None
    assert len(out.frame.items) == 4
    assert [r.reason for r in out.rejections] == [RejectionReason.OVER_CAPACITY] * 2
    assert all(r.score > 0 for r in out.rejections)


def test_low_salience_rejected(ws_params: C2WorkspaceParams) -> None:
    """全零分量 → LOW_SALIENCE（score ≤ 0 不占席位）。"""
    pipe = WorkspacePipeline(ws_params, readers=READERS)
    pipe.submit(WorkspaceProposal(
        proposal_id="zero", content_ref="c.zero", source_level=RepresentationLevel.PERCEIVED,
        salience=SalienceComponents(0, 0, 0, 0, 0), sponsor_module="perception"))
    out = pipe.run_competition(cycle=0)
    assert out is None   # 无入选不发布帧
    assert pipe.last_rejections[0].reason is RejectionReason.LOW_SALIENCE   # 淘汰留痕可见
    assert pipe.rejections_total == 1


def test_frame_items_capped_at_k(ws_params: C2WorkspaceParams) -> None:
    """帧构造面 K 上界机械强制（>4 即拒——容量是功能属性，L07 §8 不变量 3）。"""
    from galatea.subject.workspace.frame import WorkspaceItem, WorkspaceFrame

    items = tuple(WorkspaceItem(f"p{i}", f"c.{i}", RepresentationLevel.PERCEIVED, 1.0)
                  for i in range(5))
    with pytest.raises(ValueError):
        WorkspaceFrame(
            frame_id="f.x", cycle_id=0, items=items, competition_trace=(),
            source_levels=tuple(i.source_level for i in items),
            modulation_receipt_ids=(), ttl_cycles=4, recursion_depth=0,
        )
