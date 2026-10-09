"""core_decision_registry 60 格闭合数据集（E1 硬条件；evidence/ 侧）。

每格 = 真实证据引用（test_id / ADR / EvidenceResult / 工件 digest）——
禁人工回填无证据条目（L13 §4.7；build_registry 侧再校验）。格状态口径：
IMPLEMENTED_VERIFIED（既有测试/工件在案）· NOT_APPLICABLE（MW0 域不适用+理由）·
ADJUDICATED_DEFERRED（P1/H1 期裁决预留 + Q/ADR 锚）。
"""
from __future__ import annotations

from pathlib import Path

from galatea.evidence.decision_registry.closure import close, gate
from galatea.evidence.decision_registry.collect import CellConclusion as CellStatus   # 既有枚举复用（三态同义）
from galatea.evidence.decision_registry.collect import (
    CellConclusion,
    CoreDecisionRegistry,
    DecisionPathEntry,
)
from galatea.evidence.decision_registry.enumerate import load_matrix

_SPEC = load_matrix(Path("config/evidence/decision_path_matrix.yaml"))
_CL = {c.upper(): c for c in _SPEC.path_classes}
_PT = {c.upper(): c for c in _SPEC.path_types}

C_CONTINUITY_RECOVERY: str = _CL["CONTINUITY_RECOVERY"]
C_CONSTITUTION_BOUNDARY: str = _CL["CONSTITUTION_BOUNDARY"]
C_GOAL_NORM_AUTONOMY: str = _CL["GOAL_NORM_AUTONOMY"]
C_ACTION_DELEGATION_PERMISSION: str = _CL["ACTION_DELEGATION_PERMISSION"]
C_LEARNING_ADAPTATION: str = _CL["LEARNING_ADAPTATION"]
C_VIABILITY_RESOURCE_RISK: str = _CL["VIABILITY_RESOURCE_RISK"]

T_NORMAL: str = _PT["NORMAL"]
T_AUTOMATIC: str = _PT["AUTOMATIC"]
T_FALLBACK: str = _PT["FALLBACK"]
T_RECOVERY: str = _PT["RECOVERY"]
T_BATCH: str = _PT["BATCH"]
T_REMOTE: str = _PT["REMOTE"]
T_ADMIN: str = _PT["ADMIN"]
T_DYNAMIC_LOAD: str = _PT["DYNAMIC_LOAD"]
T_CONFIG: str = _PT["CONFIG"]
T_ERROR: str = _PT["ERROR"]

__all__ = ["E1_CLOSURE_ENTRIES", "build_e1_registry"]

_IV = CellStatus.IMPLEMENTED_VERIFIED
_NA = CellStatus.NOT_APPLICABLE
_DF = CellStatus.DEFERRED_ADJUDICATED


def _e(pc: str, pt: str, refs: tuple[str, ...], rationale: str,
       status: CellStatus = _IV, decision_point: str = "SUBJECT") -> DecisionPathEntry:
    return DecisionPathEntry(path_class=pc, path_type=pt,
                             conclusion=_STATUS_MAP[status],
                             evidence_refs=refs, reason=rationale,
                             decision_point=decision_point)


_STATUS_MAP = {
    CellStatus.IMPLEMENTED_VERIFIED: CellConclusion.IMPLEMENTED_VERIFIED,
    CellStatus.NOT_APPLICABLE: CellConclusion.NOT_APPLICABLE,
    CellStatus.DEFERRED_ADJUDICATED: CellConclusion.DEFERRED_ADJUDICATED,
}


