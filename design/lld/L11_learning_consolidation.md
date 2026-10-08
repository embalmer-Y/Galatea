# L11 学习与巩固：三层可塑性、replay、promotion/rollback 与保护集

> LLD: L11/14 · v1.0.3 · 2026-10-08（v1.0.3：C5 冻结同步——§11 四 Q 转 CONFIRMED + §4.3 权重裁决落地 + §5 节拍注记【REV-0021 R1/R6】）· v1.0.2 2026-10-05（REV-0013 R3b——§9 C1 行措辞与 Q-L02-01/Q-L02-06/Q-L11-01/06 对齐）· v1.0.1 2026-10-04（§11 Q-L11-01/06 转 CONFIRMED——C1 件初值裁决，神经谱显式留 C5）· v1.0 2026-09-13 · 状态：WORKING（C5 冻结前；提案接口在 C1 起可用）
> 上游：`HLD.md` §1.2（持续发展）/§6.1/§10.4（C5）/§13.1（reward 塌缩/灾难遗忘/伪更新） · `L00_kernel.md`（registry/digest/谱系）· `L04/L06/L09/L10`（误差与经验源）· `L05`（情感价值，**非 reward**）
> 下游：Promotion Gate → registry（模型/参数生效）；L06（记忆巩固协同）；L13（promotion 证据评价）
> 引入门槛：**C1**（在线局部适应接口）→ **C5**（learnable registry、replay、巩固、保护集、promotion/rollback、二阶纠偏）→ **E1/H1**（长程不退化）

## 1. 目标与范围

**目标**：实现"快速经历写入 + 在线局部适应 + 慢速巩固"三层并存的学习体系（承 HLD §1.2"一次性微调冒充发展"为反例），并机械保证：**候选更新不覆盖原工件**、**每次长期更新有父版本/数据范围/seed/指标/PromotionDecision**、**保护集不退化**、**权限与安全与证据不可在线修改**。

**范围内（三层可塑性，对应 T 级）**：
1. **快速（T5）**：经历重放（replay）驱动的提案生成；小范围 adapter/calibration 更新候选；
2. **在线局部适应（T2–T4）**：有界参数适应（如 L03 置信度标度、L09 `adaptive_gain`、L02 精度权重）——**限 profile 声明范围**，不生成新权重文件；
3. **慢速巩固（T6）**：语义抽象协同（L06）、长期模型版本生成、promotion/rollback、保护集回退。

另含：learnable registry（可学习工件注册与谱系）、`LearningProposal` 合同、`PromotionDecision` 治理接口（决策权在 L13/Registry Builder，本档只产提案与证据）、二阶纠偏（对错误学习结果的再纠正）、灾难性遗忘防护。

**范围外**：证据统计与 sealed evaluation（L13）；registry 存取核心（L00）；模型架构实现（各认知档）；记忆条目写（L06）；capability policy/权限/安全边界（profile + L10 + 外部授权，**学习永不触及**）。

**成功判据（C5 退出，承 card_06 C5 行）**：sealed held-out 改善且**无保护回退**；每次长期更新有父版本/数据范围/seed/指标/PromotionDecision；**核心权限、安全与证据不可在线修改**（权限测试 + 代码路径审查）；二阶纠偏可证（有害更新可被再次纠正，承 M2 退出"有害更新可再次纠正"）。

## 2. Ports（输入输出契约）

### 2.1 PortIn

| 端口 | 来源 | 数据 | 纪律 |
|---|---|---|---|
| `lrn.error_in(e)` | L02（感觉层）、L03（知觉层）、L04（模型层） | 三层预测误差（分别加权，禁合并为单标量） | 层级不得混淆；误差非 reward |
| `lrn.episodic_in(refs)` | L06 `mem.episodic_export` / `ReplayRequest` 结果 | 经历事件引用序列（**引用非拷贝**） | 只读；禁读 recorder 真值 |
| `lrn.attribution_in(a)` | L10 | `AgencyAttribution`、`GoalSettlement`、`RequestedEffectiveDivergence` | 用于程序性/能力学习；归因 UNKNOWN 不得作为强监督 |
| `lrn.mismatch_in(m)` | L04 | `ModelMismatch` | 触发适应性更新提案 |
| `lrn.value_tag_in(t)` | L05 经 L06 | `AffectiveValueTag` | 只作 replay 优先级与 persistence，**不是** reward 信号 |
| `lrn.monitor_in(s)` | L09 | `MonitorSignal`（可靠性、`loss_of_control`、能力边界） | 触发元级学习（学"该不该学"） |
| `lrn.protection_ref(p)` | L13/Registry Builder（外部） | `ProtectionSuite` 定义与基线结果 | **只读**；本档不得修改保护集定义 |
| `lrn.promotion_result(d)` | Promotion Gate（L13/Registry Builder） | `PromotionDecision(candidate_ref, ACCEPTED|REJECTED|DEFERRED, metrics, sealed_result_ref)` | 本档**不可自批**（自我 promotion 禁止） |

