"""affect/drive 不直达执行权限测试（L08 §9 C3 行 / L05 §9 C3 行——C3 硬条件）。

本文件**零 affect import**（P03：action 域禁触情感层——结构面禁令对测试同等生效；
类型面断言经 affect 侧测试套件承载（affect/tests/test_affect_not_command.py），
本文件以源扫描 + metacontrol 纯断言补齐 action 侧检出面。禁令模式在断言中以
分段字面量拼装（避免本文件源文本自匹配泄漏探针）。
"""
from pathlib import Path

from galatea.subject.action.metacontrol import MetaTriggers, decide

_BANNED_HEAD = "from galatea." + "subject.affect"
_BANNED_TAIL = "import galatea." + "subject.affect"


def _action_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_action_plane_source_free_of_affect_imports() -> None:
    """结构面：action 包全部模块源零 affect import（字符串扫描——不 import 即不触 P03）。"""
    offenders: list[str] = []
    for py in sorted(_action_root().rglob("*.py")):
        if "tests" in py.parts or "__pycache__" in py.parts:
            continue
        text = py.read_text(encoding="utf-8")
        if _BANNED_HEAD in text or _BANNED_TAIL in text:
            offenders.append(str(py))
    assert offenders == [], f"action 域泄漏 affect import：{offenders}（affect 不直达执行）"


def test_metacontrol_output_is_decision_not_command() -> None:
    """元决策产出 = 决策枚举（非 ActionIntention——L09 §4.3 状态机语义）。"""
    d = decide(MetaTriggers())
    assert d in ("ACT", "OBSERVE", "THINK", "SEEK_HELP", "ABANDON")
    from galatea.subject.control.intention import ActionIntention
    assert not isinstance(d, ActionIntention)


def test_gateway_signature_sources_unreachable_from_metacontrol() -> None:
    """metacontrol 无网关调用面（决策 ≠ 命令；授权唯一在 L10 gateway 经提案仲裁后）。"""
    import galatea.subject.action.metacontrol as mc

    assert not any("gateway" in k for k in vars(mc))
    assert not hasattr(mc, "authorize")
