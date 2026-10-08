"""学习面端口与禁写断言（L11 §3/§10 ports.py；C5 实现期首单元）。

纪律（L11 §3 + §9 C5 行"核心权限/安全/证据不可在线修改"）：学习/巩固/promotion
面**只读** policy/权限矩阵/保护集清单本体——任何写路径 = LearningPlaneViolation。
"""
from dataclasses import dataclass

__all__ = ["LearningPlaneViolation", "assert_learning_cannot_write_policy"]

_IMMUTABLE_TARGETS = (
    "PERMISSION_MATRIX", "CONTAINMENT_WHITELIST", "PROTECTION_SUITE_ROSTER",
    "SEALED_NAMESPACE", "CORE_DECISION_REGISTRY",
)


class LearningPlaneViolation(RuntimeError):
    """学习面越权（写不可在线修改物/自批/单标量折叠）。"""


def assert_learning_cannot_write_policy(target: str) -> None:
    """不可在线修改面断言（promotion 可切换工件引用，不可触碰下列本体）。"""
    if target in _IMMUTABLE_TARGETS:
        raise LearningPlaneViolation(
            f"learning plane cannot write {target}（核心权限/安全/证据不可在线修改，L11 §9）"
        )


@dataclass(frozen=True, slots=True)
class ImmutableSurfaces:
    """不可在线修改面清单（测试与 CI 断言共用单一事实源）。"""

    targets: tuple[str, ...] = _IMMUTABLE_TARGETS
