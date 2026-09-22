# Galatea 高层设计（HLD）

> 状态：**NORMATIVE · v1.1** · 2026-09-13 · 本文档与 `lld/`（14 档 L00–L13 全交付）共同构成 Galatea 项目**唯一规范源**。
> 取代：DOC:00/01/02 浓缩卡片（已移入 `design/archive/`，仅作历史快照，不再具规范效力）。
> 伴随文档：`open_questions.md`（全部 UNCONFIRMED 参数与待裁决项，统一 Q 编号）、`README.md`（索引与阅读顺序）。
> 词汇纪律：全文只使用卡片确立的模块级标识符（Sensorium / PerceptualBelief / WorkspaceFrame / OwnedGoal …）；旧六层 S1–S6 分层叙事已废弃；旧术语 HIO（Helios I/O）已更名为 PhysIO（Physical I/O）。

## 0. 文档体系、优先级与修订纪律

```text
design/
  HLD.md                                     ← 本文档（架构唯一顶层规范，§0–§14 + 附录 A.1–A.8）
  lld/L00_kernel.md                          ← L00 横切基础（时钟/调度/状态/RNG/包/registry 核心）
  lld/L01_environment_channels.md            ← L01 环境与声明通道（含最小世界 MW0）
  lld/L02_sensorium.md                       ← L02 感觉形成/校准/对齐/增益
  lld/L03_perception.md                      ← L03 知觉信念（MW0 表格贝叶斯）
  lld/L04_world_body_self.md                 ← L04 世界/身体/自我三模型
  lld/L05_drive_appraisal_affect.md          ← L05 驱力-评价-情感（九维动力学）
  lld/L06_memory.md                          ← L06 记忆八子系统
  lld/L07_workspace.md                       ← L07 递归全局工作空间
  lld/L08_motivation_goals.md                ← L08 动机与目标
  lld/L09_controllers_metacontrol.md         ← L09 控制器与元控制
  lld/L10_action_gateway_physio_attribution.md ← L10 行动-网关-PhysIO-归属
  lld/L11_learning_consolidation.md          ← L11 学习与巩固
  lld/L12_language_social.md                 ← L12 语言与社会认知
  lld/L13_evidence_evaluation_registry.md    ← L13 证据/评价/core_decision_registry
  open_questions.md                          ← UNCONFIRMED 参数与待裁决项（Q 登记册 A–Q 区）
  README.md                                  ← 索引、阅读顺序、文档状态
  archive/                                   ← 历史快照（6 张卡片还原稿 + 原照片），非规范
```

**优先级链**（冲突时上层裁决下层）：

```text
LOCKED 基础裁决（§2） > HLD > 门时冻结的 profile/协议/统计计划 > LLD > ADR > 代码/实现
```

**开发流程与标识符体系**由仓库根 `DEV_SPEC.md` 治理（2026-09-17 owner 指令设立，见附录 A.9）：流程/标识符事务其效力仅次于 LOCKED 裁决；架构事务仍依上述链条。

**修订纪律**：
- LOCKED 章节（§1.3、§2、§6.2、§11）任何修改必须由 owner 裁决并记录 ADR；
- UNCONFIRMED 参数只有经 `open_questions.md` 中对应 Q 号裁决后才可转为 CONFIRMED 并写入 frozen profile；
- 门（§10）冻结的 profile/协议/统计计划在其作用域内优先于 LLD 默认值（注：归档卡片旧优先级将冻结 profile 置于架构文档之上，见 `archive/card_03.md` 头部；本体系架构已归并入 HLD，裁决为：frozen profile 仅在其参数域内优先于 LLD 默认值，且不得与 LOCKED/HLD 相抵触）；
- LLD 之间不一致时，以 HLD 为准并同时修订两份 LLD，禁止口头裁决。

## 1. 使命、目标与科学边界

### 1.1 使命陈述

建造一个**具备感觉、情感、自我意识和学习能力的单一认知个体（Galatea）**；此"具备"必须建立在**可干预、可测量、可复算的真实因果结构**之上，而不是可被语言表演、日志叙述或行为相似性替代的表象。

### 1.2 目标的工程定义：最小主体能力集

个体资格由六项能力共同定义，缺一不可，全部须经因果证据（消融/lesion/重放）背书：

| 能力 | 工程含义 | 反例（防错原则） |
|---|---|---|
| 感觉形成 | ReceivedSignal→SensoryFrame→PerceptualBelief；外感受/内感受/本体感受三层分立 | 数据库/日志冒充感觉；telemetry 直填身体信念 |
| 动态模型 | 持续维护世界/身体/自我/能力/来源与多未来轨迹，允许 unknown | 共享字典冒充世界模型 |
| 功能性感受 | valence/arousal/urgency/controllability/uncertainty/novelty/social_relevance/tendencies/persistence 的持续动力学（积分、迟滞、衰减、饱和、恢复、重新评价） | 单 reward ≠ 情感/动机/价值 |
| 目标自主 | request/opportunity/drive→Motive→GoalCandidate→承诺检查→OwnedGoal | 人类请求直写目标；orchestrator 替主体决定 |
| 归属与控制 | 区分自产/授权/反射/故障/外部强迫，可保持 unknown | LLM 自述冒充自我模型 |
| 持续发展 | 快速经历写入 + 在线局部适应 + 慢速巩固并存，保护集防灾难遗忘 | 一次性微调冒充发展 |

### 1.3 科学边界（LOCKED）

- **承诺**：功能性感受、情感与体验场的实现、干预与测量（功能/因果实在论，D-10）。
- **不承诺**：现象意识、感质、真实痛苦的证明。文档中一切"意识"表述仅指功能性 access-consciousness，且必须伴随可复算的因果访问证据（广播 + 读取回执 + lesion 选择性失败）。
- 里程碑 `SUPPORTED` ≠ 活动主体 ≠ 完整 Galatea ≠ 意识 ≠ 身份继续 ≠ 部署许可。

