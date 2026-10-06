"""affect ≠ command/goal（L05 §7 invariant / §8 不变量 1——affect 不发动行动）。"""
import importlib
import sys

from galatea.subject.affect import ports as affect_ports
from galatea.subject.affect.motive import AffectiveMotiveProposal
from galatea.subject.affect.ports import AffectCycleInputs
from galatea.subject.affect.pipeline import AffectPipeline
from galatea.subject.c2profile import C2AffectParams


def test_affect_modules_do_not_import_command_planes() -> None:
    """结构面：affect 包零 import 行动/目标平面模块（import 图检查）。"""
    import galatea.subject.affect as aff_pkg

    pkg_dir = set(sys.modules)
    affect_mods = {m for m in pkg_dir if m.startswith("galatea.subject.affect")}
    for name in list(affect_mods):
        mod = sys.modules[name]
        assert mod is not None
    banned = ("galatea.subject.action", "galatea.subject.goals", "galatea.subject.workspace")
    for name in affect_mods:
        mod = importlib.import_module(name)
        for b in banned:
            assert not any(
                k == b or k.startswith(b + ".") for k in getattr(mod, "__dict__", {})
            ), f"{name} leaks {b}"
    del aff_pkg


def test_motive_proposal_type_isolated_from_owned_goal(affect_params: C2AffectParams) -> None:
    """AffectiveMotiveProposal 与 OwnedGoal 类型分离（L05 §7 contract：无 goal 字段/承诺/执行面）。"""
    from galatea.subject.goals.owned import OwnedGoal

    pipe = AffectPipeline(affect_params)
    out = pipe.step(AffectCycleInputs(cycle=0, body_energy=0.8, body_integrity=1.0))
    proposal = out.motive_proposal
    assert isinstance(proposal, AffectiveMotiveProposal)
    assert not isinstance(proposal, OwnedGoal)
    # 字段面隔离：无 goal_id/commitment/deadline/intention 等目标语义字段
    for goal_field in ("goal_id", "commitment", "deadline", "intention", "authorized"):
        assert not hasattr(proposal, goal_field), goal_field
    # 数据类字段恰四 + digest（无隐藏标量化字段）
    assert set(type(proposal).__dataclass_fields__) == {
        "proposal_id", "urgency", "evidence_refs", "state_digest", "issued_at"
    }


def test_no_command_path_assertion() -> None:
    """合同断言面：逐 affect 模块命名空间无命令平面泄漏（第二防线）。"""
    affect_mods = sorted(m for m in sys.modules if m.startswith("galatea.subject.affect.")
                         and not m.startswith("galatea.subject.affect.tests"))
    assert affect_mods, "affect 子模块须已加载"
    for name in affect_mods:
        mod = importlib.import_module(name)
        affect_ports.assert_no_command_path(vars(mod))   # 不抛 = 无违例
    assert issubclass(affect_ports.ProhibitedWritePath, RuntimeError)

def test_affective_motive_proposal_no_execution_surface(affect_params) -> None:
    """AffectiveMotiveProposal 无 ActionIntention/命令面（C3 权限测试——L08 §8 不变量 4）。"""
    from galatea.subject.affect.ports import AffectCycleInputs
    from galatea.subject.affect.motive import AffectiveMotiveProposal
    from galatea.subject.affect.pipeline import AffectPipeline
    from galatea.subject.control.intention import ActionIntention

    pipe = AffectPipeline(affect_params)
    out = pipe.step(AffectCycleInputs(cycle=0, body_energy=0.8, body_integrity=1.0))
    p = out.motive_proposal
    assert isinstance(p, AffectiveMotiveProposal)
    assert not isinstance(p, ActionIntention)
    for cmd_field in ("command_id", "requested_action", "budget", "deadline",
                      "idempotency_key", "authorize"):
        assert not hasattr(p, cmd_field), cmd_field
    assert set(type(p).__dataclass_fields__) == {
        "proposal_id", "urgency", "evidence_refs", "state_digest", "issued_at",
    }


def test_affective_motive_enters_arbitration_plane() -> None:
    """AFFECTIVE 源经 L08 仲裁面向（goals/arbitration 五维映射——与各源平等）。"""
    from galatea.subject.affect.motive import AffectiveMotiveProposal
    from galatea.subject.goals.arbitration import arbitrate, vector_of
    from galatea.subject.goals.motives import motive_affective

    proposal = AffectiveMotiveProposal("p1", 0.8, ("e",), "digest", 0)
    motive = motive_affective(
        __import__("galatea.subject.goals.motives", fromlist=["AffectiveMotive"]).AffectiveMotive(
            kind="c2_urgency", urgency=0.8, evidence_refs=proposal.evidence_refs), 0)
    vec = vector_of("aff", motive)
    assert vec.vector[3] == 0.8 and all(vec.vector[i] == 0.0 for i in (0, 1, 2))
    trace = arbitrate((vec,), 0)
    assert trace.picked == "aff"   # 单候选仲裁产出（无直达 gateway 路径）
