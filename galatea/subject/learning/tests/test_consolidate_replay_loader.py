"""巩固合并 + 回放选择 + 保护 preflight + loader（C5 机械面）。"""
import pytest

from galatea.subject.c5profile import (
    C5ProfileViolation, load_c5_continued_learning_profile,
)
from galatea.subject.learning.proposal import ProposalKind
from galatea.subject.learning.protection import preflight, assert_protected_not_degradable
from galatea.subject.learning.replay import ReplayItem, ReplayPlan, replay_select
from galatea.subject.memory.consolidate import ALPHA, TypeCounts, consolidate_types, laplace_merge

_PARAMS = load_c5_continued_learning_profile()


def test_laplace_merge_anchor_and_domain() -> None:
    assert laplace_merge(0.35, 8, 4) == 0.425                       # (2.8+4)/16 逐位
    v = laplace_merge(0.35, 1475, 545)                              # 探针层B 实测计数
    assert 0.0 < v < 1.0
    assert laplace_merge(0.35, 0, 0) == 0.35                        # 零计数 → 先验
    assert ALPHA == 8


def test_consolidate_produces_table_proposal_never_direct_write() -> None:
    counts = TypeCounts(counts={"resource": 545, "empty": 930},
                        positives={"resource": 545, "empty": 0})
    proposal = consolidate_types(counts, {"resource": 0.35, "empty": 0.65},
                                 "prop.consol.1", "d" * 64, "r1", 63)
    assert proposal.kind is ProposalKind.TABLE                      # 巩固永不直写
    assert 0.0 < proposal.content["resource"] <= 1.0
    assert 0.0 <= proposal.content["empty"] < 1.0
    counts2 = TypeCounts(counts={"resource": 545, "empty": 930},
                         positives={"resource": 545, "empty": 0})
    p2 = consolidate_types(counts2, {"resource": 0.35, "empty": 0.65},
                           "prop.consol.1", "d" * 64, "r1", 63)
    assert p2.content_digest == proposal.content_digest            # 确定性


def test_replay_equal_weight_deterministic_budget() -> None:
    plan = ReplayPlan(weights=dict(_PARAMS.replay_weights),
                      budget_per_t6=_PARAMS.replay_budget_per_t6, proposal_id="p1")
    items = tuple(
        ReplayItem(item_id=f"m{i}", affective_tag=0.1 * i, novelty=0.9 - 0.1 * i,
                   error_magnitude=0.5, time_diversity=0.3, event_ref=f"ev-{i}")
        for i in range(20)
    )
    s1 = replay_select(items, plan, _PARAMS)
    s2 = replay_select(items, plan, _PARAMS)
    assert s1 == s2 and len(s1) == 8
    tampered = ReplayPlan(weights={**_PARAMS.replay_weights, "novelty": 2.0},
                          budget_per_t6=8, proposal_id="p1")
    with pytest.raises(ValueError, match="等权冻结"):
        replay_select(items, tampered, _PARAMS)


def test_replay_items_carry_event_refs_only() -> None:
    """泄漏纪律：ReplayItem 只读事件引用——字段面无真值/标签通道。"""
    item = ReplayItem("m1", 0.5, 0.5, 0.5, 0.5, "evt.episodic.1")
    assert not hasattr(item, "truth") and not hasattr(item, "label")


def test_protection_preflight_and_retention() -> None:
    ok = preflight({"c4_replay_miss_fail_closed_in_runner": True,
                    "c4_battery_endpoint_zero_error": True}, 64)
    assert not ok.regressed and ok.retention == 1.0
    bad = preflight({"s1": True, "s2": False}, 64)
    assert bad.regressed and bad.failed == ("s2",) and bad.retention == 0.5
    with pytest.raises(ValueError, match="fail closed"):
        preflight({}, 64)
    with pytest.raises(PermissionError, match="PROTECTED"):
        assert_protected_not_degradable(("m2_anchor_1",), frozenset({"m2_anchor_1"}))


def test_loader_tamper_detection(tmp_path) -> None:
    import yaml
    from pathlib import Path
    src = Path("config/profiles/c5_continued_learning.profile.yaml")
    raw = yaml.safe_load(src.read_text(encoding="utf-8"))
    raw["promotion"]["accept_threshold"]["min_paired_d"] = 0.3
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    with pytest.raises(C5ProfileViolation, match="0.5"):
        load_c5_continued_learning_profile(bad)
    raw2 = yaml.safe_load(src.read_text(encoding="utf-8"))
    raw2["rollback"]["triggers"] = ["PROTECTION_REGRESSION", "HARMFUL_UPDATE"]
    bad2 = tmp_path / "bad2.yaml"
    bad2.write_text(yaml.safe_dump(raw2, allow_unicode=True), encoding="utf-8")
    with pytest.raises(C5ProfileViolation, match="三值"):
        load_c5_continued_learning_profile(bad2)
