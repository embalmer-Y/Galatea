# Galatea 软件架构：工程边界、消息协议与状态所有权

> DOC:01 | Software Architecture | Foundations & State — CARD:03/06
> NON-NORMATIVE CONDENSED SUMMARY | 源：`01_SOFTWARE_ARCHITECTURE.md` · WORKING v1.1 · 2026-09-08 | 本卡是 1/2。优先级：基础 LOCKED > 冻结 profile/协议/统计计划 > 软件架构 > 开发计划 > HLD > LLD > ADR/代码。
> 注：本卡原文术语 HIO 已统一更名为 PhysIO（见 `../open_questions.md` Q-N01）。

## 1. 使命与顶层工程决策

| 决策 | 选择 | 原因 |
|---|---|---|
| 系统边界 / 进程 | 科学安全平面与主体平面分离；首期单机单进程模块化单体 | 实验系统不替主体认知；优先确定性、可调试性和低通信复杂度 |
| 计算 / 接口 | 逻辑 actor、多速率虚拟时钟、协作调度；typed ports + versioned schema | 支持并行递归和确定性提交；消除自然语言/自由字典隐式协议 |
| 状态 / 证据 | 单写者、多读者、版本快照；外部 append-only recorder | 责任和因果来源明确；主体不可修改独立事实 |
| 整合 / 感觉 | common schema + workspace + affect + prediction error；显式 Sensorium | 防工具拼盘；强制 ReceivedSignal→SensoryFrame→PerceptualBelief |
| 学习 / 执行 | 小范围可塑性、异步审查、promotion；capability gateway fail closed | 候选更新不覆盖原工件；认知输出不等于现实执行 |
| 模型 / 扩展 | 可替换小模型组合，LLM 仅局部角色；测量后再拆服务 | 防中央大模型劫持；只为已证明的瓶颈支付复杂度成本 |

**非目标**：复制人脑 | 证明意识/感质/人格 | 让 LLM 承担完整主体 | 门前建设完整平台 | 开放网络/shell/任意代码/物理能力 | 主体改写权限/证据/安全边界 | 单 reward 统一价值 | 数据库/总线/prompt 冒充整合 | 日志冒充记忆。

## 2. 系统上下文

```text
Human Researcher → Experiment Control API
  → Scientific & Safety Plane [Environment | Intervention | Channel Adapter | Gateway | Recorder | Evaluator | Registry]
  → declared channels
  → Cognitive Subject Plane [Embodiment/Sensorium/Perception | World/Body/Self | Drives/Appraisal/Affect |
       Memory/Workspace | Goals/Executive | Action/Attribution | Learning/Consolidation]
  → Cognitive Runtime Kernel [Clock | Scheduler | State | RNG]
```

运行时内核只提供时钟、调度、状态、随机流、检查点和资源服务，不得形成目标、选择认知内容、给出行动理由或解释结果。训练器、离线 evaluator、工作库、sealed evaluation 和未来物理 PhysIO 位于主体边界之外。

## 3. 跨模块消息协议

```text
CognitivePacket(event_id, subject_candidate_id, run_id, branch_id, activity_window_id, cycle_id,
  virtual_time, source_module, content_type, representation_level, schema_version, payload_ref,
  confidence, provenance, causal_parent_ids, access_scope, content_digest)
```

- **协议纪律**：Envelope 不可变；大 tensor 只读引用并带 digest；payload 有版本 schema；禁止匿名来源和字符串 unknown；修正以新事件引用旧事件；消费方记录 accepted/rejected/ignored/deferred。
- **表示层级**：RECEIVED / SENSORY_FORMED / PERCEIVED / PREDICTED / IMAGINED / RECALLED / EXTERNAL_STATEMENT。广播、缓存和存储不得静默提升层级；接收质量不等于真值概率。

## 4. 单写者状态所有权

| 状态 | 唯一写入者 | 关键读取/边界 |
|---|---|---|
| ChannelDeliveryFact / ReceivedSignal | channel adapter / 边界端 | 前者仅 recorder/evaluator；后者不可改写，仅供 Sensorium |
| SensorySample/Frame / PerceptualBelief | Sensorium / Perception | 感觉与信念分离；知觉不得读取原始通道 |
| World / Body / Self / Drive / Affect | 各模型、驱力、情感动力学 | telemetry、内感受和身体信念不可互填 |
| WorkspaceFrame / OwnedGoal | workspace / goal ownership | 广播需读取回执；请求不能直写目标 |
| ActionIntention / ExecutionFact | 行动仲裁 / 独立环境或 gateway | 意图不等于执行；主体不能读取执行真值 |
| AgencyAttribution / GoalSettlement | 归属 / 结算系统 | 仅用主体可见证据；迟到结果以 revision 表达 |
| LearningProposal / 长期模型版本 | 学习模块 / promotion gate | 候选更新不覆盖原工件 |
| core_decision_registry | 外部 registry builder | 主体不可写；存在不等于可达路径闭合 |

## 5. 必须机械禁止的写入路径

external request→OwnedGoal | LLM→world truth/episodic experience | affect→action gateway | evaluator label→subject attribution | recorder truth→belief（绕过声明通道） | environment/channel→PerceptualBelief | perception→raw channel | attention/affect/prediction→rewrite ReceivedSignal | Sensorium→fact/goal/intention/agency | 未闭合路径静默忽略 | learner→capability policy | orchestrator→subject memory | workspace→execution。
