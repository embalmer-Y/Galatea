"""回执/watch/effective_access/递归/层级/no-execution/伪判据（L07 §7 合同面）。"""
import importlib
import sys

import pytest

from galatea.kernel.packet import RepresentationLevel
from galatea.kernel.unknown import Unknown
from galatea.subject.c2profile import C2WorkspaceParams
from galatea.subject.workspace.broadcast import ReadReceipt
from galatea.subject.workspace.pipeline import WorkspacePipeline
from galatea.subject.workspace.ports import PostHocWatchRejected, StaleFrameReference
from galatea.subject.workspace.pseudo_check import PseudoWorkspaceSuspect, pseudo_workspace_check
from galatea.subject.workspace.propose import SalienceComponents, WorkspaceProposal
from galatea.subject.workspace.watch import WatchPointUpdate

READERS = ("perception", "models", "affect", "memory")


def _prop(pid: str, goal: float = 0.5, sponsor: str = "perception") -> WorkspaceProposal:
    return WorkspaceProposal(
        proposal_id=pid, content_ref=f"c.{pid}", source_level=RepresentationLevel.PERCEIVED,
        salience=SalienceComponents(goal, 0.3, 0.3, 0.2, 0.2), sponsor_module=sponsor,
    )


def _receipt(pipe: WorkspacePipeline, frame_id: str, module: str, changed: bool, at: int) -> None:
    pipe.submit_read_receipt(ReadReceipt(
        frame_id=frame_id, reader_module=module, read_at=at,
        pre_state_digest="d0", post_state_digest="d1" if changed else "d0",
        effect_declared=changed,
    ))


def _watch(pipe: WorkspacePipeline, frame_id: str, module: str, changed: bool, at: int) -> None:
    pipe.submit_watch_update(WatchPointUpdate(
        watch_id=f"watch.{module}", module=module, changed=changed,
        digest_before="d0", digest_after="d1" if changed else "d0",
        pre_registered=True, at_cycle=at,
    ), frame_id=frame_id)


def _run_frame(pipe: WorkspacePipeline, cycle: int, n: int = 2):
    for i in range(n):
        pipe.submit(_prop(f"p{cycle}.{i}", 0.4 + 0.1 * i))
    return pipe.run_competition(cycle=cycle)


# ------------------------------------------------------------------ 回执
def test_missing_receipt_excluded_from_access(ws_params: C2WorkspaceParams) -> None:
    """缺回执读者不计入——回执 <2 → effective_access=false（如实呈现禁美化）。"""
    pipe = WorkspacePipeline(ws_params, readers=READERS)
    out = _run_frame(pipe, 0)
    assert out is not None
    _receipt(pipe, out.frame.frame_id, "perception", True, 1)     # 仅 1 回执
    _watch(pipe, out.frame.frame_id, "perception", True, 1)
    _watch(pipe, out.frame.frame_id, "models", True, 1)
    ev = pipe.settle(out.frame.frame_id, now_cycle=2)
    assert ev.effective_access is False and ev.receipts_count == 1
    assert "no causal access" in ev.note


def test_late_receipt_not_counted(ws_params: C2WorkspaceParams) -> None:
    """超时回执（read_at > deadline = 帧拍 + N2）不计入（Q-L07-03①）。"""
    pipe = WorkspacePipeline(ws_params, readers=READERS)
    out = _run_frame(pipe, 0)
    assert out is not None
    _receipt(pipe, out.frame.frame_id, "perception", True, at=10)   # deadline = 0+2 → 迟到
    _receipt(pipe, out.frame.frame_id, "models", True, at=1)
    ev = pipe.settle(out.frame.frame_id, now_cycle=10)
    assert ev.receipts_count == 1