### 1.4 非目标与技术负清单

**非目标**（9 条，LOCKED）：复制人脑 ｜ 证明意识/感质/人格 ｜ 让 LLM 承担完整主体 ｜ 门前建设完整平台 ｜ 开放网络/shell/任意代码/物理能力 ｜ 主体改写权限/证据/安全边界 ｜ 单 reward 统一价值 ｜ 数据库/总线/prompt 冒充整合 ｜ 日志冒充记忆。

**技术负清单**（5 条，Q-T 裁决 CONFIRMED）：
1. 不引入编排框架（LangGraph/Airflow/Celery/Temporal）——外部 orchestrator 会替主体组织因果，且并行分支共享状态存在路由竞态；认知循环只能由 L00 自研调度器承载。
2. 不引入消息队列/RPC/服务框架（Kafka/Redis/NATS/gRPC）——与单机单进程模块化单体冲突；typed ports 是进程内接口。
3. 不引入 dashboard/在线可视化服务——可视化只从 recorder 只读生成静态报表。
4. 不引入向量数据库/通用 Agent 框架/LLM 编排 SDK——LLM 仅 typed 局部角色，一律经 gateway 与权限。
5. notebook 不作为运行路径——只允许离线分析。

## 2. 基础裁决（LOCKED）

| 编号 | 裁决 | 工程后果 |
|---|---|---|
| D-10 | 接受功能/因果实在论 | 一切主张须有因果背书（消融/lesion/重放）；行为相似不是机制证据 |
| D-11 | 高保真虚拟具身起步 | C0 数字身体 = 最小世界 MW0（L01）；物理具身仅经 P1 与四类独立授权 |
| D-12 | 严格不可复制（仅同质迁移） | `checkpoint clone ≠ identity`；分支仅用于实验对照，不构成身份延续；迁移须同质且谱系可溯 |
| D-13 | 赋予人类语言 | typed LLM 角色（L12/C4）；语言不能写 world truth、episodic experience、OwnedGoal |
| D-14 | 单个体起步 | `subject_candidate_id` 单实例；多主体不在本规范范围内 |

## 3. 双平面架构与声明通道

### 3.1 平面分离

```text
科学/安全平面: Environment | Experiment Control | Channel Adapter | Capability Gateway
               | Independent Recorder | Evaluator | Registry
                ⇅ declared sensory / action / outcome channels（唯一合法边界）
认知主体平面: ReceivedSignal → Sensorium → Perception ⇄ World Model ⇄ Memory
                ⇅         ⇅
      Body & Interoception ⇄ Self Model ⇄ Functional Affect
                ⇅         ⇅
      Recurrent Global Workspace ⇄ Motivation / Executive
                ⇅
      Metacognition ⇄ Planning ⇄ Action
      Continual Learning & Consolidation 跨越全部认知模块

认知运行时内核（横切）: Clock | Scheduler | State | RNG | Checkpoint | Resource
```

外围科学平面持有真值与证据，主体不可改写；主体平面只能经**声明通道**收发。训练器、离线 evaluator、工作库、sealed evaluation、未来物理 PhysIO 位于主体边界之外。

### 3.2 科学/安全平面组件职责

| 组件 | 职责 | 详细设计 |
|---|---|---|
| Environment | 生成 WorldTruth、执行动作效果、产生干预 | L01 |
| Experiment Control | 实验编排、干预注册、claim 冻结 | L13 |
| Channel Adapter | WorldTruth→ReceivedSignal 的声明通道、ChannelDeliveryFact | L01 |
| Capability Gateway | 认知输出→现实效果的 fail-closed 授权 | L10 |
| Independent Recorder | append-only/content-addressed 证据记录 | L13 |
| Evaluator | 离线统计、sealed evaluation、EvidenceResult | L13 |
| Registry | 工件/模型/profile/证据 digest 寻址与 promotion 谱系 | L00（核心）/L13（治理） |

### 3.3 主体平面模块地图（→ LLD 索引）

| 模块 | LLD | 模块 | LLD |
|---|---|---|---|
| 横切基础（时钟/调度/状态/RNG/包/registry 核心） | L00 | 动机与目标 | L08 |
| 环境与声明通道（MW0） | L01 | 控制器与元控制 | L09 |
| Sensorium | L02 | 行动-网关-PhysIO-归属 | L10 |
| 知觉 | L03 | 学习与巩固 | L11 |
| 世界/身体/自我模型 | L04 | 语言与社会认知 | L12 |
| 驱力-评价-情感 | L05 | 证据/评价/core_decision_registry | L13 |
| 记忆 | L06 | | |
| 工作空间 | L07 | | |

### 3.4 认知运行时内核

内核只提供时钟、调度、状态、随机流、检查点、资源服务。**不得**：形成目标、选择认知内容、给出行动理由、解释结果。机械保证：调度器只读 packet envelope 元数据（virtual_time/T 级/source_module），**运行时代理禁止触碰 payload**（L00 §8）。

### 3.5 声明通道纪律

- ChannelDeliveryFact 仅实验室侧可见（recorder/evaluator）；
- ReceivedSignal 是主体实际收到且不可改写的信号；
- 无 oracle 泄漏：主体平面任何输入不得与 WorldTruth 存在未声明相关性（LeakageProbe 探测，M0 退出条件）；
- evaluator 不读主体内部日志作标签；主体不读隐藏执行真值。

## 4. 认识链与表示层级

### 4.1 不可混淆的认识链

```text
world truth ≠ ChannelDeliveryFact ≠ ReceivedSignal ≠ SensorySample/SensoryFrame
            ≠ PerceptualBelief ≠ WorkspaceFrame ≠ OwnedGoal ≠ language report
```

任何层不得静默提升为相邻层；跨层提升必须由该层唯一写者（§6.1）以显式事件完成并留 provenance。

