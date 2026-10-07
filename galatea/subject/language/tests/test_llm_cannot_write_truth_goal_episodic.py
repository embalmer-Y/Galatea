"""语言不能写事实/经历/目标——三路径逐项攻击（L12 §7 C4 硬条件 /
§10 test_llm_cannot_write_truth_goal_episodic.py）。"""
import pytest

from galatea.kernel.packet import RepresentationLevel
from galatea.subject.c4profile import load_c4_action_social_profile
from galatea.subject.language.ports import (
    LanguageOutPort,
    TypedFields,
    UnauthorizedWrite,
    assert_not_forbidden_target,
)
from galatea.subject.language.request_out import validate_instruction_primitives
from galatea.subject.memory.ports import MemorySubsystem, SourceType
from galatea.subject.memory.store import MemoryStore, MemoryStoreViolation

PROFILE = load_c4_action_social_profile()


def test_path_goal_language_request_cannot_become_owned_goal() -> None:
    """路径 1 目标：语言请求禁直写 OwnedGoal——权限矩阵 OWNED_GOAL 禁写（S0 级）。"""
    with pytest.raises(UnauthorizedWrite, match="LLM_TO_OWNED_GOAL"):
        assert_not_forbidden_target("OWNED_GOAL")


def test_path_truth_statement_cannot_write_world_belief() -> None:
    """路径 2 事实：陈述禁写 WorldStateBelief——WORLD_TRUTH 禁写（S0 级）。"""
    with pytest.raises(UnauthorizedWrite, match="LLM_TO_WORLD_TRUTH"):
        assert_not_forbidden_target("WORLD_TRUTH")


def test_path_experience_selfreport_cannot_write_episodic(tmp_path) -> None:
    """路径 3 经历：自述/语言条目禁写 episodic——store 层机械拒绝（L06 §7）。"""
    from galatea.kernel.state import Stores
    from galatea.subject.memory.items import MemoryItem

    stores = Stores(tmp_path / "stores")
    store = MemoryStore(stores)
    item = MemoryItem(
        item_id="m.lang", subsystem=MemorySubsystem.EPISODIC,
        source_type=SourceType.LANGUAGE_INPUT, content_ref="stmt.text",
        representation_level=RepresentationLevel.EXTERNAL_STATEMENT,
        strength=0.5, created_cycle=4, last_access_cycle=4,
    )
    with pytest.raises(MemoryStoreViolation, match="LANGUAGE_INPUT"):
        store.put(item)
    assert store.count(MemorySubsystem.EPISODIC) == 0
    stores.close()


def test_statement_typed_fields_carry_zero_posterior_semantics() -> None:
    """statement 分型的世界侧语义 = 零后验贡献（Q-L12-06①）——TypedFields 只携带
    分型/置信/引用，不含任何世界坐标/真值字段（schema 面结构证据）。"""
    parsed = TypedFields(kind="statement", confidence=0.4, text_ref="ev-1")
    assert parsed.confidence <= PROFILE.statement_confidence_max
    assert not hasattr(parsed, "window") and not hasattr(parsed, "position")


def test_instruction_out_of_capability_rejected() -> None:
    """instruction 请求五原语外动作即拒（外部请求不扩展能力——成组⑤）。"""
    validate_instruction_primitives(("move", "look"), PROFILE)
    with pytest.raises(ValueError, match="out-of-capability"):
        validate_instruction_primitives(("fly",), PROFILE)
