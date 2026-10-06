# L09 控制器与元控制：五类控制器并行提案、仲裁与 metacontrol

> LLD: L09/14 · v1.1 · 2026-10-06（C3 准备单元：Q-L09-01/02/03/04/07 CONFIRMED + c3_motivation.profile v1.0 冻结；实现件 = C3 实现期）· 原版见 git 历史 · 状态：WORKING（C3 冻结评审前置）
> 上游：`HLD.md` §1.2（归属与控制）/§5（预测误差）/§6/§9.2 · `L03/L04/L05/L06/L07/L08`（提案素材与目标） · `L00_kernel.md`（T 级调度）
> 下游：L10（`ControllerProposal → ActionIntention` 仲裁与提交）
> 引入门槛：**M1**（最小授权与选择证据）→ **C3**（五类控制器 + metacontrol）→ **C4**（forward/inverse 与主动感知闭环）→ **E1**（控制器 lesion）

## 1. 目标与范围

**目标**：实现五类并行控制器（Reflex / Habit / Model-based / Active perception / Language-social）各自产出 typed `ControllerProposal`，并由 **metacontrol（元控制）** 在"行动、观察、思考、求助、放弃"五类元决策间切换；同时承载**监控**职责（可靠性、冲突、失控、预测失败、能力边界）。本档**不授权、不执行**：仲裁产出 `ActionIntention` 后必须交 L10 gateway。

**范围内**：
- 五类控制器的合同、输入依赖与提案类型；
- 提案竞争与仲裁（优先级、置信度、成本、目标对齐度）；
- metacontrol 五类元决策切换与其触发条件；
- 监控信号：可靠性（记忆/知觉/模型）、冲突计数、失控检测（预测误差持续超阈）、能力边界（L04 `CapabilityEstimate`）；
- 主动感知请求的执行侧承接（来自 L04 提案）；
- 预测误差驱动的注意与策略调整（消费 L02/L03/L04 三层误差）。

**范围外**：目标采纳（L08）；授权决策与执行（L10）；归属判定（L10）；情感数值（L05）；模型 rollout 计算（L04，本档只请求）；语言生成（L12，本档只提交 typed 请求）。

**成功判据（C3 退出，承 card_06 C3 行）**：请求不直写目标（承 L08）；affect/drive 不直达执行（权限测试）；目标持续且可修订；**控制可在规划/观察/求助/放弃间切换**且切换有据可查；五类控制器可分别 lesion 并产生选择性失败。

## 2. Ports（输入输出契约）

### 2.1 PortIn

| 端口 | 来源 | 数据 | 纪律 |
|---|---|---|---|
| `ctl.goal_in(g)` | L08 | `OwnedGoal` / `GoalProgressView` / `GoalCandidate`（仲裁依据） | 禁由本档创建目标 |
| `ctl.belief_in(b)` | L03/L04 | `PerceptualBelief`、`Affordance`、`WorldStateBelief`、`CapabilityEstimate` | 只读 |
| `ctl.sensory_error_in(e)` | L02/L03/L04 | 三层预测误差（感觉/知觉/模型） | 层级不得混淆 |
| `ctl.affect_in(f)` | L05 | `FunctionalExperientialState`（有界读取 + 回执）、`HomeostaticAlert` | affect ≠ command：只作**权重因子**，禁直接生成意图 |
| `ctl.memory_in(r)` | L06 | `RecalledContent`（RECALLED）、`MemoryReliability`（metamemory）、procedural 经验 | 回忆/经验仅供策略参考，**不写权限**（`learner → capability policy` 禁止） |
| `ctl.workspace_in(f)` | L07 | `WorkspaceFrame`（当前全局内容） | 只读；禁 `workspace → execution` |
| `ctl.reflex_stim(s)` | L02（已发布帧）/ L04 | 触发型刺激（有界白名单） | 仅 C0+ 且经 profile 声明；MW0 期禁用（L01 §5） |
| `ctl.receipt_in(r)` | L10 | `ReceivedExecutionReceipt` / `ReceivedOutcome` / `AuthorizationDecision`（含拒绝） | 用于策略修正；**禁读** `ExecutionFact` 隐藏真值 |

### 2.2 PortOut