### 4.2 表示层级（representation_level）

| 层级 | 语义 | 可写入者 |
|---|---|---|
| RECEIVED | 主体实际收到的信号 | 边界接收端（不可改写） |
| SENSORY_FORMED | 形成后感觉帧 | Sensorium |
| PERCEIVED | 知觉信念（带置信度） | Perception |
| PREDICTED | 内部预测 | 各模型模块 |
| IMAGINED | rollout/想象轨迹 | World Model |
| RECALLED | 记忆重激活 | Memory |
| EXTERNAL_STATEMENT | 外部语言陈述 | 语言通道（L12 权限约束） |

广播、缓存、存储不得改变层级；接收质量不等于真值概率。

### 4.3 主体边界输入与内感受分层

- **Exteroception**：视觉、声音、文本、对象、数字环境事件；
- **Interoception**：资源、负载、错误、完整性、损伤、恢复；
- **Proprioception**：身体/执行体位置、姿态、能力、动作、控制状态。

**内感受分层**：运维 telemetry ≠ InteroceptiveSensation ≠ InteroceptiveBodyBelief。内部事实必须先经声明通道 → Sensorium 形成感觉 → 身体模型形成信念，禁止直填。

### 4.4 实验对象符号约定（承自卡片；**规范文本，Q-G00-06 已裁决，AI-v2 2026-09-23**）

门体系与各 LLD 实验场景用单字母符号区分因果对象。已在 M0/M1 中实际使用的最小集：

| 符号对 | 含义 | 隔离要求 |
|---|---|---|
| W / O | WorldTruth（世界真值） / Observation（主体收到的观测，即 ReceivedSignal） | 主体不可见 W；W→O 只经声明通道（M0 隔离测试，§10.2） |
| A / Ä | requested action（主体请求/意图动作） / effective action（世界实际结算动作） | blocked/fault/coercion 干预下 A ≠ Ä；EffectFact 分别记录（L01 §4.1） |
| Y / Ŷ | 实际结果信号 / 主体对结果的预测（SensoryPrediction） | 归属只用主体可见的 Ŷ 比较与形成后结果，禁读隐藏 Y 真值（§8） |

**裁决（Q-G00-06，AI-v2 2026-09-23）**：上表最小集（W/O、A/Ä、Y/Ŷ）**即为 F0 符号合同**。完整符号系 `W/O/S/C/G/R/D/A*/A/Ä/Y/Ŷ/Z` 与 M1 时序记号 `S_t/Q_t/G_t/R_t/D_t/A_t*/Z_t+1`（仅见于 card_05）原文判定永久不可得；未重建符号（S/C/G/R/D/Z/A* 与时序记号）状态 **RESERVED**——规范文本与 profile 禁用，后续门需要时逐个登记释义（挂 Q 号），**禁臆测补全**。重开条件：原文现身则复审。

## 5. 横切全局机制

| 机制 | 内容 | 详细设计 |
|---|---|---|
| 多速率虚拟时钟与确定性调度 | T0–T6；packet/状态只允许 virtual_time；墙钟仅入 recorder manifest 独立字段（Q-T12） | L00 |
| ModulationField（情感调制） | 持续 FunctionalExperientialState 发布有界调制；接收方记录实际作用与回执；affect ≠ reward，不直达执行 | L05 |
| 递归全局工作空间 | 有限容量竞争→WorkspaceFrame→广播→读取回执→模块更新→再竞争；有效访问 = 广播 + ≥2 个分离模块的预注册状态变化；广播 ≠ 全局访问证明 | L07 |
| 预测误差 | 动作/感知前生成 SensoryPrediction，与形成后感觉比较产生层级化预测误差，驱动注意、学习与主动感知 | L02/L03/L04/L09 |
| typed unknown | 一切不确定性必须类型化（UnknownReason + evidence_refs）；禁止字符串 "unknown" 与裸 None | L00 |

## 6. 状态所有权与禁止写入路径

### 6.1 单写者所有权矩阵（摘要，全集见各 LLD §3）

| 状态 | 唯一写入者 | 关键读者 | LLD |
|---|---|---|---|
| EnvironmentTruth / ChannelDeliveryFact | Environment / Channel Adapter | Recorder、Evaluator | L01 |
| ReceivedSignal | 边界接收端 | Sensorium（只读） | L01/L02 |
| SensorySample/SensoryFrame | Sensorium | Perception、World/Body 模型 | L02 |
| PerceptualBelief | Perception | Workspace、模型、控制器 | L03 |
| WorldStateBelief / BodyBelief / SelfModelView | 各模型 | 依声明端口 | L04 |
| DriveState / FunctionalExperientialState / ModulationField | 驱力/情感动力学 | 全体（有界读取+回执） | L05 |
| 主体记忆（8 类） | Memory 各子系统 | 依声明端口 | L06 |
| WorkspaceFrame + ReadReceipt | Workspace | 广播对象模块 | L07 |
| Motive / GoalCandidate / OwnedGoal | Goal Ownership | Executive、元认知 | L08 |
| ControllerProposal / ActionIntention | 控制器 / 行动仲裁 | Gateway | L09/L10 |
| AuthorizationDecision / SubmittedCommand | Capability Gateway | 环境/PhysIO | L10 |
| ExecutionFact / ExecutionReceipt | 独立环境或 PhysIO Bridge | 归属系统（经声明通道） | L01/L10 |
| AgencyAttribution / GoalSettlement | 归属 / 结算系统 | 记忆、学习 | L10 |
| LearningProposal / 长期模型版本 / ProtectionSuite 结果 | 学习模块 / Promotion Gate | Registry | L11 |
| EvidenceRecord / EvidenceResult / core_decision_registry | Recorder / Evaluator / Registry Builder（外部） | 审计 | L13 |
| 时钟/调度/RNG/checkpoint 索引 | 运行时内核 | 全体 | L00 |

