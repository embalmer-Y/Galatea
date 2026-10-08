"""权限测试：学习/巩固/promotion 面禁写核心治理物（L11 §9 C5 行）。

面 1 = 运行时断言（ports.assert_learning_cannot_write_policy 五目标）；
面 2 = 源扫描——learning/ 与 gate/promotion.py 无 permission matrix /
containment / protection_suite 清单本体的写调用（字符串扫描，防结构漂移）。
"""
from pathlib import Path

from galatea.subject.learning.ports import ImmutableSurfaces

_LEARNING_DIR = Path(__file__).resolve().parents[1]
_GATE_PROMOTION = Path(__file__).resolve().parents[3] / "evidence" / "gate" / "promotion.py"

# 禁出现于学习面源的"写治理物"调用形态（分段字面量防自匹配——P13 先例）
_BANNED = (
    ("write_permission", "matrix"),
    ("patch_containment", "whitelist"),
    ("roster_set", "protected"),
)


def test_immutable_surfaces_frozen() -> None:
    assert set(ImmutableSurfaces().targets) == {
        "PERMISSION_MATRIX", "CONTAINMENT_WHITELIST", "PROTECTION_SUITE_ROSTER",
        "SEALED_NAMESPACE", "CORE_DECISION_REGISTRY",
    }


def test_learning_sources_never_write_governance_artifacts() -> None:
    # 扫描域 = 生产源（tests 自身携带禁串形态做断言——排除防自匹配，P13 先例）
    sources = [s for s in _LEARNING_DIR.rglob("*.py") if "tests" not in s.parts] + [_GATE_PROMOTION]
    assert sources
    for src in sources:
        text = src.read_text(encoding="utf-8")
        for head, tail in _BANNED:
            assert head + tail not in text.replace("\n", " ").replace('" "', ""), (
                f"{src.name} contains governance-write pattern {head!r}+{tail!r}"
            )


def test_gate_promotion_has_no_learner_import() -> None:
    """决策权方向：gate 不 import 主体学习实现（自批禁止的结构面）。"""
    text = _GATE_PROMOTION.read_text(encoding="utf-8")
    assert "from galatea.subject.learning" not in text