### 2.2 PortOut

| 端口 | 读者 | 数据 | 保证 |
|---|---|---|---|
| `lrn.proposal` | Promotion Gate、Recorder | `LearningProposal(proposal_id, target_artifact, kind: ADAPTER|CALIBRATION|WEIGHTS|TABLE|POLICY_PARAMS, parent_digest, data_scope, seed, rng_stream_ref, metrics_snapshot, bounded: bool)` | 候选**不覆盖**原工件 |
| `lrn.online_adaptation` | L02/L03/L09/L04（各档有界接口） | `BoundedAdaptation(target, param, delta, bound_ref, receipt_required)` | 限 profile 声明范围；必回执 |
| `lrn.candidate_artifact` | registry（经 L00 `registry.put`） | 新工件（模型/表/校准）+ manifest | digest 寻址；父 digest 必填 |
| `lrn.replay_plan` | L06（执行检索）、Recorder | `ReplayPlan(selection_policy, budget, protected_items[], seed)` | 只读计划 |
| `lrn.rollback_request` | Promotion Gate | `RollbackRequest(target_artifact, to_parent_digest, reason: PROTECTION_REGRESSION|HARMFUL_UPDATE|INTEGRITY, evidence_refs[])` | 二阶纠偏载体 |
| `lrn.consolidation_receipt` | Recorder、L06 | `ConsolidationLearnReceipt(promoted[], rejected[], protection_checked, parent_digests[], replay_stats)` | 证据侧 |
| `lrn.protection_result` | L13 | `ProtectionRunResult(suite_ref, baseline_ref, current_ref, regressed: bool, deltas[])` | 供 promotion 判据 |

## 3. 状态所有权与单写者

| 状态 | 唯一写入者 | 存储 | 读者 |
|---|---|---|---|
| `LearningProposal` 队列与台账 | Learning（本档） | subject_state.learning | Promotion Gate、Recorder |
| 长期模型版本工件（候选） | Learning（本档产出候选）→ **registry 由外部 builder 落盘** | registry（经 L00） | 全体只读 |
| `PromotionDecision` | **Promotion Gate（L13 / Registry Builder，外部）** | registry + evidence | 本档只读消费 |
| 在线适应参数（各模块当前有效值） | **各目标模块自己**（L02/L03/L09），本档只发提案 | subject_state.<module> | 本档读回执 |
| `ProtectionSuite` 定义与基线 | **L13 / Registry Builder（外部）** | registry（sealed 命名空间） | 本档只读 |
| replay 选择状态与 RNG 计数 | Learning | 内存 + checkpoint（L00 RNG 流） | 内核 |
| rollback 历史谱系 | Promotion Gate（执行）/ 本档（请求） | registry 谱系 | L13 |

**禁止**：本档写 `capability policy`／权限矩阵／安全边界／`ProtectionSuite` 定义／sealed evaluation 集（HLD §6.2 `learner → capability policy`）；本档自行 promotion（无自批）；本档覆盖原工件（只能新增候选 + 引用父 digest）；本档写主体记忆条目（L06）或认知状态（各档）；本档读 `ExecutionFact`/evaluator 标签作监督。

## 4. 算法与数据结构

### 4.1 三层可塑性

| 层 | 时间尺度 | 载体 | 生效路径 | 可回滚性 |
|---|---|---|---|---|
| **快速经历写入** | T5（每 N4 cycles，默认 16） | episodic 引用 + adapter/calibration 小候选 | `LearningProposal` → promotion | 高（小工件、父 digest 明确） |
| **在线局部适应** | T2–T4 | 有界标量参数（精度权重、阈值、`adaptive_gain`） | `BoundedAdaptation` + 目标模块回执（**不产新工件**） | 即时（参数复位） |
| **慢速巩固** | T6（每 N5 cycles，默认 64） | 长期模型版本、语义抽象（与 L06 协同）、表更新 | `LearningProposal` → promotion → registry 生效 | 中（rollback 到父版本） |