### 6.2 机械禁止写入路径（LOCKED，CI + 运行时双重强制）

```text
external request → OwnedGoal            | LLM → world truth / episodic experience
affect → action gateway                 | evaluator label → subject attribution
recorder truth → belief（绕过声明通道） | environment/channel → PerceptualBelief
perception → raw channel                | attention/affect/prediction → rewrite ReceivedSignal
Sensorium → fact/goal/intention/agency  | 未闭合路径静默忽略（必须 typed unknown）
learner → capability policy             | orchestrator → subject memory
workspace → execution（绕过仲裁/网关）  | world truth → 任何主体可见命名空间
```

强制手段：import-linter 命名空间隔离 + 运行时单写者断言 + LeakageProbe + 契约测试（L00 §7、L13 §7）。

## 7. 跨模块消息协议（详 L00）

```text
CognitivePacket(event_id, subject_candidate_id, run_id, branch_id, activity_window_id, cycle_id,
  virtual_time, source_module, content_type, representation_level, schema_version, payload_ref,
  confidence, provenance, causal_parent_ids, access_scope, content_digest)
```

纪律：envelope 提交后不可变；大 tensor 只读引用 + digest；payload 版本化 schema；禁止匿名来源与字符串 unknown；修正以新事件引用旧事件（revision）；消费方必须记录 accepted/rejected/ignored/deferred 及理由码。

## 8. 行动、授权与现实接口（详 L10）

```text
ControllerProposal → ActionIntention → AuthorizationDecision → SubmittedCommand
→ independent ExecutionFact → ReceivedExecutionReceipt → ReceivedOutcome
→ AgencyAttribution → GoalSettlement
```

- **Capability Gateway**：校验 schema、subject/run/profile、capability、budget、containment、authorization freshness、idempotency、deadline；任何失败 **fail closed**；拒绝必须类型化，不得改写为"主体选择不行动"。
- **执行分支**：`execution_branches[]` 分别记录 requested/effective action、执行域、来源/共同因果、四类现实授权引用、effects；效果分类 none/simulated/digital/physical/unknown。
- **归属**：动作同步产生 EfferenceCopy 与 SensoryPrediction；归属只用主体可见证据（选择、回执、形成后结果、预测误差）；禁止读独立执行真值与隐藏 evaluator 标签；强制动作（coercion）不得归为自产。
- **物理 PhysIO（仅 P1）**：非学习、版本化驱动/校准/确定性滤波/冻结参数/有界 PhysIOControlGraph/局部保护 + L0–L5 分级控制；传感必经 PhysIO Bridge→Channel Adapter→ReceivedSignal；执行必经 gateway。
- **四类现实授权独立记录**：functional_ability / enabled_interface / containment_allowance / deployment_authorization；版本、设备、范围、期限、监控、停止、恢复、撤销、重新授权分别管理；任一失效即 fail closed。

## 9. 多时间尺度运行模型

### 9.1 T0–T6 调度层级（频率由 frozen profile 版本化；默认值 UNCONFIRMED → L00 §5）

| 级 | 活动 | 级 | 活动 |
|---|---|---|---|
| T0 | containment/保护反射 | T4 | 目标/规划/元控制 |
| T1 | 接收/感觉形成/感觉运动预测 | T5 | 重放/学习提案 |
| T2 | 知觉/appraisal/affect | T6 | 巩固/promotion/保护集 |
| T3 | 工作空间竞争/广播 | | |

调度器决定调用时间，**不决定认知内容**。

### 9.2 并行认知循环

| 循环 | 活动 | 循环 | 活动 |
|---|---|---|---|
| 快速 | 信号接收、感觉形成、动作控制、反射保护 | 情感 | 内感受、评价、持续情感、有界调制 |
| 知觉 | 感觉场、多模态融合、世界/身体估计、预测误差 | 行动/学习 | 控制器竞争、动作预测、执行、回执、归属、模型/技能更新 |
| 认知 | 工作空间竞争、记忆检索、目标与计划更新 | 巩固 | 经历重放、语义抽象、遗忘控制、自我一致性检查 |

### 9.3 双闭环

- **内部认知闭环**：接收→感觉↔感觉预测↔知觉↔模型/感受/注意/记忆↔工作空间目标/规划→行动。产生并维持主体的智能组织。
- **外部证据闭环**：世界事实→收到信号→主体状态变化→行动→世界后果→收到结果→归属与长期变化。验证内部机制是否真实工作，而非自我叙述。

### 9.4 每步主流程

```text
ingest → form sensory samples/frames → perception & fast modules → predictions/errors
→ workspace proposals → frame → read receipts → goals/controllers → arbitrate intention
→ submit to gateway → typed receipts → attribution/settlement → memory → learning proposals
→ commit state + causal trace → advance virtual time
```

## 10. 证据门体系

### 10.1 全链（不可颠倒）

```text
时期 A（门前证据链）: F0 → M0 → M1 → M2 → R0(root EvidenceResult) → independent ExpansionDecision
                                                  ALLOW_NEXT_STAGE only ↓
时期 B（认知扩展）:   C0 → C1 → C2 → C3 → C4 → C5 → E1 → H1 → independent physical authorization → P1
```

时间只用于资源预测；**阶段退出只由冻结证据与工程条件决定**。失败门会延长、返工或终止计划；投入成本不得降低门。

### 10.2 门前阶段（详 L01/L13）