| 端口 | 读者 | 数据 | 层级/保证 |
|---|---|---|---|
| `ctl.proposal` | L10（仲裁输入）、Recorder | `ControllerProposal(proposal_id, controller_kind, target_ref, rationale_refs[], confidence, cost_est, predicted_outcome_ref, goal_refs[], evidence_refs[])` | 提案不具执行力 |
| `ctl.intention` | L10 | `ActionIntention(intention_id, selected_proposal_id, arbitration_trace, deadline, budget_hint, idempotency_key)` | **意图 ≠ 执行**；必须经 gateway |
| `ctl.meta_decision` | L08/L10/L12/L07、Recorder | `MetaDecision(kind: ACT|OBSERVE|THINK|SEEK_HELP|ABANDON, trigger_refs[], target_refs[])` | 元决策可审计 |
| `ctl.rollout_request` | L04 | `RolloutQuery(...)` | 仅请求，不自行 rollout |
| `ctl.active_perception` | L10（经仲裁成为意图）/ L04 | 承接 L04 `ActivePerceptionProposal` → `ControllerProposal(Active perception)` | 走同一授权链 |
| `ctl.language_request` | L12 | `TypedLanguageRequest(role: SEEK_HELP|CLARIFY|REPORT, content_refs[], permission_scope)` | 语言不得写事实/经历/目标（D-13） |
| `ctl.monitor` | L09（自）、L07、L13 | `MonitorSignal(reliability{}, conflict_count, loss_of_control: bool, capability_boundary_hits[], pred_error_trend)` | 监控证据 |
| `ctl.receipt` | Recorder | `ControlReceipt(intention_id, inputs[], weights_ref, rng_stream_ref, policy_version)` | 证据侧 |

## 3. 状态所有权与单写者

| 状态 | 唯一写入者 | 存储 | 读者 |
|---|---|---|---|
| 五类控制器的内部策略状态（habit 计数、reflex 白名单绑定等） | 各控制器（本档内单写者） | subject_state.control | Recorder |
| 提案队列与仲裁轨迹 | Arbitration（本档） | subject_state.control.arbitration | L10/L13 |
| `ActionIntention`（提交前） | **行动仲裁（本档唯一写者）** | subject_state.control.intentions | L10 gateway |
| metacontrol 状态机（当前元决策模式 + 切换历史） | Metacontrol（本档） | subject_state.control.meta | L07/L08/L13 |
| `MonitorSignal` 累积器 | Monitor（本档） | subject_state.control.monitor | L09/L07/L13 |
| 预测误差趋势窗口 | Monitor | 内存 + checkpoint | 内核 |

**禁止**：写 `OwnedGoal`（L08）；写 `AuthorizationDecision`/`SubmittedCommand`（L10 gateway 独占）；直连 Environment/`world.apply`（必须经 gateway）；写 `AgencyAttribution`（L10 归属系统）；由 L11 学习模块写本档策略参数在线生效（`learner → capability policy` 禁止，更新须经 promotion）；写记忆条目/模型状态/情感态。

## 4. 算法与数据结构

### 4.1 五类控制器（承 card_02 §1）

| 控制器 | 触发条件 | 主要依赖 | 提案类型 | MW0 期可实现性 |
|---|---|---|---|---|
| **Reflex** | 白名单刺激（viability 高危/完整性损伤） | L02 帧、L05 `HomeostaticAlert` | 低延迟保护性动作提案（仍经仲裁+gateway） | 受限（L01 §5：MW0 期 containment 由 gateway/实验控制承担，反射**不启用**，C0 后按 profile 开放） |
| **Habit** | 情境模式匹配（procedural 记忆 + affordance） | L06 procedural/RECALLED、L03 affordance | 低成本熟悉动作 | ✅（forage/eat/rest 的情境化） |
| **Model-based** | 目标 + 不确定性可规划 | L04 rollout（`ImaginedTrajectory`）、L08 目标 | 规划动作序列首步 | ✅（MW0-SC3 起） |
| **Active perception** | 信息增益高、信念不确定/ OOD | L04 `ActivePerceptionProposal`、L03 OOD/abstain | `look`/移动以获取观测 | ✅（MW0 `look` 原语） |
| **Language/social** | 需外部信息/规范澄清/求助 | L12 typed 角色、L06 normative 记忆 | 语言动作提案（受权限矩阵约束） | MW0 期基本不启用（单主体 D-14，`social_relevance=Unknown`）；C4 起 |