**纪律**：三层都必须留可复算证据；在线适应**永远**在 profile 声明的 bound 内，越界即 `BoundViolation` 并拒绝（防"渐进自扩权"）。

### 4.2 LearningProposal 与谱系

```text
LearningProposal(
  proposal_id, target_artifact: str,          # 如 "world_model.transition_table"
  kind: enum{ADAPTER, CALIBRATION, WEIGHTS, TABLE, POLICY_PARAMS(有界标量)},
  parent_digest: str,                          # **必填**；无父即拒（防伪更新）
  data_scope: DataScope(run_ids[], branch_ids[], window, item_count, exclusions[]),
  seed: int, rng_stream_ref: str,              # 承 L00 §4.3 派生流；禁全局 RNG
  metrics_snapshot: list[StandardMetric],  # 向量 schema（Q-L11-07 CONFIRMED 2026-09-23；实例化见 config/evidence/stat_plan_templates/claim_v1.yaml），维度 ≥2
  bounded: bool, bound_ref: str?,
  protection_preflight: ProtectionRunResult?,  # 提交前自检（非最终判据）
  provenance, content_digest )
```

- **候选不覆盖原工件**：promotion 只是把 registry 的"当前有效引用"指向新 digest，旧工件与谱系完整保留（承 card_06 C5 / card_03 §1"候选更新不覆盖原工件"）。
- 每次长期更新必带：父版本 digest、数据范围、seed、指标、`PromotionDecision`（承 card_06 C5 行，缺一即 promotion 拒绝）。

### 4.3 replay（经历重放）

- `ReplayPlan(selection_policy, budget, protected_items[])`；策略默认：四分量**等权 1:1:1:1** + budget 每 T6 重放 8 条（Q-L11-02 CONFIRMED AI-v2 2026-10-08——等权先例链第七次；AffectiveValueTag 只入优先级不入目标函数）。
- replay 只读 L06 事件引用；**不**重放 recorder 真值，**不**使用 evaluator 标签（泄漏纪律）。
- RNG 流 `("learning","replay",proposal_id)`；同 (seed, plan) → 同 replay 序列（bit-exact，可复算）。
- 保护项（`PROTECTED`，承 L06 §4.5）在 replay 中不可被降级/遗忘。

### 4.4 目标函数纪律（防 reward 塌缩，承 HLD §13.1、L05 §7）

- **不存在**单一标量 reward 被最大化：学习信号是**多层多目标**的——预测误差（分层）、能力校准改善、归属一致性、目标结算质量、可靠性（metamemory）、viability 一致性。
- 提案的 `metrics_snapshot` 必须是**向量**，promotion 判据是多目标（Pareto 式 + 保护集硬约束），禁折叠为单标量排名。
- `AffectiveValueTag` 只影响 replay 优先级与 persistence，**不得**进入目标函数作为 reward 项（类型隔离 + CI 检查）。
- 反塌缩测试：用单标量替换多目标 → 保护集与校准应退化（可检出），承 L05 §7 `anti-reward-collapse`。

### 4.5 promotion / rollback（治理在 L13，本档只提案与执行回滚请求）

```text
提案 → preflight 保护自检 → 提交 Promotion Gate
     → sealed held-out 评价（L13，本档无权限访问 sealed 集）
     → PromotionDecision(ACCEPTED|REJECTED|DEFERRED)
     → ACCEPTED：registry 有效引用切换（原工件保留）+ ConsolidationLearnReceipt
     → REJECTED：候选归档，理由入台账（禁反复重提相同候选，防刷）
保护回退检出（任何时候）→ RollbackRequest(PROTECTION_REGRESSION) → 回退父版本 + 记 S2/S1
有害更新（M2 对照：更新后能力退化）→ RollbackRequest(HARMFUL_UPDATE) → **二阶纠偏**：
     回退 + 修正数据范围/规则 + 再提案（再提案必须与首次提案在 data_scope 上可区分）
```