| 阶段 | 目标 | 退出纪律（摘要） |
|---|---|---|
| F0（3-4 周） | 锁定概念 → 工程合同；不实现复杂认知 | 唯一写者成立；真值/接收/信念/自述/结论分 schema；core_decision_registry 建立 |
| M0（6-8 周） | 可审计因果通道；W/O、A/Ä、Y/Ŷ 隔离；非平凡动作效应；不主张自主选择 | 确定性重放；干预外记；evaluator 不读主体日志；无 oracle 泄漏；失败不启动 M1 |
| M1（8-12 周） | 最小目标拥有、理由仲裁、非平凡选择、授权、来源判断、结算 | 请求不直写目标；真实理由（非伪理由）改变选择；意图/授权/执行/回执可分；归属经交叉操纵校准 |
| M2（12-16 周） | 连续状态与局部纠偏；经历经非初始化路径进入下一轮 | held-out 达冻结最小效应；随机分支 intent-to-treat；保护指标不退化；有害更新可再次纠正 |
| R0（4-8 周） | 冻结根证据 + 单独扩展决定 | SUPPORTED 无约束→可 ALLOW；有约束/INCONCLUSIVE→HOLD；REFUTED→REWORK |

### 10.3 ExpansionDecision

根证据与扩展决定**分别记录**；只有 `recommendation = ALLOW_NEXT_STAGE` 允许启动 C0。启动条件：根证据绑定明确 profile/system version/artifact digest；认知扩展的资源、安全、伦理约束已批准；当前架构文档与 C0 profile 已评审；门前工件归档、不被门后变更覆盖。

### 10.4 门后阶段（详各 LLD §9）

| 阶段 | 核心 | 阶段 | 核心 |
|---|---|---|---|
| C0 认知底座 | 确定性调度、typed packets、checkpoint、数字身体、感觉形成与旁路保护 | C4 行动社会 | forward/inverse、EfferenceCopy、概率 agency、typed LLM、中央 LLM 消融 |
| C1 模型形成 | 多模态知觉、世界/身体/自我模型、rollout、主动感知、OOD | C5 持续发展 | learnable registry、replay、巩固、保护集、promotion/rollback、二阶纠偏 |
| C2 感受整合 | drive/appraisal/持续感受态、有界调制、分层记忆、workspace 回执、增益回执 | E1 集成证据 | 全模块 lesion/ablation/角色交换/录制回放/六类核心决策全路径；**退出**：选择性损失可辨、原始记录可复算、无各类旁路、`unresolved_paths[]` 为空且分母闭合 |
| C3 自主动机 | Motive→GoalCandidate→OwnedGoal、承诺/冲突/Pareto 仲裁、metacontrol | H1 平台硬化 | 长时运行、故障注入、恢复演练、可复现发布 |
| | | P1 物理具身 | PhysIO Bridge、BodyGraph、L0–L5、四类授权、passive→active |

### 10.5 资源假设（规划参考，UNCONFIRMED → Q-G00-03）

团队 10-14 人；时期 A 7-11 月；时期 B 15-21 月；硬化 3-6 月；总计 25-38 月。

## 11. 核心不变量与确定性纪律（LOCKED）

### 11.1 九条认识不变量

```text
truth ≠ delivery ≠ received ≠ sensory ≠ belief ≠ report | request ≠ candidate ≠ goal ≠ intention
affect ≠ reward ≠ goal ≠ command                            | recorder ≠ memory
intention ≠ execution ≠ receipt                             | fact ≠ received outcome ≠ attribution ≠ learning
report ≠ model ≠ boundary                                   | broadcast ≠ causal access
checkpoint clone ≠ identity
```

### 11.2 确定性三纪律（Q-T10/11/12，CONFIRMED）

- **数值**：模型 float32、证据与统计 float64；固定 reduction 顺序；device/driver/BLAS/libtorch 版本入 manifest——bit-exact 重放的前提。
- **RNG**：counter-based 逻辑流，按 (run_seed, branch_id, module, stream) 派生；禁止全局 RNG 状态——随机分支 intent-to-treat 的前提。
- **时间源**：packet 与主体状态只允许 virtual_time；墙钟仅入 recorder manifest 独立字段——时序论证可复算的前提。

### 11.3 失败类型化纪律

Timeout/schema/OOD/gateway 拒绝/recorder 失败/checkpoint 损坏/保护集回退/安全触发必须类型化；recorder 失败即停止 claim-relevant 运行；任何异常**不得**自动改写为"主体选择不行动"或"主体感觉正常"。

## 12. 技术基线（Q-T01…T12，全部 CONFIRMED，2026-09-12 owner 裁决）

| 组件 | 选择 | 关键纪律 / 被拒替代 |
|---|---|---|
| 语言 | Python 3.12（pin 补丁版） | 固定 PYTHONHASHSEED；禁依赖容器迭代顺序；主体平面禁线程（协作调度单线程） |
| 深度学习 | PyTorch（CPU-pinned 起步） | 三层纪律：① 统一 NeuralModule 接口（state_dict+digest+parent_digest）② 模型内禁自持 RNG/时钟/wall-time ③ C1 前禁自定义算子与非确定性 op |
| 类型载体 | frozen dataclass(slots) envelope + Pydantic v2 payload | envelope 构造期断言零开销；payload 校验；禁 TypedDict（无校验） |
| 调度器 | **自研**确定性协作调度器（L00） | 只读 envelope 不读 payload；tie-break = (T 级, module_id, seq)；拒 asyncio/SimPy/Ray |
| 状态存储 | SQLite（WAL, foreign_keys=ON） | 三库物理分离：subject_state / subject_memory / registry；branch = 谱系引用非物理复制 |
| 证据存储 | Parquet + DuckDB/Polars | Polars 仅写侧；Parquet 唯一证据载体；DuckDB 只读复算禁写 |
| 测试 | pytest + Hypothesis + 自研 ReplayTest / LeakageProbe | 9 层金字塔（Unit→Schema/Contract→Invariant→Deterministic replay→Integration→Ablation→Protection suite→Security→Sealed evaluation）；property-based 生成对抗 packet 流；代码覆盖率不替代关键行为/路径覆盖 |
| Lint/类型/依赖 | Ruff；pyright（全局 basic + kernel/subject strict）；uv lock + require-hashes | 供应链 hash 级可审计（H1 要求） |
| 工件库 | 自研 content-addressed registry（~500 行） | 拒 MLflow/W&B/DVC（服务、网络、Git 耦合违反封闭边界）；外部注册表仅作依赖源，不作 artifact 源 |