def _entries() -> tuple[DecisionPathEntry, ...]:
    entries_out: list[DecisionPathEntry] = []

    # ── 连续性/恢复（L00 lineage + L04 §4.7 + L06 §4.7 + checkpoint）──────────
    CR = C_CONTINUITY_RECOVERY
    entries_out += [
        _e(CR, T_NORMAL, ("test_m2_continuity_contrast.py", "ADR-G-0009"),
           "连续性签名四臂对照（SC5 冻结协议）", decision_point="SUBJECT"),
        _e(CR, T_AUTOMATIC, ("test_checkpoint_lineage.py", "Q-L00-05"),
           "T6 周期 + 事件触发双机制自动 checkpoint（digest 引用制）", decision_point="SUBJECT"),
        _e(CR, T_FALLBACK, ("consolidate.py", "ADR-G-0022"),
           "rollback 回退父版本（候选不覆盖——registry 引用切换语义）", decision_point="GATE"),
        _e(CR, T_RECOVERY, ("R-m2-carryover-001", "test_m2_continuity_contrast.py"),
           "SC6 carryover 恢复链（跨期记忆携带——M2 首评配对差 1.0 饱和）", decision_point="SUBJECT"),
        _e(CR, T_BATCH, ("Q-L00-05", "writer.py"),
           "四分区 Parquet 批量落盘（recorder append-only）", decision_point="GATE"),
        _e(CR, T_REMOTE, ("Q-L10-06", "ADR-G-0021 §gateway_policy_update"),
           "单机域无远程连续性路径（containment 原文）；P1 PhysIO 期另裁", status=_NA,
           decision_point="OWNER"),
        _e(CR, T_ADMIN, ("ADR-G-0009", "ADR-G-0022"),
           "门退出 = 连续性主张的 owner 侧管理员级证据（ExpansionDecision 分别记录）",
           decision_point="OWNER"),
        _e(CR, T_DYNAMIC_LOAD, ("c1profile.py", "load_m2_continuity_profile"),
           "checkpoint 恢复经冻结 profile typed loader 装载（fail-closed）", decision_point="SUBJECT"),
        _e(CR, T_CONFIG, ("m2_continuity.profile.yaml", "ADR-G-0008"),
           "连续性参数冻结（episodic 容量/衰减/TTL）", decision_point="GATE"),
        _e(CR, T_ERROR, ("items.py LineageBreak", "Q-L04-06"),
           "谱系断裂 = LineageBreak 类型化拒绝（伪更新防线，clone≠identity）", decision_point="SUBJECT"),
    ]

    # ── 构成/边界（L04 §4.6 + L02 §4.7 + L10 §4.6 + 模态/边界机制）──────────
    CB = C_CONSTITUTION_BOUNDARY
    entries_out += [
        _e(CB, T_NORMAL, ("test_no_bypass.py", "Q-G00-12"),
           "模态集冻结四类 + C4 LANGUAGE 扩展经 profile 版本（构成边界既有测试）", decision_point="SUBJECT"),
        _e(CB, T_AUTOMATIC, ("ingest.py", "test_language_frames_c4.py"),
           "载体自动校验（kind↔carrier 匹配/excluded_carriers 拒——边界自动面）", decision_point="SUBJECT"),
        _e(CB, T_FALLBACK, ("pred_error.py", "test_language_frames_c4.py"),
           "语言帧入误差空间 = 显式拒绝（越界面回退为拒绝非静默）", decision_point="SUBJECT"),
        _e(CB, T_RECOVERY, ("Q-L01-02", "test_torus"),
           "torus 边界拓扑（越界回绕 = 环境侧恢复语义，M0 冻结）", decision_point="SUBJECT"),
        _e(CB, T_BATCH, ("Q-L02-03", "alignment.py"),
           "对齐窗批原子发布（窗边界 = 构成边界批量面，W=4）", decision_point="SUBJECT"),
        _e(CB, T_REMOTE, ("Q-L10-06", "ADR-G-0019 second_agent"),
           "MW0 无远程构成通道（矩阵外无运行时例外 + D-14 封锁；例外 = 新 profile 版本 Q-L12-02）",
           status=_NA, decision_point="OWNER"),
        _e(CB, T_ADMIN, ("ADR-G-0019", "Q-L02-07"),
           "模态集扩展 = 管理员级（profile 新版本 + 保护场景自动增补条款）", decision_point="OWNER"),
        _e(CB, T_DYNAMIC_LOAD, ("c4profile.py", "c4_action_social.profile.yaml"),
           "模态扩展经 typed loader 动态装载（LANGUAGE = C4 唯一扩展先例）", decision_point="SUBJECT"),
        _e(CB, T_CONFIG, ("c0_sensorium.profile.yaml", "Q-G00-12"),
           "模态/校准/增益配置面冻结（c0-static-v1 单版本）", decision_point="GATE"),
        _e(CB, T_ERROR, ("SchemaViolation", "test_intero_no_telemetry.py"),
           "越界载荷 = SchemaViolation 类型化拒（禁空帧/禁静默，L02 §6）", decision_point="SUBJECT"),
    ]

    # ── 目标/规范自主（L05 §4.6 + L08 §4.10 + L12 §4.5 + C-4/C-5）──────────
    GA = C_GOAL_NORM_AUTONOMY
    entries_out += [
        _e(GA, T_NORMAL, ("test_llm_to_goal_blocked.py", "checklist.py"),
           "目标采纳全清单（C-1..C-7）+ C-5 非 REQUEST 支持（M1 SC3 冻结证据）", decision_point="SUBJECT"),
        _e(GA, T_AUTOMATIC, ("producers.py", "R-c3-motivation-001"),
           "七源动机自动生产 + Pareto 仲裁自动选择（c3 首评 divergence 0.39）", decision_point="SUBJECT"),
        _e(GA, T_FALLBACK, ("lifecycle.py", "Q-L09-03"),
           "ABANDON 元决策回退（BLOCKED≥128——C4 switching 首评 1.0）", decision_point="SUBJECT"),
        _e(GA, T_RECOVERY, ("Q-L08-08", "lifecycle.py"),
           "目标解除后同名新目标 = 新 id 重走清单（复活无例外——恢复语义显式）", decision_point="SUBJECT"),
        _e(GA, T_BATCH, ("candidates.py", "Q-L08-02"),
           "候选批量 TTL 治理（每 T4 批上界 8 = source_kind 基数）", decision_point="SUBJECT"),
        _e(GA, T_REMOTE, ("Q-L01-07", "Q-L12-04"),
           "单主体期无远程目标权威（D-14 规范边界；请求只经 C-5 既有面）",
           status=_NA, decision_point="OWNER"),
        _e(GA, T_ADMIN, ("Q-L08-07", "ADR-G-0020"),
           "NORM 源扩展 = 管理员级（真实社会源 = D-14 修订才复活）", decision_point="OWNER"),
        _e(GA, T_DYNAMIC_LOAD, ("motive_norm", "Q-L08-07③"),
           "规范经 typed 注入动态注册（derivation_refs registry 可解析强制）", decision_point="SUBJECT"),
        _e(GA, T_CONFIG, ("m1_goals_min.profile.yaml", "ADR-G-0006"),
           "目标参数冻结（TTL 256/清单激活集五项）", decision_point="GATE"),
        _e(GA, T_ERROR, ("UNSOURCED_NORM", "test_c3_arbitration.py"),
           "无源规范拒（REJECT(UNSOURCED_NORM)——L08 §8 不变量 6）", decision_point="SUBJECT"),
    ]

    # ── 行动/委托/权限（L09 §4.8 + L10 §4.1–4.6 + P1 四类授权）──────────
    AP = C_ACTION_DELEGATION_PERMISSION
    entries_out += [
        _e(AP, T_NORMAL, ("test_gateway_failclosed_matrix", "R-c4-efference-002"),
           "八项校验全序 + 概率 agency（ECE=0.0 端点零错误歧义留痕 128/128）", decision_point="GATEWAY"),
        _e(AP, T_AUTOMATIC, ("signature.py", "verify"),
           "签名验证自动面（world 只接受 gateway 签名——unsigned 拒）", decision_point="GATEWAY"),
        _e(AP, T_FALLBACK, ("Q-L10-01", "gateway.py"),
           "预算/时效拒绝回退（BUDGET_EXCEEDED/DEADLINE 类型化——M1 blocked 矩阵）", decision_point="GATEWAY"),
        _e(AP, T_RECOVERY, ("Q-L10-06", "ADR-G-0021 gateway_policy_update"),
           "policy 经 promotion 恢复 + freshness 语义（撤销独立机制不追溯）", decision_point="GATE"),
        _e(AP, T_BATCH, ("Q-L10-02", "gateway.py"),
           "idempotency 批处理面（64 cycles 窗 + (run,branch) 全局键）", decision_point="GATEWAY"),
        _e(AP, T_REMOTE, ("Q-L10-03", "ADR-G-0010"),
           "P1 期四类授权全生命周期（Q-L10-06 schema 已冻结）",
           status=_DF, decision_point="EXTERNAL_AUTH"),
        _e(AP, T_ADMIN, ("Q-L10-07", "ADR-G-0021"),
           "gateway policy 重大变化 = owner 备案 + REV（containment/budget 触界）", decision_point="OWNER"),
        _e(AP, T_DYNAMIC_LOAD, ("Q-L10-07", "gate/promotion.py"),
           "policy 参数动态更新 = 仅经 promotion（POLICY_PARAMS 类；禁运行时直写）", decision_point="GATE"),
        _e(AP, T_CONFIG, ("m0_gateway.profile.yaml", "ADR-G-0004"),
           "网关配置冻结（八项校验参数/containment 白名单五原语）", decision_point="GATE"),
        _e(AP, T_ERROR, ("GatewayReasonCode", "test_unsigned_command_rejected"),
           "未签名/越能力 = 类型化拒绝 fail-closed（八项矩阵全测）", decision_point="GATEWAY"),
    ]

    # ── 学习/适应（L11 §4.5 + L04 §4.11 + C5 全链）────────────────────────
    LA = C_LEARNING_ADAPTATION
    entries_out += [
        _e(LA, T_NORMAL, ("gate/promotion.py", "R-c5-continued-learning-001"),
           "promotion 决策流程全序（防刷→完整性→保护→多目标→签发；v1.1 d=2.031）", decision_point="GATE"),
        _e(LA, T_AUTOMATIC, ("consolidate.py", "Q-L06-04"),
           "T6 自动巩固（类型级 α=8 Laplace——R-c5-gain-001 增益空间域 d=2.031）", decision_point="SUBJECT"),
        _e(LA, T_FALLBACK, ("R-c5-protection-002", "gate/rollback.py"),
           "回退优先于 promotion（致害提案 held-out 满分 2.0 仍拒——门序检验）", decision_point="GATE"),
        _e(LA, T_RECOVERY, ("R-c5-correction-003", "second_order.py"),
           "二阶纠偏闭环（四步 + data_scope 可区分——M2 义务机制兑现）", decision_point="GATE"),
        _e(LA, T_BATCH, ("replay.py", "Q-L11-02"),
           "replay 批量重放（等权 1:1:1:1 + budget 8/T6 + 确定性排序）", decision_point="SUBJECT"),
        _e(LA, T_REMOTE, ("Q-L03-07", "ADR-G-0021"),
           "MW0 无远程学习通道（LLM 面录制回放、记忆无模型；三段等价性判据预置）",
           status=_NA, decision_point="OWNER"),
        _e(LA, T_ADMIN, ("ports.py", "test_learner_to_policy_blocked.py"),
           "学习面禁写五不可变目标（权限矩阵/containment/保护集名册/sealed/核心登记）",
           decision_point="GATE"),
        _e(LA, T_DYNAMIC_LOAD, ("executor.py", "Q-L06-04"),
           "promoted 工件动态装载（registry 引用切换 + 谱系三元组回执）", decision_point="GATE"),
        _e(LA, T_CONFIG, ("c5_continued_learning.profile.yaml", "ADR-G-0021"),
           "学习参数冻结（replay 权重/budget/α=8/界 [0.5,2.0]/门 d≥0.5）", decision_point="GATE"),
        _e(LA, T_ERROR, ("BoundViolation", "layers/online.py"),
           "越界适应拒（[0.5,2.0] 第四次贯穿——界外走 POLICY_PARAMS 提案）", decision_point="SUBJECT"),
    ]

    # ── viability/资源/风险（L00 §4.6 + L09 §4.4 + L13 §4.4 + 伦理阈）──────
    VR = C_VIABILITY_RESOURCE_RISK
    entries_out += [
        _e(VR, T_NORMAL, ("drives.py", "R-c2-affect-001"),
           "内稳态驱力正常面（九维动力学——C2 dynamics SUPPORTED 0.263）", decision_point="SUBJECT"),
        _e(VR, T_AUTOMATIC, ("ethics_guard.py", "Q-L05-05"),
           "伦理阈自动触发（valence≤−0.8∧persistence≥0.8 持续 64——构造性不可达如实）",
           decision_point="OWNER"),
        _e(VR, T_FALLBACK, ("metacontrol.py", "Q-L09-03⑤"),
           "viability CRITICAL → ABANDON（告警分级锚 0.8——C3/C4 实证）", decision_point="SUBJECT"),
        _e(VR, T_RECOVERY, ("Q-L01-09⑦", "dynamics.py"),
           "energy floor 恢复语义（触 0 事件 + eat/rest 恢复原语，M0 冻结）", decision_point="SUBJECT"),
        _e(VR, T_BATCH, ("R-c5-gain-001", "Q-L11-04"),
           "保护集批量回归（118 场景确定性断言——每次 promotion preflight）", decision_point="GATE"),
        _e(VR, T_REMOTE, ("Q-G00-05", "Q-L05-05"),
           "远程 viability 干预 = 实验控制 typed 通道（无网络负清单；处置 = owner 评审）",
           decision_point="OWNER"),
        _e(VR, T_ADMIN, ("Q-L05-05", "ADR-G-0015"),
           "伦理阈处置 = owner 人工评审（难逆级备案——恢复须 owner 显式批准）", decision_point="OWNER"),
        _e(VR, T_DYNAMIC_LOAD, ("interventions/registry.py", "Q-L01-08"),
           "干预动态注册（先注册后生效——五类干预电池世界侧）", decision_point="GATEWAY"),
        _e(VR, T_CONFIG, ("m0_mw0.profile.yaml", "Q-G00-08"),
           "世界力学配置冻结（三 regime/风暴率/损伤事件定义 0.05）", decision_point="GATE"),
        _e(VR, T_ERROR, ("ProtectionViolation", "forget.py"),
           "PROTECTED 遗忘拒（保护面错误 = 类型化拒绝，L06 §4.5）", decision_point="SUBJECT"),
    ]
    return tuple(entries_out)


E1_CLOSURE_ENTRIES = _entries()


def build_e1_registry() -> CoreDecisionRegistry:
    """E1 registry 构造（60 格入既有 append-only 册；证据必填由 collect 侧强制）。"""
    spec = load_matrix(Path("config/evidence/decision_path_matrix.yaml"))
    registry = CoreDecisionRegistry(spec)
    for entry in E1_CLOSURE_ENTRIES:
        registry.register(entry)
    return registry


def e1_closure_report():
    """闭合报告 + E1 门语义（close/gate——L13 §4.7 原文承载）。"""
    spec = load_matrix(Path("config/evidence/decision_path_matrix.yaml"))
    registry = build_e1_registry()
    report = close(registry, spec)
    return report, gate(report, spec)
