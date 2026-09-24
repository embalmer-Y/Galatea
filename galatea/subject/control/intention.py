"""ActionIntention 冻结构造（L09 §10 intention.py；schema 见 L10 §2.1 PortIn）。

纪律：L09 所有、L10 只消费——本模块是 ActionIntention 的唯一定义点；
F0 范围 = schema 合同；仲裁行为（arbitrate.py）归 M1/C3。
"""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ActionIntention:
    """意图（L10 §2.1：网关唯一合法入口的数据合同）。"""

    intention_id: str
    selected_proposal_id: str
    arbitration_trace: str  # ArtifactRef/台账引用（仲裁台账 schema 归 L09 M1）
    deadline: int  # virtual_time
    budget_hint: int | None
    idempotency_key: str