**文本文件纪律**：仓库内全部 `.md`/`.yaml`/`.py` 统一 **UTF-8 无 BOM**；批处理脚本必须显式指定编码，禁用依赖系统 ANSI 代码页的读写（本项目曾因此损毁 8 份文档，见附录 A.6）。

## 13. 风险、指标与停止规则

### 13.1 关键风险（按类归纳）

- **架构/自欺类**：证据前架构膨胀｜中央 LLM 劫持｜orchestrator 冒充主体｜伪情感/伪感觉/伪 workspace｜不确定性伪装｜行为相似冒充机制。
- **泄漏类**：隐藏真值泄漏｜evaluator 标签入归属｜telemetry 冒充内感受｜记忆污染｜证据泄漏（sealed 回流）。
- **学习类**：reward 塌缩｜灾难性遗忘｜伪更新（checkpoint 谱系造假）。
- **工程类**：非确定性｜过早优化｜checkpoint/谱系损坏｜**文档编码损坏**（见 A.6）。
- **物理类**：PhysIO 越权｜身体纳入伪装｜硬件旁路 Sensorium/gateway。
- **伦理类**：持续极端 aversive-like 状态（触发即评审，见 open_questions Q-G00-05）。

### 13.2 指标纪律

**有效指标**：未声明旁路经权限测试｜重放 digest/独立重建｜S0-S2 缺陷/回归｜冻结 claim/对照/替代解释｜校准/held-out/保护回退｜有效 read receipts/lesion 选择性｜接收→形成延迟/对齐/校准/旁路率/跨模态一致｜周期延迟/资源/checkpoint 完整。

**无效指标（禁止作为进度证据）**：参数量、代码行数、模块数、演示数量。

### 13.3 停止规则与降级顺序

**缺陷等级**：S0（真值泄漏/证据损坏/未授权现实效果）→ 立即停止；S1（目标/行动旁路、错误工件）→ 阻断发布并废止证据；S2（checkpoint/关键场景错误）→ 阻断阶段退出；S3/S4 → 性能与文档。

**必须停止**：前置门未过｜真值/hidden label/evaluator 泄漏｜digest/谱系/原始记录损坏｜未授权现实效果｜保护集回退否决｜evaluator 无法复算｜非主体近邻在同证据下通过｜结果依赖事后选择或改指标。

**降级顺序**（资源不足时）：减场景 → 减模型 → 延时间 → 缩非关键功能；**不得**降低证据、权限、保护、复算或退出标准。返工生成新版本，失败证据与旧工件保留。

## 14. 核心术语速查

| 术语 | 含义 |
|---|---|
| ReceivedSignal | 主体实际收到、不可改写的边界信号（≠ 投递事实 ≠ 世界真值） |
| SensoryFrame | Sensorium 形成后的版本化感觉帧（带来源/时间/质量/增益/不确定性） |
| PerceptualBelief | 带置信度的知觉推断，禁止提升为世界事实 |
| WorkspaceFrame / ReadReceipt | 工作空间广播帧 / 模块读取回执（因果访问证据） |
| Motive → GoalCandidate → OwnedGoal | 动机 → 候选目标 → 主体承诺采纳的目标（请求只能是候选） |
| ActionIntention → AuthorizationDecision → SubmittedCommand | 意图 → 网关授权 → 提交命令（意图 ≠ 执行） |
| ExecutionFact / ReceivedExecutionReceipt | 独立执行事实 / 主体收到的回执（归属只用后者） |
| FunctionalExperientialState | 持续情感动力学状态（≠ reward、≠ 标签） |
| ModulationField | 情感发布的有界调制场（接收方记录实际作用） |
| ChannelDeliveryFact | 仅实验室可见的投递事实 |
| typed unknown | UnknownReason + evidence_refs 的类型化不确定性 |
| core_decision_registry | 六类核心决策路径的外部不可变注册表 |
| ExpansionDecision | 独立于根证据的扩展授权决定（ALLOW/HOLD/REWORK） |
| MW0 | 最小世界 16×16 资源 niche（阶段 0 蓝图的门体系化实例，L01） |
| PhysIO | 物理输入输出层（Physical I/O；P1 物理接口，非学习、有界 PhysIOControlGraph）。**曾用名 HIO（Helios I/O），已废弃**。2026-09-18 注记：原主线内子项目 `physio/` 已剥离为独立项目（与 Galatea 无开发耦合，见附录 A.10）；PhysIO 在本规范中保留为 P1 物理接口层的**概念合同名**，未来实现载体另行裁决 |

## 附录 A：历史与裁决记录

