"""慢环调度（三时钟第二钟——Q-L09-11；L09 移交件：触发判据属 L09 域，产物面属 L07 草稿板）。

合同（Q-L09-11）：
- **触发** = 空闲拍（无驱力 urgency > 0——Q-L08-09④ 活跃信号判据的补集，锚既有
  冻结常数；且无 pending 命令）或低唤起（arousal < arousal_low = 0.1——锚 Q-L05-03
  band = 2 × render_noise_sigma 同源常数）；禁抢占快环反应（本模块零行动面接口，
  结构守卫 = workspace → action/goals 禁 import 既有面）；
- **产物** = 草稿板假设（Q-L07-09 结构，供体 = controller_proposal）——行动面零新增：
  本模块只产 DraftHypothesis 与审计记录，禁产命令/意图；
- **频度** = 逐拍检测（check_interval_cycles=1——触发判据本身即频度门，零新自由常量；
  profile v1.1 冻结）；深思拍数上界 = 思维循环 think_steps_budget（Q-L07-10③ 复用）；
- **审计**（④）：SlowClockRecord 逐事件 typed（jsonl 可序列化形态）+ episode digest——
  迁移审计流扩展点（Q-L13-16 既有 jsonl 面消费）。
"""
from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Callable

from galatea.kernel.digest import content_digest
from galatea.subject.workspace.draft import DraftDonor, DraftHypothesis
from galatea.subject.workspace.thought import ThoughtLoopResult

__all__ = [
    "SlowClockTrigger",
    "SlowClockParams",
    "SlowClockDecision",
    "SlowClockRecord",
    "SlowClockEpisode",
    "SlowClock",
]


class SlowClockTrigger(enum.StrEnum):
    """触发词表（Q-L09-11①；profile slow_clock.trigger 冻结校验点）。"""

    IDLE_CYCLE = "idle_cycle"
    LOW_AROUSAL = "low_arousal"


@dataclass(frozen=True, slots=True)
class SlowClockParams:
    """慢环冻结参数（p4_beta_mind.profile slow_clock 节 v1.1 typed 视图）。"""

    triggers: tuple[SlowClockTrigger, ...]   # (idle_cycle, low_arousal) 冻结
    arousal_low: float                       # 0.1（锚 Q-L05-03 band = 2σ）
    urgency_idle: float                      # 0.0（锚 Q-L08-09④ urgency>0 活跃判据补集）
    check_interval_cycles: int               # 1 = 逐拍检测（频度冻结）

    def __post_init__(self) -> None:
        if self.triggers != (SlowClockTrigger.IDLE_CYCLE, SlowClockTrigger.LOW_AROUSAL):
            raise ValueError("slow clock trigger set frozen（Q-L09-11①）")
        if not 0.0 <= self.arousal_low <= 1.0:
            raise ValueError(f"arousal_low out of [0,1]: {self.arousal_low!r}")
        if not 0.0 <= self.urgency_idle <= 1.0:
            raise ValueError(f"urgency_idle out of [0,1]: {self.urgency_idle!r}")
        if self.check_interval_cycles < 1:
            raise ValueError("check_interval_cycles must be ≥1（逐拍检测下界）")


@dataclass(frozen=True, slots=True)
class SlowClockDecision:
    """单拍触发判定（不触发 = None；触发词表可多 Satisfaction 并存）。"""

    cycle: int
    triggers: tuple[SlowClockTrigger, ...]
    arousal: float
    urgency_max: float
    pending_command: bool