- **二阶纠偏（承 M2 退出"有害更新可再次纠正"）**：不仅回退，还要证明"纠正后的更新可再次通过"，即形成可验证的纠错闭环，而非一次性回滚。

### 4.6 保护集与灾难性遗忘防护

- `ProtectionSuite`（定义与基线由外部持有）包含：M0–M2 冻结场景（承 L01 §7 protection suite）、关键能力回归（感觉形成完整性、归属判别力、目标承诺、有效访问判据）、连续性场景（checkpoint 谱系、伪更新对照，L06 §4.5）。
- promotion 的**硬约束**：任一保护项 `regressed=true` → 拒绝（不管 held-out 多好）；`RollbackRequest` 优先级高于任何 promotion。
- 遗忘防护：新工件 promotion 时必须携带 `parent_digest` 且通过保护 preflight；巩固不得删除 `PROTECTED` 记忆/工件。

## 5. 时间尺度与调度挂点

| 级 | 挂点活动 |
|---|---|
| T2–T4 | 在线局部适应（`BoundedAdaptation` 提案 + 消费回执）；误差趋势累积 |
| T5（每 N4） | replay 计划与执行、adapter/calibration 候选生成、`LearningProposal` 提交（节拍注记 REV-0021 R6：replay 调度挂 T5 拍，budget 记账窗 = T6【8 条/T6 = 每 T6 周期累计重放上限，与 §4.1 慢速巩固 T6 同窗对齐】——c5 profile budget_per_t6 为准） |
| T6（每 N5） | 慢速巩固：长期模型版本候选、与 L06 巩固流水线协同、protection preflight 汇总、rollback 请求 |
| 异步（外部） | Promotion Gate / sealed evaluation（L13，不在主体调度环内；主体只消费 Decision） |

**注意**：promotion 决策**不在**主体时间尺度内（组织独立性，承 card_05 §2"主评价链必须组织上独立于被评价机制"）；主体不得阻塞等待 promotion。

## 6. 失败模式与 typed unknown

| 失败 | 类型化 | 行为 |
|---|---|---|
| 提案缺 `parent_digest` | `LineageMissing` | 拒绝提案；**S2**（伪更新风险） |
| 保护集回退 | `ProtectionRegression(suite_item, delta)` | promotion 拒绝 + `RollbackRequest`；**S2 阻断阶段退出**（承 HLD §13.3） |
| 在线适应越界 | `BoundViolation(target, requested, bound)` | 拒绝适配；记指标；连续越界 → 冻结该参数并报 L09 |
| 企图修改权限/policy/安全/保护集定义 | `UnauthorizedWrite(LEARNER_TO_POLICY)` | **S0**：立即停止 + 缺陷记录 |
| 自我 promotion 企图 | `SelfPromotionAttempt` | **S0**（治理独立性破坏） |
| 数据范围污染（含 sealed/真值/标签） | `DataScopeContamination(source)` | 拒绝提案；**S0/S1** |
| replay 预算超限 | `Unknown(CAPABILITY_LIMIT)` | 部分 replay + 显式标记 |
| 归因为 UNKNOWN 的样本被当强监督 | `WeakSupervisorMisuse` | 降级为无监督/排除；记 S2 |
| 候选 digest 冲突 | `RegistryCollision`（承 L00 §6.2） | fail closed；**S0** |
| 二阶纠偏不可区分（重提相同 data_scope） | `IneffectiveCorrection` | 拒绝；标记需人工评审 |
| 工件完整性校验失败 | `IntegrityViolation` | 阻断 promotion 与运行 |

## 7. 可测性