def test_effective_access_requires_two_separated(ws_params: C2WorkspaceParams) -> None:
    """对照（L07 §7 effective access）：≥2 分离模块预注册变化 → true；单模块 → false。"""
    pipe = WorkspacePipeline(ws_params, readers=READERS)
    out = _run_frame(pipe, 0)
    assert out is not None
    for m in READERS:
        _receipt(pipe, out.frame.frame_id, m, True, 1)
        _watch(pipe, out.frame.frame_id, m, True, 1)
    ev = pipe.settle(out.frame.frame_id, now_cycle=2)
    assert ev.effective_access is True
    assert set(ev.separated_modules) == {"perception_L03", "models_L04", "affect_L05", "memory_L06"}

    pipe2 = WorkspacePipeline(ws_params, readers=READERS)
    out2 = _run_frame(pipe2, 0)
    assert out2 is not None
    for m in READERS:
        _receipt(pipe2, out2.frame.frame_id, m, m == "perception", 1)
        _watch(pipe2, out2.frame.frame_id, m, m == "perception", 1)
    ev2 = pipe2.settle(out2.frame.frame_id, now_cycle=2)
    assert ev2.effective_access is False and ev2.separated_watch_changes == 1


def test_broadcast_without_updates_is_not_access(ws_params: C2WorkspaceParams) -> None:
    """广播但读者被禁更新 → effective_access=false（L07 §7 构造对照原文）。"""
    pipe = WorkspacePipeline(ws_params, readers=READERS)
    out = _run_frame(pipe, 0)
    assert out is not None
    for m in READERS:
        _receipt(pipe, out.frame.frame_id, m, False, 1)   # 回执在案但无效果
    ev = pipe.settle(out.frame.frame_id, now_cycle=2)
    assert ev.effective_access is False and ev.receipts_count == 4


# ------------------------------------------------------------------ watch
def test_posthoc_watch_rejected(ws_params: C2WorkspaceParams) -> None:
    """事后注册/未注册 watch 更新 = PostHocWatchRejected（评价诚信 S2 面）。"""
    pipe = WorkspacePipeline(ws_params, readers=READERS)
    out = _run_frame(pipe, 0)
    assert out is not None
    with pytest.raises(PostHocWatchRejected):
        pipe.submit_watch_update(WatchPointUpdate(
            watch_id="watch.perception", module="perception", changed=True,
            digest_before="d0", digest_after="d1", pre_registered=False, at_cycle=1,
        ), frame_id=out.frame.frame_id)
    with pytest.raises(PostHocWatchRejected):
        pipe.submit_watch_update(WatchPointUpdate(
            watch_id="watch.unregistered", module="perception", changed=True,
            digest_before="d0", digest_after="d1", pre_registered=True, at_cycle=1,
        ), frame_id=out.frame.frame_id)
    with pytest.raises(ValueError):
        pipe.submit_watch_update(WatchPointUpdate(    # changed 与 digest 变化不一致
            watch_id="watch.perception", module="perception", changed=False,
            digest_before="d0", digest_after="d1", pre_registered=True, at_cycle=1,
        ), frame_id=out.frame.frame_id)


# ------------------------------------------------------------------ 递归
def test_recursion_depth_gate(ws_params: C2WorkspaceParams) -> None:
    """depth > 3 → Unknown(CAPABILITY_LIMIT) 不产帧（递归是能力不是无限自我激励）。"""
    pipe = WorkspacePipeline(ws_params, readers=READERS)
    pipe.submit(_prop("r1"))
    out = pipe.run_competition(cycle=0, depth=4)
    assert isinstance(out, Unknown)   # depth 4 > depth_max 3（Q-L07-04①）
    pipe2 = WorkspacePipeline(ws_params, readers=READERS)
    pipe2.submit(_prop("r2"))
    out2 = pipe2.run_competition(cycle=0, depth=3)
    assert out2 is not None and out2.frame.recursion_depth == 3   # depth=3 合法（上界含）


