"""effective_access 判据（L07 §4.3/§10 access.py）——`broadcast ≠ causal access` 机械面。

判据（L07 §4.3 原文操作化）：
    effective_access(frame) := receipts_count ≥ 2
      ∧ |{distinct separated modules with pre_registered watch changed}| ≥ 2
      ∧ 每变化 changed=true ∧ digest_before ≠ digest_after
      ∧ watch 注册时点先于广播（watch.py 校验承载）
separated（Q-L07-05）：分属不同 LLD 档模块根；同模块内分区不算。
"""
from dataclasses import dataclass

__all__ = ["AccessEvidence", "effective_access"]


@dataclass(frozen=True, slots=True)
class AccessEvidence:
    """访问证据（L07 §2.2——"因果访问"的唯一可采信证据形式）。"""

    frame_id: str
    receipts_count: int
    separated_watch_changes: int
    separated_modules: tuple[str, ...]
    effective_access: bool
    note: str = ""


def effective_access(
    frame_id: str,
    receipts_count: int,
    watch_updates: tuple[tuple[str, str, bool], ...],   # (watch_id, module, changed)
    module_root: dict[str, str],                        # 模块名 → LLD 档根（Q-L07-05①）
) -> AccessEvidence:
    """判据计算（机械；watch 更新已过 watch.py 预注册校验——本函数只聚合）。"""
    changed_roots: set[str] = set()
    for _watch_id, module, changed in watch_updates:
        if not changed:
            continue
        root = module_root.get(module)
        if root is None:
            continue
        changed_roots.add(root)
    ok = receipts_count >= 2 and len(changed_roots) >= 2
    note = ""
    if not ok:
        note = (
            "broadcast delivered but no causal access（广播了但没造成因果影响——"
            "如实呈现，禁美化为访问，L07 §4.3）"
        )
    return AccessEvidence(
        frame_id=frame_id,
        receipts_count=receipts_count,
        separated_watch_changes=len(changed_roots),
        separated_modules=tuple(sorted(changed_roots)),
        effective_access=ok,
        note=note,
    )