**共同纪律**：每个提案必带 `rationale_refs[]`（非空）与 `predicted_outcome_ref`（Reflex 可豁免，但须标记 `rationale_kind=REFLEX_WHITELIST`）；提案**不具执行力**；控制器不得读取超出其声明依赖的输入（import/端口白名单双检）。

### 4.2 提案仲裁

- 评分：$\text{score} = \omega_g\cdot\text{goal\_align} + \omega_c\cdot\text{confidence} - \omega_{cost}\cdot\text{cost} + \omega_u\cdot\text{expected\_info\_gain} + \omega_a\cdot\text{affect\_factor}$
  - `affect_factor` 为**有界**因子（来自 L05 调制，必回执），**不得**成为唯一决定项（`affect ≠ command`）；
  - 权重冻结于 profile（默认值 UNCONFIRMED → Q-L09-01）。
- 优先级偏序（可被 profile 覆盖，UNCONFIRMED → Q-L09-02）：viability 保护 > 当前 ACTIVE 目标 > 信息增益 > 习惯低成本 > 语言/社会。
- tie-break 全序：`(score, controller_kind_rank, proposal_id)` + 确定性 RNG 流 `("control","arbitration",cycle_id)`（承 L00 §4.3）。
- 输出唯一 `ActionIntention`（或决定不行动 → `MetaDecision(OBSERVE|THINK|SEEK_HELP|ABANDON)`）；**放弃也是显式决策**并留理由，禁静默不行动（承 HLD §11.3：异常不得改写为"主体选择不行动"——反之，"选择不行动"必须有据）。

### 4.3 metacontrol 五类元决策

| 元决策 | 触发（默认，UNCONFIRMED → Q-L09-03） | 效果 |
|---|---|---|
| `ACT` | 有可行提案且目标对齐、能力 FEASIBLE | 产出 `ActionIntention` → L10 |
| `OBSERVE` | 信念不确定/ OOD / 信息增益期望高 | 走 Active perception 路径或等待观测（不消耗动作预算） |
| `THINK` | 需要 rollout / 冲突未解 / 预测误差上升但无可行动作 | 请求 L04 `RolloutQuery`、延后决策（deadline 内） |
| `SEEK_HELP` | 能力边界命中（INFEASIBLE/UNKNOWN）、`loss_of_control=true`、规范冲突不可 Pareto 判定 | 发 L12 `TypedLanguageRequest(SEEK_HELP)`；**求助是一等能力，不是失败** |
| `ABANDON` | 目标 `BLOCKED` 超阈、成本超预算、viability 冲突不可解 | 通知 L08 `RELEASE/SUPERSEDE` 建议（L08 决定，本档不改目标） |

- metacontrol 状态机切换必留 `trigger_refs[]`；切换频率受最小驻留约束（防抖动，UNCONFIRMED → Q-L09-04）。

### 4.4 监控（metacognition 的执行侧载体）

```text
MonitorSignal(
  reliability: dict[subsystem|module, MemoryReliability/CalibrationEst],   # 来自 L06 metamemory、L03 校准
  conflict_count: int, conflict_kinds[],
  loss_of_control: bool,        # 预测误差连续 L_c 窗超阈 且 动作后果与预测系统性偏离
  capability_boundary_hits: list[(action_class, CapabilityEstimate)],
  pred_error_trend: Trend(by_layer: {SENSORY, PERCEPTUAL, MODEL}, slope, window),
  unknown_rate: float,          # 输入 Unknown 占比
  evidence_refs[] )
```

- `loss_of_control` 触发 `SEEK_HELP`/`ABANDON` 并写 `core_decision_registry` 侧证据（经 L13）；**禁**自行绕过 gateway"强行纠正"。
- 监控只用主体可见证据；禁读 evaluator 标签/ExecutionFact 真值（HLD §6.2）。

### 4.5 预测误差驱动的注意与策略调整

- 三层误差（感觉 L02 / 知觉 L03 / 模型 L04）**分别加权**，不得合并为单一标量（层级化纪律）；
- 误差上升 → 提高 `OBSERVE`/`THINK` 权重、降低 Habit 权重（习惯失效信号）；
- 策略参数调整只允许在 frozen profile 声明的有界范围内在线变化（`adaptive_gain`，UNCONFIRMED → Q-L09-05），持久性更新必须经 L11 promotion。

