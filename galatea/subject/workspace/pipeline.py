"""工作空间装配面（L07 §5 T3 挂点 / §10 补录件——C2 实现期次单元）。

T3 周期（竞争 → 选帧 → 广播 → 收回执/watch → 发布 AccessEvidence → 再竞争门）：
- `run_competition(cycle, salience_modulation)`：提案池竞争 + 帧发布 + 投递清单
  （消费 affect salience 调制：clip [0.5,2.0] + 回执——三类调制第三类闭环）；
- `submit_read_receipt` / `submit_watch_update`：读者面交互（预注册校验）；
- `settle(cycle)`：回执超时结算（N2）+ effective_access 计算 + 伪判据状态；
- 递归：`run_competition(depth=...)` 经 recursion_gate；去重窗 DedupRegistry。

确定性：零 RNG 零墙钟（c2_workspace.profile determinism none 形态）；帧不可变。
"""
from dataclasses import dataclass

from galatea.kernel.unknown import Unknown
from galatea.subject.affect.modulation import ModulationField
from galatea.subject.c2profile import C2WorkspaceParams
from galatea.subject.workspace.access import AccessEvidence, effective_access
from galatea.subject.workspace.broadcast import ReadReceipt, settle_receipts
from galatea.subject.workspace.compete import (
    RejectedProposal,
    ScoredProposal,
    compete,
    consume_salience_modulation,
)
from galatea.subject.workspace.frame import WorkspaceFrame, build_frame
from galatea.subject.workspace.propose import WorkspaceProposal
from galatea.subject.workspace.recurse import DedupRegistry, recursion_depth
from galatea.subject.workspace.receipt import WorkspaceReceipt
from galatea.subject.workspace.watch import WatchPointUpdate, WatchRegistry

__all__ = ["WorkspaceCycleOutput", "WorkspacePipeline"]

#: 模块 → LLD 档根（Q-L07-05① 形式定义——运行期冻结）
MODULE_ROOT: dict[str, str] = {
    "perception": "perception_L03",
    "models": "models_L04",
    "affect": "affect_L05",
    "memory": "memory_L06",
}


@dataclass(frozen=True, slots=True)
class WorkspaceCycleOutput:
    """单竞争拍产物（证据侧可审计）。"""

    frame: WorkspaceFrame
    trace: tuple[ScoredProposal, ...]
    rejections: tuple[RejectedProposal, ...]
    delivery: tuple[tuple[str, str], ...]
    modulation_receipt_id: str | None
    workspace_receipt: WorkspaceReceipt


