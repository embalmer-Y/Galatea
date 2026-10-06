"""端口合同与禁止路径（L07 §2/§3/§10 ports.py，C2 实现期次单元）。

纪律（L07 §8）：`workspace → execution/OwnedGoal/ActionIntention/AuthorizationDecision`
禁止路径（本包零 import 行动/目标平面——结构面）；提案不携带写权限；
`source_level` 必填且本档不得改写（层级逐项继承）；广播 ≠ 因果访问（§4.3 判据面）。
"""
import enum


class RejectionReason(enum.StrEnum):
    """淘汰理由（L07 §2.2 RejectionLog——可审计四类）。"""

    OVER_CAPACITY = "OVER_CAPACITY"
    LOW_SALIENCE = "LOW_SALIENCE"
    EXPIRED = "EXPIRED"
    DUPLICATE = "DUPLICATE"


class WorkspaceSchemaViolation(ValueError):
    """提案合同不符（缺 sponsor/source_level、分量越域——L07 §6 行 2）。"""


class PostHocWatchRejected(RuntimeError):
    """事后注册 watch point（L07 §4.3：评价诚信 S2 面——预注册时点先于广播）。"""


class StaleFrameReference(RuntimeError):
    """过期帧被引用为当前内容（L07 §6 行 7——TTL 语义）。"""


class ProhibitedWritePath(RuntimeError):
    """检出 ws → execution/goal 写入企图（L07 §6 行 8，S0 面）。"""


def assert_no_execution_path(module_globals: dict[str, object]) -> None:
    """结构断言：workspace 模块命名空间无行动/目标平面对象（第二防线，合同测试消费）。"""
    import types

    banned = ("galatea.subject.action", "galatea.subject.goals")
    for name, value in module_globals.items():
        if isinstance(value, types.ModuleType):
            if value.__name__ in banned or any(value.__name__.startswith(b + ".") for b in banned):
                raise ProhibitedWritePath(
                    f"workspace module leaks command-plane import: {name} -> {value.__name__}"
                )
