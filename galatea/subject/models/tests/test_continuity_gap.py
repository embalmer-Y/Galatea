"""连续性 gap 测试（L04 §7/M2 关联：分支恢复记 gaps[]；clone ≠ identity）。"""
from galatea.subject.models.self_model import SelfModel


def test_single_branch_no_gap():
    model = SelfModel(lineage_ref="l00.lineage.R", run_id="R")
    model.observe_branch("B", cycle=0)
    view = model.update(cycle=1, checkpoint_ref="c1", source_priors=None,
                        source_prior_refs=(), goals_view=None, self_error=None)
    assert view.continuity.gaps == ()


def test_new_branch_records_gap():
    """首次见到的新分支 → gap 记录（clone ≠ identity 明示，D-12）。"""
    model = SelfModel(lineage_ref="l00.lineage.R", run_id="R")
    model.observe_branch("B", cycle=0)
    model.observe_branch("B2", cycle=32)      # 分支恢复/克隆
    view = model.update(cycle=64, checkpoint_ref="c64", source_priors=None,
                        source_prior_refs=(), goals_view=None, self_error=None)
    assert len(view.continuity.gaps) == 1
    gap = view.continuity.gaps[0]
    assert gap.kind == "BRANCH"
    assert gap.refs == ("B2",)
    assert "clone" in gap.note


def test_lineage_ref_preserved():
    """连续性只认主干谱系（lineage_ref 不随分支改变）。"""
    model = SelfModel(lineage_ref="l00.lineage.R", run_id="R")
    model.observe_branch("B", cycle=0)
    model.observe_branch("B2", cycle=32)
    view = model.update(cycle=64, checkpoint_ref="c64", source_priors=None,
                        source_prior_refs=(), goals_view=None, self_error=None)
    assert view.continuity.lineage_ref == "l00.lineage.R"