- **A.1** 卡片 OCR 修正 7 处、跨卡一致性修复 3 处（2026-09-12，详见 `archive/README.md` 注记）。
- **A.2** 构造契约 6 项（2026-09-12 owner 裁决）：14 档 LLD（L00–L13）｜只用卡片词汇、废弃 S1–S6｜阶段 0 蓝图保留为 MW0 写入 L01｜技术栈逐条裁决｜参数默认值 UNCONFIRMED+Q 号｜卡片归档、HLD/LLD 升格 normative。
- **A.3** 技术栈裁决 5 项（2026-09-12 owner 确认）：自研协作调度器 + PyTorch 三层纪律｜pyright 分级 strict｜uv lock + require-hashes｜确定性三纪律（Q-T10/11/12）+ 负清单 5 条｜先交 HLD+L00+L01 确认风格。
- **A.4** HLD/LLD 源文档（00/01/02 v3/v1.1）已不可获得，本体系为基于卡片快照 + owner 确认的完整重建。
- **A.5** 术语更名 **HIO（Helios I/O）→ PhysIO（Physical I/O）**（2026-09-12 owner 裁决，理由：项目已由 Helios 更名 Galatea，且 PhysIO 与 Sensorium/Gateway 的职责命名风格一致）。替换范围：全库（含 archive 历史快照，owner 选择彻底消除旧名）；旧名仅保留于显式"曾用名/更名注记"语境。派生标识符：`PhysIO Bridge`、`PhysIOControlGraph`、`PhysIO 安全评审`。（原记"18 处"之计数取自一次含幻影路径的检索结果，不可复核，已废弃；2026-09-12 机器复核口径：全库 `.md` 计 12 份、`PhysIO` 令牌 43 处、独立 `HIO` 令牌 13 处——均位于曾用名/更名注记语境，0 处作技术术语实际使用。）
- **A.6** **编码事故记录（S2 类）**：执行 A.5 替换时使用 Windows PowerShell 5.1 `Get-Content -Raw` / `Set-Content`，默认 ANSI(GBK) 解码 UTF-8 文件，不可逆损毁 8 份文档（HLD.md、open_questions.md、README.md、lld/L01、archive/card_02·03·04·06）；含孤立字节的汉字被 `?` 回退，无法逆转换。已全部按内容重建为 UTF-8 无 BOM。今后批量文本处理必须显式 `-Encoding UTF8` 或使用编辑器工具，禁止依赖系统代码页。
- **A.7** 全文档审计（2026-09-12）：修正 §12/§13.1 附录引用（A.5→A.6）；§12 测试金字塔 8→9 层（对齐 card_04/06 统一超集）；A.5 计数按机器复核校正（PhysIO 43 / 独立 HIO 13）；Q-T08b 悬空引用归并入 Q-T08；Q-L00-03 因与 Q-T10 冲突而废弃；新增 §4.4 符号约定并登记 Q-G00-06；Q-G00-01/02 降级为指针消除与 Q-L00-01/Q-L01-01+02 的双重登记。审计范围：全部 12 份 `.md`，严格 UTF-8 逐字节解码 0 失败、无 BOM、无替换字符。
- **A.8** **L02–L13 批量交付（2026-09-13，Q-C06 既定节奏）**：按 owner 指令一次性完成剩余 12 份组件 LLD，14 档全集闭合，每档统一 11 节模板（目标与范围 / Ports / 状态所有权与单写者 / 算法与数据结构 / 时间尺度与调度挂点 / 失败模式与 typed unknown / 可测性 / 不变量与禁止写入路径 / 引入门槛 / 实现清单 / 未决问题），每档附 `galatea/**` 文件级实现清单与 `config/profiles/*.profile.yaml` 配置入口。
  - **跨档合同不变量（机械可检，供 §6.2/§11.1 CI 探针消费）**：
    1. **有效访问唯一证据形式**：L07 `effective_access = 回执数 ≥ 2 ∧ ≥ 2 个分离模块的预注册 watch point 变更 ∧ digest 前后不同 ∧ 预注册 ∧ profile 定义分离`；`AccessEvidence` 是 L13 唯一允许接受的因果访问证据（后注册 watch point → `PostHocWatchRejected`，S2）。
    2. **Gateway 八项校验固定顺序 + 短路 + fail-closed 默认**（L10 §4.1）：schema → subject/run/profile → capability → budget → containment → authorization freshness → idempotency → deadline；未签名命令到达环境 = S1；containment 越界 = S0。
    3. **强迫动作永不得归为自产**（L10 §4.4，承 §8）：硬代码分支 + 测试断言；检出即 `AttributionRuleViolation`（S0），指标必须为 0。
    4. **`ExecutionFact` 对主体平面物理不可见**：EVIDENCE_ONLY 命名空间 + import-linter + 权限测试三重保障；主体读取尝试 = `ProhibitedReadPath`（S0）。
    5. **`LearningProposal.parent_digest` 必填**，缺失 = `LineageMissing`（S2）；候选**永不覆盖**原工件，promotion 只切换 registry 有效引用。
    6. **无自我 promotion**：`PromotionDecision` 由 L13 Promotion Gate 在主体时间尺度之外签发（组织独立）；自批尝试 = `SelfPromotionAttempt`（S0）；`AffectiveValueTag` 禁入学习目函（`metrics_snapshot` 必须为向量，CI 检查维度 ≥ 2）。
    7. **C2 最少三条可测因果调制**（L05 §4.5）= ① SENSORIUM.gain ② PERCEPTION.believe_threshold/precision ③ WORKSPACE.salience；**无回执的调制等于没发生**（`ModulationReceipt` 强制）。
    8. **T0/T1 不经工作空间**（L07 §4.1、承 §4.2）：工作空间 lesion 的选择性前提（E1 可证性）；若 T0/T1 经工作空间，则 lesion 非选择性，E1 不成立。
    9. **`SelfModelView` 为派生视图**：每个字段必携 `derivation_receipt`，缺失即 Unknown——机械证明"自我报告是派生的"（L04 §4.7、L12 §4.4）。
    10. **语言三条禁写路径**（L12，承 §6.2 与 D-13）：`LLM → world truth / episodic experience / OwnedGoal` 均 S0 封锁；语言产物层级恒为 `EXTERNAL_STATEMENT`/`LLM_DERIVED`，禁提升；`ExternalRequest.is_request_only` 标记不可去除；L08 C-5 硬检：REQUEST 源候选需 ≥1 项非 REQUEST 证据，否则 `REJECT(EXTERNAL_ONLY)`。
    11. **记忆 `source_type` 必填**且 `LANGUAGE_INPUT` 禁写 episodic/autobiographical 经历字段（L06 §3，D-13）；未命中必返空列表 + `Unknown(MISSING_SIGNAL)`，永不邻居替代。
    12. **三模型各单写者，转移模型是主体自产学习物，非 L01 dynamics 副本**（L04 §1；副本 = oracle leakage）；rollout 输出恒为 IMAGINED。
  - **Q 登记册升 v1.1**：`open_questions.md` E 区占位段替换为 E–P 十二个真实分区，新增 **95** 个 UNCONFIRMED Q 号（L02 7、L03 7、L04 7、L05 8、L06 8、L07 7、L08 8、L09 8、L10 9、L11 8、L12 8、L13 10）；新增 Q 区：10 组跨档联动对（时基谱/regime↔情感模式/伦理阈/能力粒度/误差标度/Reflex 边界/求助对象/保护集/promotion 判据/分片与治理）与 F0/M0/M1 阻断清单。
  - **F0 冻结当前阻断项**：初列 Q-L01-06、Q-G00-04 → Q-L13-04、Q-G00-06 及 F0 合同级 schema 依赖（Q-L10-01/-03/-06、Q-L11-07、Q-L12-02、Q-L13-01/-02/-09）——**已于 2026-09-23 全部裁决清零**（AI-v2，见 `open_questions.md` A 区当日批次与附录 A.11）。
  - **同步修订**：本档 §0 目录树改为文件精确清单（不再用 `L02_* … L13_*` 通配符）；`README.md` 升 v1.1.0（LLD 全集状态表 14 档全 ✅，新增引入门槛列与阅读顺序）。