def test_dedup_window_and_stale_frame(ws_params: C2WorkspaceParams) -> None:
    """同内容去重窗 TTL=4 内 DUPLICATE；过期帧引用 = StaleFrameReference。"""
    pipe = WorkspacePipeline(ws_params, readers=READERS)
    pipe.submit(_prop("dup", goal=0.9))
    out = pipe.run_competition(cycle=0)
    assert out is not None
    pipe.submit(_prop("dup.again", goal=0.9))   # 同 content? content_ref 不同——用同内容提案
    from galatea.subject.workspace.propose import WorkspaceProposal as WP
    pipe.submit(WP(
        proposal_id="dup.2", content_ref="c.dup", source_level=RepresentationLevel.PERCEIVED,
        salience=SalienceComponents(0.9, 0.3, 0.3, 0.2, 0.2), sponsor_module="perception"))
    out2 = pipe.run_competition(cycle=1)
    assert out2 is None or all(r.reason.value == "DUPLICATE" for r in pipe.last_rejections)
    frame = pipe.frame(out.frame.frame_id)
    with pytest.raises(StaleFrameReference):
        from galatea.subject.workspace.recurse import assert_frame_current
        assert_frame_current(frame, cycle=0 + ws_params.frame_ttl_cycles)


# ------------------------------------------------------------------ 层级/禁径
def test_level_inheritance(ws_params: C2WorkspaceParams) -> None:
    """帧 source_levels 逐项 = 提案层级（不提升——RECALLED 入帧恒 RECALLED）。"""
    pipe = WorkspacePipeline(ws_params, readers=READERS)
    pipe.submit(WorkspaceProposal(
        proposal_id="mem.1", content_ref="c.mem", source_level=RepresentationLevel.RECALLED,
        salience=SalienceComponents(0.9, 0.1, 0.1, 0.1, 0.1), sponsor_module="memory"))
    out = pipe.run_competition(cycle=0)
    assert out is not None
    assert out.frame.source_levels == (RepresentationLevel.RECALLED,)
    assert out.frame.items[0].source_level is RepresentationLevel.RECALLED


def test_no_execution_path(ws_params: C2WorkspaceParams) -> None:
    """结构面：workspace 包零 import 行动/目标平面（命名空间扫描第二防线）。"""
    from galatea.subject.workspace import ports as ws_ports

    mods = sorted(m for m in sys.modules if m.startswith("galatea.subject.workspace.")
                  and not m.startswith("galatea.subject.workspace.tests"))
    assert mods
    for name in mods:
        mod = importlib.import_module(name)
        ws_ports.assert_no_execution_path(vars(mod))
    del ws_params


# ------------------------------------------------------------------ 伪判据
def test_pseudo_workspace_criteria_faces() -> None:
    """四判据：FAIL 即 PseudoWorkspaceSuspect；③④ PENDING 不冒充 PASS。"""
    status = pseudo_workspace_check(
        rejections_count=1, frames_with_effective_access=1,
        lesion_selectivity_established=None, competition_causality_established=None,
    )
    assert status["lesion_selectivity"] == "PENDING_E1"
    assert status["competition_causality"] == "PENDING_C2_STAT"
    with pytest.raises(PseudoWorkspaceSuspect):
        pseudo_workspace_check(0, 0, None, None)      # 容量判据 FAIL
    with pytest.raises(PseudoWorkspaceSuspect):
        pseudo_workspace_check(1, 0, None, None)      # effective_access 不可达 FAIL


def test_double_run_bit_exact(ws_params: C2WorkspaceParams) -> None:
    """同提案序列双跑 → 帧序列 digest bit-exact 恒等（零 RNG 零墙钟）。"""
    outs1, outs2 = [], []
    for pipe, outs in ((WorkspacePipeline(ws_params, readers=READERS), outs1),
                       (WorkspacePipeline(ws_params, readers=READERS), outs2)):
        for c in range(3):
            for i in range(5):
                pipe.submit(_prop(f"p{c}.{i}", 0.2 + 0.15 * i, sponsor=READERS[i % 4]))
            o = pipe.run_competition(cycle=c)
            if o is not None:
                outs.append(o)
    d1 = outs1[0].frame.content_digest if outs1 else ""
    assert pipe.trace_digest(tuple(outs1)) == pipe.trace_digest(tuple(outs2))
    assert d1
