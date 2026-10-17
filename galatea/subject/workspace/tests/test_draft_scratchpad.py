"""草稿板合同测试（Q-L07-09：权限矩阵/状态机/非信念结构面/确定性快照）。"""
import pytest

from galatea.subject.workspace.draft import (
    DraftDonor,
    DraftEvaluation,
    DraftHypothesis,
    DraftSchemaViolation,
    DraftStateViolation,
    DraftStatus,
    Scratchpad,
    UnauthorizedDraftDonor,
)


def _draft(hid: str = "h1", donor: DraftDonor = DraftDonor.MODELS_ROLLOUT,
           status: DraftStatus = DraftStatus.OPEN, **kw) -> DraftHypothesis:
    return DraftHypothesis(
        hypothesis_id=hid, claim=kw.get("claim", "resource near center is forageable"),
        provenance_ref=kw.get("prov", "rollout/r-17"), confidence=kw.get("conf", 0.6),
        created_cycle=kw.get("cycle", 10), donor=donor, status=status,
        payload=kw.get("payload", {"target": "5,5"}))


def test_write_permission_matrix() -> None:
    """白名单外供体 = UnauthorizedDraftDonor（Q-L07-09③ 既有权限矩阵扩展语义）。"""
    pad = Scratchpad()
    for donor in DraftDonor:
        pad.submit(_draft(f"h-{donor.value}", donor=donor))
    with pytest.raises(UnauthorizedDraftDonor):
        pad.submit_from("language_llm", hypothesis_id="hx", claim="x",
                        provenance_ref="p", confidence=0.5, created_cycle=0)
    with pytest.raises(UnauthorizedDraftDonor):
        pad.submit_from("orchestrator", hypothesis_id="hy", claim="y",
                        provenance_ref="p", confidence=0.5, created_cycle=0)
    assert pad.submit_from("models_rollout", hypothesis_id="hz", claim="z",
                           provenance_ref="p", confidence=0.5, created_cycle=0)


def test_state_machine_no_skip_no_revival() -> None:
    """open→evaluated→{superseded|contradicted}；跳级/终态转移/未知 id 全拒。"""
    pad = Scratchpad()
    pad.submit(_draft("a"))
    pad.submit(_draft("b"))
    pad.submit_from("workspace_loop", hypothesis_id="a2", claim="successor",
                    provenance_ref="loop/1", confidence=0.7, created_cycle=11)
    ev = lambda hid: DraftEvaluation(hypothesis_id=hid, cycle=12, score=0.5,
                                     evaluator_ref="rssm_imagine_rollout", beat=1)
    with pytest.raises(DraftStateViolation):
        pad.supersede("a", "a2")            # 跳级：open 不可 supersede
    pad.evaluate("a", ev("a"))
    with pytest.raises(DraftStateViolation):
        pad.evaluate("a", ev("a"))          # 二次评估 = 状态机违例
    pad.supersede("a", "a2")
    assert pad.get("a").status is DraftStatus.SUPERSEDED
    with pytest.raises(DraftStateViolation):
        pad.contradict("a")                 # 终态禁复活
    with pytest.raises(DraftStateViolation):
        pad.evaluate("nope", ev("nope"))
    pad.evaluate("b", ev("b"))
    pad.contradict("b")
    assert pad.get("b").status is DraftStatus.CONTRADICTED
    # supersede 后继必须来自 workspace_loop（revise 拍供体）
    pad.submit(_draft("c", status=DraftStatus.EVALUATED))
    pad.submit(_draft("d", donor=DraftDonor.PERCEPTION_HYPOTHESIS))
    with pytest.raises(DraftStateViolation):
        pad.supersede("c", "d")


def test_schema_fail_closed() -> None:
    """空 claim/provenance、confidence 越域、donor 类型——构造面即拒。"""
    with pytest.raises(DraftSchemaViolation):
        _draft("e1", claim="")
    with pytest.raises(DraftSchemaViolation):
        _draft("e2", prov="")
    with pytest.raises(DraftSchemaViolation):
        _draft("e3", conf=1.5)
    with pytest.raises(DraftSchemaViolation):
        DraftHypothesis(hypothesis_id="e4", claim="x", provenance_ref="p",
                        confidence=0.5, created_cycle=0, donor="models_rollout")


def test_non_belief_structural_surface() -> None:
    """非信念原则（②）：draft 模块 import 面零触及信念面（L03/L04）与行动/目标面。"""
    import ast
    import inspect

    import galatea.subject.workspace.draft as draft_mod
    tree = ast.parse(inspect.getsource(draft_mod))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    for banned in ("galatea.subject.perception", "galatea.subject.models",
                   "galatea.subject.goals", "galatea.subject.action"):
        hits = [m for m in imported if m.startswith(banned)]
        assert not hits, f"draft module must not import {banned}（Q-L07-09②）, got {hits}"
    # API 形状承诺：无"确证/信念"出口（P14 教训：扫描 import 面与成员面，禁源码字面量匹配）
    pad_api = Scratchpad
    assert not hasattr(pad_api, "confirm")
    assert not hasattr(pad_api, "to_belief")
    assert not hasattr(pad_api, "write_belief")


def test_snapshot_roundtrip_and_digest() -> None:
    """快照往返 bit 级恒等 + digest 稳定 + 被篡改快照 fail closed（Q-L07-09④）。"""
    pad = Scratchpad()
    pad.submit(_draft("a"))
    pad.submit_from("workspace_loop", hypothesis_id="a2", claim="successor",
                    provenance_ref="loop/1", confidence=0.7, created_cycle=11)
    pad.evaluate("a", DraftEvaluation(hypothesis_id="a", cycle=12, score=0.5,
                                      evaluator_ref="rssm_imagine_rollout", beat=1))
    pad.supersede("a", "a2")
    snap = pad.snapshot()
    digest1 = pad.state_digest()
    restored = Scratchpad()
    restored.restore_snapshot(snap)
    assert restored.state_digest() == digest1
    assert restored.snapshot() == snap
    # 篡改：未知 draft 的 evaluation / 形状破损 → 拒
    import copy
    bad = copy.deepcopy(snap)
    bad["evaluations"].append({"hypothesis_id": "ghost", "cycle": 0, "score": 0.0,
                               "evaluator_ref": "x", "beat": 0})
    with pytest.raises(DraftStateViolation):
        Scratchpad().restore_snapshot(bad)
    with pytest.raises(DraftSchemaViolation):
        Scratchpad().restore_snapshot({"drafts": []})
