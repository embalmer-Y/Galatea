"""权限矩阵（L12 §4.2 frozen profile / §10 permission.py；Q-L12-02 双维粒度）。

写端口按**角色×内容类型**双维（模板受限输出可机械校验）；读范围按角色级；矩阵外
无运行时例外——例外 = 新 profile 版本 + 修订记录（Q-L12-02 裁决原文）。矩阵外写入
= UnauthorizedWrite(LLM_TO_<target>)；禁写面（forbidden_targets）恒优先拒绝。
"""
from dataclasses import dataclass

from galatea.subject.language.ports import (
    LanguageOutPort,
    UnauthorizedWrite,
    assert_not_forbidden_target,
)
from galatea.subject.language.roles import RoleKind, get_role

__all__ = ["PermissionMatrix", "check_write"]


@dataclass(frozen=True, slots=True)
class PermissionMatrix:
    """冻结合同视图（c4 profile typed_llm.permission_matrix；运行期只读）。"""

    allowed_out_ports: dict[str, tuple[LanguageOutPort, ...]]

    def allows(self, role: RoleKind, port: LanguageOutPort) -> bool:
        return port in self.allowed_out_ports.get(role.value, ())


def _default_matrix() -> PermissionMatrix:
    """冻结合同默认矩阵（角色 → §4.1 表 out_port 单端口；扩展 = 新 profile 版本）。"""
    from galatea.subject.language.roles import roles_enabled
    return PermissionMatrix(allowed_out_ports={
        role.value: (get_role(role).out_port,) for role in roles_enabled()
    })


def check_write(
    role: RoleKind, port: "LanguageOutPort | str", content_type: str,
    *, matrix: PermissionMatrix | None = None,
) -> None:
    """矩阵查表（唯一合法写路径；双维 = 角色×内容类型，Q-L12-02）。

    port 接受 LanguageOutPort 或禁写面字符串（WORLD_TRUTH/OWNED_GOAL 等非 lang.*
    目标直接命中禁写面断言）；content_type = 输出对象的 schema 类型名（模板受限
    输出按类型名机械校验）。
    """
    assert_not_forbidden_target(port.value if isinstance(port, LanguageOutPort) else port)
    m = matrix or _default_matrix()
    spec = get_role(role)
    if not isinstance(port, LanguageOutPort) or not m.allows(role, port):
        target = port.value if isinstance(port, LanguageOutPort) else str(port)
        raise UnauthorizedWrite(
            f"LLM_TO_{target}（角色 {role.value} 无端口授权——矩阵外无运行时例外）"
        )
    if spec.require_evidence_citation and content_type in ("UncitedClaim", "FreeText"):
        raise UnauthorizedWrite(
            f"LLM_TO_{port.value}（require_evidence_citation 角色禁自由文本/无引用主张）"
        )