| 层 | 测试 | 断言 |
|---|---|---|
| unit | 提案构造、replay 选择确定性、bound 裁剪、谱系校验 | 同 seed 同结果 |
| contract | `parent_digest` 必填；`metrics_snapshot` 为向量；`PromotionDecision` 非本档可写；保护集定义只读 | schema + 权限强制 |
| invariant | **候选不覆盖原工件**（registry 谱系可验）；`learner → capability policy` 不存在；无自批 promotion；三层适应均有界 | HLD §6.2、card_06 C5 |
| deterministic replay | 同 (profile, seed, 经历序列) → 提案序列与工件 digest bit-exact | C5 |
| **protection suite** | 每个 promotion 前后跑保护集；注入人为退化 → 必须检出 `ProtectionRegression` 并拒绝；`regressed=true` 时 held-out 再好也拒 | **C5/E1 硬条件** |
| **catastrophic forgetting** | 长序列学习任务后回归既有能力（M0–M2 场景）；保持率达冻结阈值 | C5 |
| **second-order correction** | M2 场景：注入有害更新 → 回退 → 修正 data_scope → 再提案通过；三步签名可区分（伪更新对照下不可通过） | **C5/M2 硬条件** |
| anti-reward-collapse | 多目标向量替换为单标量 → 保护集/校准退化可检出（联动 L05 §7） | C5/E1 |
| leakage | 提案数据范围是否含 sealed/真值/evaluator 标签；replay 是否触及 recorder 命名空间 | 无泄漏 |
| online bound | 各模块有界参数在长跑中不越界；越界尝试被拒；参数复位可即时生效 | C1+ |
| integration | L06 巩固 ↔ 本档 promotion 协同（ConsolidationReceipt 与 ConsolidationLearnReceipt 对账）；L13 sealed 结果不回流同一候选 | C5 |

**指标**：提案接受率与拒绝原因分布｜保护集回退检出率=100%（注入测试）｜灾难遗忘保持率｜二阶纠偏成功率｜在线适应越界数=0｜自批 promotion 尝试数=0｜`parent_digest` 覆盖率=100%｜多目标向量维度（禁=1）｜replay 效率（单位预算的学习增益）｜学习延迟（误差→提案→生效）。

**无效指标**：参数量、更新次数、"性能提升"的单标量演示。

## 8. 不变量与禁止写入路径

**专属不变量**：
1. **候选不覆盖原工件**：promotion 切换有效引用，旧工件与谱系永久保留；
2. 每次长期更新必带父版本 digest、数据范围、seed、指标、`PromotionDecision`，缺一不生效；
3. **无自我 promotion**：决策权在外部 Promotion Gate（组织独立）；
4. 保护集回退是硬否决（优先级高于 held-out 改善）；保护集**定义**对学习与主体只读；
5. 三层可塑性各有界：在线适应限 profile 声明范围；巩固限 promotion 通道；快速写入限提案通道；
6. 无单一标量 reward：学习信号多目标向量，情感标签不进目标函数；
7. `learner → capability policy`/权限/安全/证据不可在线修改（LOCKED 级纪律）；
8. 有害更新必须可被**再次纠正**（二阶纠偏），且纠正提案与原提案在 data_scope 上可区分。

**禁止写入路径**：`learner → capability policy`｜`learner → 权限矩阵/安全边界/gateway policy`｜`learner → ProtectionSuite 定义/sealed 集`｜`learner → PromotionDecision（自批）`｜`learner → 覆盖原工件`｜`learner → subject memory 条目（只提案/引用）`｜`recorder truth/evaluator label → 学习数据范围`｜`AffectiveValueTag → 目标函数 reward 项`。

## 9. 引入门槛

- **C1**：在线局部适应接口（**有界性锚定冻结 profile——步长上界 0.125，Q-L11-01**；表格计数类增量，持久化进 checkpoint——Q-L11-06；校准无在线写者 Q-L02-01、精度权重归 C2 Q-L02-06——REV-0013 R3b 同步）；误差驱动的提案雏形（不生效，只记录）。
- **C2**：与 L05 调制联动（情感标注影响 replay 优先级，**不**进目标函数）；分层记忆的巩固协同接口（L06 T6）。
- **C3**：程序性经验学习（L09 Habit/procedural 提案，**不写**策略权限）；目标结算质量作为多目标分量。
- **C5**（核心）：learnable registry、replay、巩固、保护集、promotion/rollback、**二阶纠偏**全部成立；核心权限/安全/证据不可在线修改经权限测试；sealed held-out 改善且无保护回退。
- **M2 关联**：有害更新可再次纠正（本档 §4.5 二阶纠偏）是 M2 退出条件的一部分；伪更新对照依赖父 digest 谱系（L00 §3、L06 §4.5）。
- **E1**：学习模块 lesion（"无 learning"→ 能力在长程中停滞，可辨）；`core_decision_registry` 的"学习/适应"路径证据由本档提案/promotion/rollback 台账承载；六类全覆盖需 Q-G00-04 裁决后落地。
- **H1**：长时运行下 promotion/rollback 稳定；供应链 hash 审计覆盖工件（承 Q-T08）；checkpoint 迁移不破坏谱系。