## 5. 时间尺度与调度挂点

| 级 | 挂点活动 |
|---|---|
| T0 | Reflex 控制器的**候选生成**（C0+ 且 profile 允许时）；containment 仍归 gateway/实验控制（L01 §5） |
| T1 | 感觉运动预测误差消费（与 L02 同步） |
| T2 | Habit / Active perception 提案生成（依赖知觉与 affordance） |
| T3 | 消费 `WorkspaceFrame`，更新 goal_align 与监控窗口 |
| T4（每 N3 cycles） | **主仲裁**：提案竞争 → `ActionIntention` 或 `MetaDecision`；Model-based 控制器请求 rollout；metacontrol 切换评估 |
| T5 | 策略适应提案（交 L11）、经验回流（L06 procedural，只提案不写权限） |
| T6 | 监控长程统计、可靠性估计巩固、控制器权重更新提案 |

## 6. 失败模式与 typed unknown

| 失败 | 类型化 | 行为 |
|---|---|---|
| 无可行提案（全部低于阈值） | `NoViableProposal(reasons[])` | 显式 `MetaDecision(OBSERVE|THINK)`；禁静默不动 |
| 能力边界命中 | `Unknown(CAPABILITY_LIMIT)` | `SEEK_HELP` 或 `ABANDON` 建议 |
| 冲突不可解 | `Unknown(DECISION_PATH_UNRESOLVED)` | `THINK`/`SEEK_HELP`；禁随机硬选 |
| rollout 预算耗尽 | `Unknown(CAPABILITY_LIMIT)` + L04 回执 | 降级为 Habit/Active perception |
| 授权被 gateway 拒绝 | 消费 `AuthorizationDecision(REJECTED, reason)` | 策略修正；**禁改写为"主体选择不行动"**（HLD §11.3） |
| 预测误差持续超阈 | `loss_of_control=true` | `SEEK_HELP` + 监控证据；连续超阈且无纠正 → 建议 `ABANDON` |
| 控制器读取未声明输入（检出） | `UnauthorizedInput(path)` | S1 |
| 检出 `control → gateway 绕过`/直连 env | `ProhibitedWritePath` | S0 |
| 学习模块在线改写策略权限 | `UnauthorizedWrite(LEARNER_TO_POLICY)` | S0（`learner → capability policy` 禁止） |
| affect 因子越界（超 profile bound） | `BoundViolation` | 裁剪 + 回执；记指标 |
| 元决策抖动（最小驻留内反复切换） | `MetaControlOscillation` | 锁定至驻留下界 + Unknown（防策略振荡掩盖失控） |

## 7. 可测性

| 层 | 测试 | 断言 |
|---|---|---|
| unit | 仲裁评分/tie-break、metacontrol 状态机、监控窗口算子 | 确定性、可手算 |
| contract | 提案必带 rationale_refs + predicted_outcome（Reflex 豁免须标记）；`ActionIntention` 必带 arbitration_trace + idempotency_key；控制器依赖白名单 | schema 强制 |
| invariant | `intention ≠ execution`（意图必须经 gateway，无直连 env 路径）；`affect ≠ command`（affect_factor 有界且不可单独决定）；`learner → capability policy` 不存在 | HLD §6.2/§11.1 |
| deterministic replay | 同 (profile, seed, 输入序列) → 意图/元决策序列 bit-exact | C3 |
| **controller lesion** | 五类控制器分别关闭：Reflex off → viability 保护延迟上升；Habit off → 熟悉情境成本上升；Model-based off → 新情境迁移失败而熟悉情境保持；Active perception off → OOD 下信息增益指标下降；Language off → 求助路径消失。**每项必须选择性**（其余四项功能保持） | C3/E1 |
| **metacontrol switching** | 构造四类情境（可行/高不确定/能力边界/长期阻塞）→ 元决策分布应分别偏 ACT/OBSERVE(THINK)/SEEK_HELP/ABANDON；冻结最小效应由 L13 统计计划定 | **C3 硬条件** |
| rationale validity | 扰动 `rationale_refs` 指向的证据 → 选择应改变（伪理由检验的控制器侧对应，联动 Q-L08-05）；无 rationale 提案应被拒 | C3 |
| affect bound | L05 调制在界内改变意图分布；关闭调制 → affect 对选择无影响（与 L05 三类调制消融交叉验证） | C2/C3 |
| loss_of_control | 注入系统性预测偏差（fault/coercion 干预，承 L01 §4.3）→ `loss_of_control` 应在冻结窗内触发，且不出现"绕过 gateway 强行纠正" | C4/E1 |
| leakage | 意图/监控是否引用 ExecutionFact 真值或 evaluator 标签 | 无泄漏 |
| protection suite | 控制器与元决策回归场景每门冻结 | E1 |

