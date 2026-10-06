"""预注册 watch point 表与更新校验（L07 §4.3/§10 watch.py）。

Q-L07-06：最小集 = 每声明读者一个状态 digest watch（perception/models/affect/
memory 四模块——Q-L07-05② 一一对应）；新增仅经 profile 版本变更（运行期禁增删）；
**事后注册拒绝**（PostHocWatchRejected——预注册时点必须先于广播，评价诚信 S2 面）。
"""
from dataclasses import dataclass

from galatea.subject.workspace.ports import PostHocWatchRejected

__all__ = ["WatchPointUpdate", "WatchRegistry"]


@dataclass(frozen=True, slots=True)
class WatchPointUpdate:
    """watch 更新（有效变化 = pre_registered ∧ digest_before ≠ digest_after）。"""

    watch_id: str
    module: str
    changed: bool
    digest_before: str
    digest_after: str
    pre_registered: bool
    at_cycle: int


class WatchRegistry:
    """预注册表（启动期注册；运行期禁增删——Q-L07-06②）。"""

    def __init__(self) -> None:
        self._registered: dict[str, int] = {}     # watch_id -> registered_at_cycle
        self._frozen = False

    def register(self, watch_id: str, at_cycle: int) -> None:
        """启动期注册（冻结后注册 = PostHocWatchRejected）。"""
        if self._frozen:
            raise PostHocWatchRejected(
                f"watch registration closed at runtime: {watch_id!r}（Q-L07-06② 仅经 profile 版本变更）"
            )
        if watch_id in self._registered:
            raise ValueError(f"duplicate watch_id: {watch_id!r}")
        self._registered[watch_id] = at_cycle

    def freeze(self) -> None:
        """启动期结束（此后注册 = 事后注册，拒）。"""
        self._frozen = True

    def validate(self, update: WatchPointUpdate, frame_cycle: int) -> WatchPointUpdate:
        """更新校验（预注册先于广播；changed 一致性——变化 ⟺ digest 改变）。"""
        registered_at = self._registered.get(update.watch_id)
        if not update.pre_registered or registered_at is None:
            raise PostHocWatchRejected(
                f"watch {update.watch_id!r} not pre-registered（事后注册无效，L07 §4.3）"
            )
        if registered_at > frame_cycle:
            raise PostHocWatchRejected(
                f"watch {update.watch_id!r} registered at {registered_at} > frame cycle {frame_cycle}"
                "（预注册必须先于广播）"
            )
        if update.changed != (update.digest_before != update.digest_after):
            raise ValueError(
                f"watch {update.watch_id!r}: changed flag inconsistent with digest change"
            )
        return update

    def registered_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._registered))