@dataclass(frozen=True, slots=True)
class SlowClockEpisode:
    """一次深思 episode（触发判定 + 思维循环产物 + 供体提案引用）。"""

    decision: SlowClockDecision
    loop: ThoughtLoopResult
    proposal_ref: str                # 提案面引用（L09 控制器提案 — provenance 素材）

    def digest(self) -> str:
        return content_digest({
            "decision": {
                "cycle": self.decision.cycle,
                "triggers": [t.value for t in self.decision.triggers],
                "arousal": self.decision.arousal,
                "urgency_max": self.decision.urgency_max,
                "pending_command": self.decision.pending_command,
            },
            "loop": {
                "selected_id": self.loop.selected_id,
                "selected_score": self.loop.selected_score,
                "iterations": self.loop.iterations,
                "terminated_by": self.loop.terminated_by,
                "receipts": [r.digest() for r in self.loop.receipts],
                "contradictions": [e.event_id for e in self.loop.contradictions],
            },
            "proposal_ref": self.proposal_ref,
        })


@dataclass(frozen=True, slots=True)
class SlowClockRecord:
    """审计记录（Q-L09-11④：jsonl 可序列化 + digest——迁移审计流扩展点）。"""

    cycle: int
    kind: str                        # "slow_clock_episode"
    triggers: tuple[str, ...]
    episode_digest: str
    drafts_created: int
    terminated_by: str

    def to_jsonl(self) -> str:
        import json
        return json.dumps({
            "kind": self.kind, "cycle": self.cycle, "triggers": list(self.triggers),
            "episode_digest": self.episode_digest, "drafts_created": self.drafts_created,
            "terminated_by": self.terminated_by,
        }, ensure_ascii=False, sort_keys=True)


class SlowClock:
    """慢环调度器（触发判定 + episode 记账；域提案逻辑注入——本类零行动面）。"""

    def __init__(self, params: SlowClockParams) -> None:
        self._params = params
        self._records: list[SlowClockRecord] = []

    def should_trigger(self, cycle: int, arousal: float, urgency_max: float,
                       pending_command: bool) -> SlowClockDecision | None:
        """触发判定（①：空闲 = urgency_max ≤ 阈 且无 pending；低唤起 = arousal < 阈）。"""
        if cycle % self._params.check_interval_cycles != 0:
            return None
        satisfied: list[SlowClockTrigger] = []
        if (urgency_max <= self._params.urgency_idle and not pending_command
                and SlowClockTrigger.IDLE_CYCLE in self._params.triggers):
            satisfied.append(SlowClockTrigger.IDLE_CYCLE)
        if arousal < self._params.arousal_low and SlowClockTrigger.LOW_AROUSAL in self._params.triggers:
            satisfied.append(SlowClockTrigger.LOW_AROUSAL)
        if not satisfied:
            return None
        return SlowClockDecision(cycle=cycle, triggers=tuple(satisfied), arousal=arousal,
                                 urgency_max=urgency_max, pending_command=pending_command)

    def run_episode(self, decision: SlowClockDecision, loop_result: ThoughtLoopResult,
                    drafts_created: int, proposal_ref: str) -> SlowClockEpisode:
        """episode 记账（循环本体由调用方驱动——提案面产物经思维循环后在此落账）。"""
        episode = SlowClockEpisode(decision=decision, loop=loop_result, proposal_ref=proposal_ref)
        self._records.append(SlowClockRecord(
            cycle=decision.cycle, kind="slow_clock_episode",
            triggers=tuple(t.value for t in decision.triggers),
            episode_digest=episode.digest(), drafts_created=drafts_created,
            terminated_by=loop_result.terminated_by))
        return episode

    @property
    def records(self) -> tuple[SlowClockRecord, ...]:
        return tuple(self._records)


#: 提案面合同：L09 控制器提案 → 种子草稿集合（供体 = controller_proposal，白名单内）。
SeedProposals = Callable[[SlowClockDecision], tuple[DraftHypothesis, ...]]


def require_controller_donors(seeds: tuple[DraftHypothesis, ...]) -> tuple[DraftHypothesis, ...]:
    """提案面出口校验（产物纪律②：慢环种子供体必须 = controller_proposal）。"""
    for seed in seeds:
        if seed.donor is not DraftDonor.CONTROLLER_PROPOSAL:
            raise ValueError(
                f"slow clock seeds must come from controller_proposal, got {seed.donor.value}")
    return seeds