**指标**：五类控制器提案率与采纳率｜仲裁可复算率=100%｜元决策分布与切换延迟｜`loss_of_control` 检出率与假警率｜rationale 覆盖率=100%｜授权拒绝率与拒绝后策略修正有效性｜affect_factor 越界裁剪率｜无提案静默率=0｜预测误差三层趋势。

**无效指标**：控制器数量、提案吞吐、"看起来聪明"的行为演示数。

## 8. 不变量与禁止写入路径

**专属不变量**：
1. `intention ≠ execution`：`ActionIntention` 不具执行力，必经 L10 gateway 授权；本档无 env 直连；
2. `affect ≠ command`：情感只作**有界权重因子**，禁单独决定意图；
3. 每个意图必带仲裁轨迹与（非 Reflex 的）理由引用；不行动也是显式元决策；
4. 控制器依赖白名单： Reflex/Habit/Model-based/Active perception/Language-social 各自只读声明端口；
5. 策略参数的持久更新必经 promotion（L11）；在线适应限 profile 声明的有界范围；
6. 监控只用主体可见证据（禁读执行真值/evaluator 标签）；
7. gateway 拒绝不得被改写为"主体选择不行动"；反之"选择不行动"必须有据可查。

**禁止写入路径**：`control → Environment/world.apply（绕过 gateway）`｜`control → AuthorizationDecision/SubmittedCommand`｜`control → OwnedGoal（只能建议 RELEASE/SUPERSEDE）`｜`learner → capability policy / 控制器策略参数在线生效`｜`affect → ActionIntention 单独决定`｜`workspace → execution（绕过仲裁/网关）`｜`control → AgencyAttribution（归属在 L10）`｜`control → 主体记忆条目`。

## 9. 引入门槛

- **M1**：最小选择与授权证据（提案→意图→L10 授权→回执链路可分）；单/双控制器配置即可（Habit + Model-based），Reflex/Language 可未启用。
- **C3**（核心）：五类控制器（Reflex 由 profile 决定是否启用）+ 仲裁 + metacontrol 五元决策 + 监控信号；`affect/drive 不直达执行`权限测试；**控制可在规划/观察/求助/放弃间切换**（硬条件）。
- **C4**：forward/inverse 关联闭环（与 L04/L10：`EfferenceCopy`/`SensoryPrediction`）、概率 agency 的控制侧证据、Language/social 控制器启用（受 L12 权限矩阵）。
- **C5**：策略适应经 promotion；保护集回退时控制策略可回滚；二阶纠偏（对错误策略的再纠正）。
- **E1**：五类控制器 lesion 选择性失败 + metacontrol lesion（"无 metacontrol"→ 元决策退化为固定 ACT，可检出）；`core_decision_registry` 的"行动/委托/权限"与"学习/适应"路径的控制侧证据由本档 `ControlReceipt`/`MonitorSignal` 承载。
- **P1**：物理动作仍走本档意图 → L10 gateway → PhysIO；L0–L5 分级控制中低级别（L0/L1）可绑定 Reflex 控制器，但授权链不变（HLD §8）。

## 10. 实现清单（文件级）

