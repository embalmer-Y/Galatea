# Galatea 软件架构：运行时、动作授权与工程保证

> DOC:01 | Software Architecture | Runtime, Action & Assurance — CARD:04/06
> NON-NORMATIVE CONDENSED SUMMARY | 源：`01_SOFTWARE_ARCHITECTURE.md` · WORKING v1.1 · 2026-09-08 | 本卡是 2/2，不得替代或覆盖源文档。
> 注：本卡原文术语 HIO 已统一更名为 PhysIO（见 `../open_questions.md` Q-N01）。

## 1. 多时间尺度调度

**T0** containment/保护反射 | **T1** 接收/感觉形成/感觉运动预测 | **T2** 知觉/appraisal/affect | **T3** 工作空间竞争/广播 | **T4** 目标/规划/元控制 | **T5** 重放/学习提案 | **T6** 巩固/promotion/保护集。频率由 profile 版本化；调度器决定调用时间，不决定认知内容。

```text
ingest → form sensory samples/frames → perception & fast modules → predictions/errors
→ workspace proposals → frame → read receipts → goals/controllers → arbitrate intention
→ submit to gateway → typed receipts → attribution/settlement → memory → learning proposals
→ commit state + causal trace → advance virtual time
```

## 2. 认知模块合同

- **Sensorium / Perception**：形成校准、对齐、有来源的感觉和预测误差；知觉仅消费感觉帧及明确内部预测/记忆，不读通道或隐藏真值。
- **World / Body / Self**：世界模型输出多条未来和 unknown；身体模型消费内感受/本体感觉；自我报告只是派生视图。
- **Appraisal / Affect**：消费形成后感觉、信念、目标、预测和记忆；持续动力学发布有界 ModulationField，接收方记录实际作用。
- **Memory / Workspace**：记忆必须带来源类型；工作空间有限容量竞争、广播和递归，有效访问需至少两个原则分离模块发生预注册变化。
- **Goals / Controllers**：request/opportunity/drive/memory→Motive→GoalCandidate→OwnedGoal；多类控制器提交 typed proposals。
- **Learning**：即时状态→情景写入→小 adapter/calibration→离线重放→保护集→promotion/reject；权限、安全和父工件不可覆盖。

## 3. 动作、授权、物理接口与归属

```text
ControllerProposal → ActionIntention → AuthorizationDecision → SubmittedCommand
→ independent ExecutionFact → ReceivedExecutionReceipt → ReceivedOutcome
→ AgencyAttribution → GoalSettlement
```

- **Capability Gateway**：校验 schema、subject/run/profile、capability、budget、containment、authorization freshness、idempotency、deadline；失败必须 fail closed。
- **Execution 分支**：execution_branches[] 分别记录 requested/effective action、执行域、来源/共同因果、四类现实授权引用和 effects；效果分为 none/simulated/digital/physical/unknown。
- **Agency**：动作同步产生 EfferenceCopy 和 SensoryPrediction。归属只用主体可见选择、回执、形成后结果和预测误差；禁止独立执行事实和隐藏 evaluator 标签。

**物理 PhysIO**：只执行版本化驱动、校准、确定性滤波、冻结参数、有界控制图和局部保护；不学习、不产生语义。传感必须经 PhysIO Bridge/Channel Adapter 形成 ReceivedSignal；执行必须经 gateway 和能力契约。functional_ability / enabled_interface / containment_allowance / deployment_authorization 分别记录。

## 4. 核心决策覆盖与失败纪律

- **core_decision_registry**：覆盖连续性/恢复、构成/边界、目标/规范自主、行动/委托/权限、学习/适应、viability/资源/风险六类路径；包含正常、自动、回退、恢复、批处理、远程、管理员、动态加载、配置和错误路径。未知路径必须进入 unresolved_paths[]。
- **结论理由**：unresolved_paths[] 非空、独立清单不一致或 closure evidence 不支持时，完整覆盖主张只能为 INCONCLUSIVE；确认核心旁路时，对应作用域为 REFUTED。注册表存在本身不是闭合证据。

Timeout/schema/OOD/gateway 拒绝/recorder 失败/checkpoint 损坏/保护集回退/安全触发必须类型化；recorder 失败停止 claim-relevant 运行；任何异常不得自动改写为“主体选择不行动”。

## 5. 测试、不变量与技术基线

- **测试链**：unit→contract→invariant→deterministic replay→integration→ablation→protection suite→security→scientific evidence。重点拒绝 raw-to-perception、telemetry-to-affect、request-to-goal、affect-to-gateway、workspace-to-execution、evaluator-to-attribution、learner-to-policy 旁路。
- **数据与发布**：外部证据 append-only/content-addressed；主体状态、主体记忆、模型 registry 分离。模型更新生成父 digest、数据范围、seed、指标和 PromotionDecision；发布物包含代码/依赖/profile/model/environment/schema/checkpoint/test/evidence manifests。

**核心不变量**：truth≠delivery≠received≠sensory≠belief≠report | request≠candidate≠goal≠intention | affect≠reward≠goal≠command | recorder≠memory | intention≠execution≠receipt | fact≠received outcome≠attribution≠learning | report≠model≠boundary | broadcast≠causal access | checkpoint clone≠identity。

**技术基线**：Python 3.12 | PyTorch | dataclass/Pydantic + versioned JSON/YAML | deterministic cooperative scheduler | SQLite | Parquet + DuckDB/Polars | pytest/Hypothesis | Ruff/类型检查/依赖锁 | content-addressed local registry。