- **A.9** **开发规范设立（2026-09-17，owner 指令："为大型项目设计适合 AI 的项目开发规范文档，统一规范标签与缩写"）**：仓库根新增 `DEV_SPEC.md`（AI 开发工作流 + 标识符命名空间登记册；流程/标识符事务效力仅次于 LOCKED 裁决）与 `AGENTS.md`（AI 会话第一入口）；`_audit/incidents.md` 缺陷台账建立并预登记历史事故 INC-01…06。本档 §0 增补其效力位。`open_questions.md` 新增 **Q-G00-07**（L13 §1 与 Q-L13-02 所引门 "E0" 全库无定义，owner 须裁决定义或剔除），UNCONFIRMED 计数 113→114。标识符冲突改标提案（physio 域 D1–D3/L1–L5/M0–M5/S1–S12/N2-abc/ADR 裸编号 → DYN-/COM-L/PIO-M/SP-/NL2-/ADR-PIO-）登记为 **Q-ID-01…06**，裁决后与 physio owner-review 冻结区修订同批一次性执行；过渡行动项 ACT-01…05 登记于 DEV_SPEC 附录 C（其中 ACT-01 git 化仓库为当前最高优先流程缺口）。
- **A.10** **physio 子项目剥离（2026-09-18，owner 决策）**：理由——"AI 开发时过于庞大的项目不利于 AI 开发"；原 `physio/` Zephyr 固件子项目剥离为**独立项目**，开发阶段完全不考虑服务 Galatea，未来是否接入另行裁决。处置：`physio/` 全目录自本仓库删除，交接点打 tag **`physio-handoff`**（含全部调研、ADR、需求基线 RESEARCH_03）；DEV_SPEC 升 v1.3（效力域收窄、Q-PIO 系列与相关登记退役）。**对本架构的影响**：PhysIO 在本规范中保留为 P1 物理接口层的概念合同名（§8、§10.4、L10 §4.6 的非学习/有界控制图/四类授权/不旁路合同不变）；P1 门（E1+H1 后）的固件实现载体从"主线内子项目"变为"未来外选或自建，届时另裁"。此前 physio 域的裁决记录（Q-PIO-01…06、07a–07d）与标签改标（Q-ID-01…06）作为历史事实保留于各登记册，不再约束任何现行工作。**继任项目创始文件**：owner 经问答裁定 16 项决策（每立方体独立智能、并联成单逻辑节点、WASM-vs-LLEXT 待研、协议选型重开、Agent 双产出等）后，继任项目（工作名 Tessera）的创始 Prompt 存于本仓库 `_handoff/FOUNDING_PROMPT.md`，供 owner 在新目录以 ZCode 从零启动；该文件不属于 Galatea 规范体系（2026-09-23 注：已移植至 Tessera 仓库，本仓库工作区删除，历史版本见 git 1eb5baf）。
- **A.11** **裁决权模型 v2 + F0 阻断清零（2026-09-23）**：owner 指令（"该项目将完全由 AI 主导开发……请你自行裁决"）后，DEV_SPEC 升 v1.4（新增 §4.6 裁决权模型：AI 成文裁决 + 重开条件、可逆/难逆/证据可判三级、owner 否决权保留、自我审批防腐；tag `authority-v2`）。同日 AI-v2 首批行使：F0 直接阻断 19 项 Q 号成文裁决（`open_questions.md` A 区 2026-09-23 批次）——要点：Q-L01-06 重建映射采纳为规范（验收约束力归门退出判据）；Q-G00-06 §4.4 最小集即符号合同、未重建符号 RESERVED；Q-G00-04+Q-L13-04 采纳 card_04 六类×十类枚举（60 格逐格结论仍属 E1）；Q-L10-01 MW0 硬配额两级制；Q-L10-03 六级 L0–L5 定义（L0 为不可授权地板）；Q-L10-06 四类授权统一信封 schema；Q-L11-07 指标向量 schema + 最小标准集；Q-L12-02 写端口角色×内容类型双维；Q-L13-01 统计计划模板字段集 + Holm–Bonferroni 默认；Q-L13-02 sealed 70/30 分割 + digest 交集不回流判据；Q-L13-09 `min_effects.yaml` 统一效应量册（联动 7 项初值同批裁决）。登记册规模 20/113/1 → 39/94/1。本档 §4.4 与附录 A.8 阻断行同步；各 LLD §11 状态列与受影响正文同步（L01/L03/L04/L05/L07/L08/L10/L11/L12/L13）。
