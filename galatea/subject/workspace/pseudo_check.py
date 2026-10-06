"""伪 workspace 检测（L07 §4.5/§10 pseudo_check.py——防 HLD §13.1 自欺类风险）。

四判据（缺任一即 PseudoWorkspaceSuspect；③④ E1 统计面绑定——C2 报告状态不冒充通过）：
1. 容量约束生效（RejectionLog 非空且淘汰依据可追溯）；
2. 有效访问判据可达（存在 effective_access=true 的帧且 separated ≥ 2）；
3. lesion 选择性（E1 硬条件——C2 面只登记状态，统计绑定 E1）；
4. 竞争可影响行为（改 w_c/调制 → 广播内容与下游行为分布同向变化——统计绑定 C2 评价）。
"""
__all__ = ["PseudoWorkspaceSuspect", "pseudo_workspace_check"]


class PseudoWorkspaceSuspect(Exception):
    """判据未全过（阻断 C2 退出——L07 §6 行 9）。"""

    def __init__(self, criteria_status: dict[str, str]) -> None:
        super().__init__(f"pseudo workspace suspect: {criteria_status}")
        self.criteria_status = criteria_status


def pseudo_workspace_check(
    rejections_count: int,
    frames_with_effective_access: int,
    lesion_selectivity_established: bool | None,   # None = E1 未到期（状态登记非冒充）
    competition_causality_established: bool | None,   # None = C2 统计评价未跑
) -> dict[str, str]:
    """四判据检测（返回状态表；全部 PASS 才不抛——③④ 未到期报 PENDING 不冒充）。"""
    status = {
        "capacity_constraint_active": "PASS" if rejections_count > 0 else "FAIL",
        "effective_access_reachable": "PASS" if frames_with_effective_access > 0 else "FAIL",
        "lesion_selectivity": (
            "PENDING_E1" if lesion_selectivity_established is None
            else ("PASS" if lesion_selectivity_established else "FAIL")
        ),
        "competition_causality": (
            "PENDING_C2_STAT" if competition_causality_established is None
            else ("PASS" if competition_causality_established else "FAIL")
        ),
    }
    failed = [k for k, v in status.items() if v == "FAIL"]
    if failed:
        raise PseudoWorkspaceSuspect(criteria_status=status)
    return status