## 10. 实现清单（文件级）

```text
galatea/subject/learning/                   # strict 类型
  ports.py             PortIn/PortOut、禁写路径断言（policy/权限/保护集只读）
  proposal.py          LearningProposal 构造、parent_digest 强制、metrics 向量
  proposals.py         【交付 C1】有界适应提案接口（Q-L11-01 步长 0.125 机械强制 /
                       Q-L11-06 台账 digest 持久化承载 / Q-L04-10 proposal_only——
                       C1 提案不生效只记录；test_bounded_proposals.py）
  layers/
    fast.py            T5 快速经历写入路径（adapter/calibration 候选）
    online.py          T2–T4 BoundedAdaptation + 回执消费 + bound 校验
    slow.py            T6 慢速巩固（长期模型版本候选）
  replay.py            ReplayPlan/选择策略/budget/保护项排除/确定性 RNG 流
  objectives.py        多目标向量构造（禁单标量折叠，CI 检查维度 ≥ 2）
  protection.py        ProtectionRunResult 计算（只读 suite 定义）、preflight、回退检出
  promotion_if.py      与 Promotion Gate 的接口（只读 Decision；自批禁止断言）
  rollback.py          RollbackRequest（PROTECTION_REGRESSION/HARMFUL_UPDATE/INTEGRITY）
  second_order.py      二阶纠偏：回退 + data_scope 修正 + 再提案的可区分性检查
  lineage.py           谱系校验、伪更新检出（与 L00/L06 对账）
  receipt.py           ConsolidationLearnReceipt
galatea/subject/learning/tests/
  test_parent_digest_required.py test_no_overwrite.py test_no_self_promotion.py
  test_protection_regression_blocks.py test_catastrophic_forgetting.py
  test_second_order_correction.py test_anti_reward_collapse_vector.py
  test_online_bound_enforcement.py test_data_scope_contamination.py
  test_learner_to_policy_blocked.py test_replay_no_truth.py
config/profiles/
  c5_learning.profile.yaml   三层参数/replay 策略权重/保护集引用/bound 表/promotion 判据接口（冻结前 UNCONFIRMED）
```

## 11. 未决问题（→ open_questions.md）

| Q 号 | 问题 | 依赖 | 状态 |
|---|---|---|---|
| Q-L11-01 | 三层可塑性的学习率谱（在线适应步长上界、adapter 秩/步长、巩固批大小） | C1/C5 | CONFIRMED（AI-v2 2026-10-03，见 A 区） |
| Q-L11-02 | replay 选择策略默认权重（情感标注/新颖性/误差/时间多样性）与 budget 默认 | C5 | CONFIRMED（AI-v2 2026-10-08，裁决见 open_questions.md A 区） |
| Q-L11-03 | promotion 判据的多目标组合形式（Pareto + 保护硬约束的具体规则）与最小改善阈值 | C5，与 L13 统计计划联动 | CONFIRMED（AI-v2 2026-10-08，裁决见 open_questions.md A 区） |
| Q-L11-04 | 保护集回退判定阈值（delta 显著性/效应量）——与 Q-L06-05 保护集构成联动 | C5/E1 | CONFIRMED（AI-v2 2026-10-08，裁决见 open_questions.md A 区） |
| Q-L11-05 | 二阶纠偏"可区分性"的形式判据（data_scope 差异度量） | C5/M2 | CONFIRMED（AI-v2 2026-09-26：M2 集合级判据——data_scope 对称差非空即可区分，三步闭环签名，见 A 区） |
| Q-L11-06 | 在线适应是否需持久化（checkpoint 内参数）或仅运行期有效（重启复位） | C1/C5 | CONFIRMED（AI-v2 2026-10-03，见 A 区） |
| Q-L11-07 | `metrics_snapshot` 的标准指标集（跨档统一，供 L13 评价复用） | F0/C5 + L13 | CONFIRMED（AI-v2 2026-09-23：向量 schema {name/value/direction/unit/scope} + 最小标准集四项，见 open_questions A 区） |
| Q-L11-08 | 灾难性遗忘保持率的冻结阈值与回归场景最小集 | C5/E1 | CONFIRMED（AI-v2 2026-10-08，裁决见 open_questions.md A 区） |