class WorkspacePipeline:
    """工作空间服务（帧/回执/watch/去重状态唯一持有者——L07 §3 单写者）。"""

    def __init__(self, params: C2WorkspaceParams, readers: tuple[str, ...]) -> None:
        self._params = params
        self._readers = readers
        self._queue: list[WorkspaceProposal] = []
        self._watch = WatchRegistry()
        for m in readers:                       # 预注册 watch = 每读者一状态 digest watch（Q-L07-06①）
            self._watch.register(f"watch.{m}", at_cycle=-1)
        self._watch.freeze()                    # 启动期结束——运行期禁增删
        self._dedup = DedupRegistry(ttl=params.dedup_ttl_cycles)
        self._receipts: dict[str, list[ReadReceipt]] = {}
        self._watch_updates: dict[str, list[WatchPointUpdate]] = {}
        self._frames: dict[str, WorkspaceFrame] = {}
        self._rejections_total = 0
        self._effective_frames = 0
        self._last_rejections: tuple[RejectedProposal, ...] = ()

    # ------------------------------------------------------------ 竞争与帧
    def submit(self, proposal: WorkspaceProposal) -> None:
        """提案入池（下一竞争拍参与；sponsor/域校验在类型面）。"""
        self._queue.append(proposal)

    def run_competition(
        self,
        cycle: int,
        salience_modulation: ModulationField | None = None,
        depth: int = 0,
    ) -> WorkspaceCycleOutput | Unknown | None:
        """竞争拍（depth = 递归深度；超深 → Unknown(CAPABILITY_LIMIT) 不产帧）。"""
        gated = recursion_depth(depth, self._params.depth_max)
        if not isinstance(gated, int):
            return gated    # Unknown——递归停止（能力上限，非错误）
        pool = tuple(self._queue)
        self._queue = []
        if not pool:
            return None
        affect_factor = 1.0
        mod_id: str | None = None
        if salience_modulation is not None:
            rec = consume_salience_modulation(salience_modulation, cycle)
            affect_factor = rec.applied_value
            mod_id = rec.modulation_id
        digests = tuple(p.content_ref for p in pool)   # 去重键 = content_ref（C2 MW0 引用即内容）
        duplicate_ids = self._dedup.duplicates(digests, cycle)
        admitted, trace, rejections = compete(pool, self._params, affect_factor, duplicate_ids)
        self._rejections_total += len(rejections)
        self._last_rejections = rejections
        if not admitted:
            return None   # 无入选不发布帧（空广播无因果访问价值；淘汰照常留痕）
        frame = build_frame(
            frame_id=f"ws.{cycle}.d{depth}", cycle_id=cycle, admitted=admitted,
            trace=trace, modulation_receipt_ids=() if mod_id is None else (mod_id,),
            ttl_cycles=self._params.frame_ttl_cycles, recursion_depth=depth,
        )
        for item in frame.items:
            self._dedup.note(item.content_ref, cycle)
        self._frames[frame.frame_id] = frame
        self._receipts[frame.frame_id] = []
        self._watch_updates[frame.frame_id] = []
        from galatea.subject.workspace.broadcast import broadcast_targets

        return WorkspaceCycleOutput(
            frame=frame, trace=trace, rejections=rejections,
            delivery=broadcast_targets(frame.frame_id, self._readers),
            modulation_receipt_id=mod_id,
            workspace_receipt=WorkspaceReceipt(
                frame_id=frame.frame_id, cycle_id=cycle,
                modulation_receipt_ids=() if mod_id is None else (mod_id,),
                policy_ref=self._params.ref(),
            ),
        )

    # ------------------------------------------------------- 读者面交互
    def submit_read_receipt(self, receipt: ReadReceipt) -> None:
        """读者回执登记（帧必须在案）。"""
        if receipt.frame_id not in self._frames:
            raise ValueError(f"receipt for unknown frame: {receipt.frame_id!r}")
        self._receipts[receipt.frame_id].append(receipt)

    def submit_watch_update(self, update: WatchPointUpdate, frame_id: str) -> None:
        """watch 更新（预注册校验——事后注册拒）。"""
        frame = self._frames[frame_id]
        self._watch.validate(update, frame.cycle_id)
        self._watch_updates[frame_id].append(update)

    # ------------------------------------------------------------- 结算
    def settle(self, frame_id: str, now_cycle: int) -> AccessEvidence:
        """回执结算 + effective_access（缺回执读者不计入 separated——Q-L07-03②）。"""
        frame = self._frames[frame_id]
        receipts = tuple(self._receipts[frame_id])
        on_time, _missing = settle_receipts(
            frame_cycle=frame.cycle_id, frame_ttl=frame.ttl_cycles, readers=self._readers,
            receipts=receipts, timeout_cycles=self._params.receipt_timeout_cycles,
            now_cycle=now_cycle, frame_id=frame_id,
        )
        on_time_modules = {r.reader_module for r in on_time}
        updates = tuple(
            (u.watch_id, u.module, u.changed)
            for u in self._watch_updates[frame_id]
        )
        evidence = effective_access(
            frame_id=frame_id,
            receipts_count=len(on_time),
            watch_updates=updates,
            module_root=MODULE_ROOT,
        )
        del on_time_modules
        if evidence.effective_access:
            self._effective_frames += 1
        return evidence

    # ------------------------------------------------------------- 状态面
    def frame(self, frame_id: str) -> WorkspaceFrame:
        return self._frames[frame_id]

    @property
    def last_rejections(self) -> tuple[RejectedProposal, ...]:
        """最近竞争拍淘汰日志（检出面可见——INC-08 纪律）。"""
        return self._last_rejections

    @property
    def rejections_total(self) -> int:
        return self._rejections_total

    def pseudo_status(self) -> dict[str, str]:
        """伪 workspace 四判据状态（③④ E1/统计面绑定——PENDING 不冒充 PASS）。"""
        from galatea.subject.workspace.pseudo_check import pseudo_workspace_check

        return pseudo_workspace_check(
            rejections_count=self._rejections_total,
            frames_with_effective_access=self._effective_frames,
            lesion_selectivity_established=None,
            competition_causality_established=None,
        )

    def trace_digest(self, outputs: tuple[WorkspaceCycleOutput, ...]) -> str:
        from galatea.kernel.digest import content_digest

        return content_digest([o.frame.content_digest for o in outputs])