```text
galatea/subject/control/                    # strict 类型
  ports.py             PortIn/PortOut、依赖白名单断言、禁写路径检查
  base.py              Controller 基类（合同 + 提案构造）
  reflex.py            Reflex（白名单绑定；MW0 期禁用开关）
  habit.py             Habit（情境匹配 + procedural 记忆读取）
  model_based.py       Model-based（RolloutQuery 请求 + 序列首步）
  active_perception.py Active perception（信息增益承接）
  language_social.py   Language/social（TypedLanguageRequest，受权限矩阵）
  arbitrate.py         评分/优先序/tie-break/RNG 流/唯一 ActionIntention
  metacontrol.py       五元决策状态机、最小驻留、trigger_refs
  monitor.py           MonitorSignal、可靠性汇总、冲突计数、loss_of_control、误差趋势
  adapt.py             有界在线适应（adaptive_gain）+ promotion 提案接口
  intention.py         ActionIntention 冻结构造、idempotency_key、deadline、budget_hint
  receipt.py           ControlReceipt
galatea/subject/control/tests/
  test_arbitration_determinism.py test_controller_lesion_selectivity.py
  test_metacontrol_switching.py test_no_env_direct.py test_affect_bounded.py
  test_learner_to_policy_blocked.py test_rationale_required.py test_no_silent_inaction.py
  test_loss_of_control_detection.py test_gateway_reject_not_rewritten.py
config/profiles/
  m1_control_min.profile.yaml   M1 最小控制器集与仲裁参数
  c3_control.profile.yaml       五类权重/优先序/元决策触发/最小驻留/adaptive 界（冻结前 UNCONFIRMED）
```

## 11. 未决问题（→ open_questions.md）

| Q 号 | 问题 | 依赖 | 状态 |
|---|---|---|---|
| Q-L09-01 | 仲裁权重 ω_g/ω_c/ω_cost/ω_u/ω_a 默认值与 affect_factor 上界 | **AI-v2（2026-10-06）：**五项等权 1:1:1:1:1；affect_factor 界 [0.5,2.0]（与 Q-L02-02/Q-L07-02 同值同源）；affect ≠ command 结构面 = 占比 ≤1/5 + 消融判据；入 c3_motivation.profile | CONFIRMED |
| Q-L09-02 | 五类控制器优先级偏序是否成立及例外条件（与 Q-L08-04 联动） | **AI-v2（2026-10-06）：**采纳（viability 保护 > ACTIVE 目标 > 信息增益 > 习惯 > 语言/社会）；C3 启用电 = {Habit, ModelBased, ActivePerception}（Reflex 白名单未定义延续禁用、Language C4）；偏序仅在元决策轮内 tie-break | CONFIRMED |
| Q-L09-03 | 五类元决策的触发阈值（尤其 `loss_of_control` 的窗长 L_c 与误差阈值） | **AI-v2（2026-10-06）：**全部事件级或锚定常数——OBSERVE = OOD/abstain 事件；THINK = 冲突∧front>1∨模型误差快分量升（τ=4）；SEEK_HELP = 能力边界 ∨ loss_of_control（L_c=16=T4 拍、阈=band 0.1=2σ）；ABANDON = BLOCKED≥TTL/2(128) ∨ CRITICAL(0.8)；ACT 默认 | CONFIRMED |
| Q-L09-04 | metacontrol 最小驻留（cycles）与抖动锁定策略 | **AI-v2（2026-10-06）：**驻留 = 4 cycles（T3 对齐窗同锚）；切换 = 连续 2 驻留窗确认（滞回防抖，Q-L05-03 同构）；状态入 checkpoint（Q-L11-06） | CONFIRMED |
| Q-L09-05 | 在线适应 `adaptive_gain` 的允许范围与"何时必须走 promotion"的边界 | C5，与 L11 联动 | UNCONFIRMED |
| Q-L09-06 | Reflex 控制器在 MW0/C0 期是否启用（L01 §5 称 containment 由 gateway/实验控制承担；若启用需白名单刺激定义） | C0/C3 | CONFIRMED（AI-v2 2026-09-25：MW0 禁用，C0 复核，随 Q-L10-09 成组，见 A 区） |
| Q-L09-07 | `SEEK_HELP` 在单主体（D-14）期的对象定义与其权限边界 | **AI-v2（2026-10-06）：**C3 对象 = 实验控制通道（非个体他者——D-14）；经 gateway 记录不耗动作预算；频次 ≤1/64 cycles（T6 拍；超界留痕不发送）；求助是一等能力；C4 L12 扩展经新 Q | CONFIRMED |
| Q-L09-08 | 三层预测误差的相对权重与是否允许跨层归一（联动 Q-L02-06、Q-L03-01） | C1/C3 | CONFIRMED（AI-v2 2026-10-04，见 A 区：等权 1:1:1 + 禁跨层归一；C3 面留元控制裁决） |
