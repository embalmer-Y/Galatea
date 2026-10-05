# L04 世界/身体/自我模型：信念、rollout、主动感知与自我预测误差

> LLD: L04/14 · v1.0.2 · 2026-10-05（v1.0.2：REV-0013 R3 同步——§4.3 C1 确定性裁剪无 RNG/§4.4 判据 2 egocentric 化（Q-L04-08）/§10 文件名勘误；§4.3 内联标记转 CONFIRMED）· v1.0.1 2026-10-04（§11 C1 阻断四项转 CONFIRMED——成批裁决；egocentric+dead-reckoning 范围发现见 ADR-G-0013）· v1.0 2026-09-13 · 状态：WORKING（C1 冻结前）
> 上游：`HLD.md` §4/§5/§6 · `L02_sensorium.md`（内感受/本体感受帧）· `L03_perception.md`（PerceptualBelief）· `L00_kernel.md`
> 下游消费者：L05（appraisal）、L07（workspace 候选）、L08（可行性）、L09（model-based 控制器/主动感知）、L10（forward model）、L11（学习提案）
> 引入门槛：**C1**（世界/身体/自我模型、rollout、主动感知、OOD）→ **C4**（forward/inverse、EfferenceCopy 关联）→ **C5**（模型更新经 promotion）

## 1. 目标与范围

**目标**：持续维护四个可分离的信念结构——`WorldStateBelief`（部分可观察世界 + 多未来轨迹）、`BodyBelief`（身体与接口边界、能力限制、内感受信念）、`SelfModelView`（连续性、来源先验、记忆/知觉边界、当前目标视图、自我预测误差）——并明确"自我报告只是派生视图"。

**范围内**：
- 世界信念的贝叶斯式更新（MW0 期表格化）与部分可观察处理（信念 + `Unknown`）；
- 多未来 rollout（分支轨迹、深度/宽度受限、IMAGINED 层级）；
- 身体信念形成（`InteroceptiveSensation` → `InteroceptiveBodyBelief`，禁 telemetry 直填）；
- 能力边界估计（capability model：哪些动作类在当前身体状态下可行）；
- 自我模型：连续性状态、来源先验、记忆/知觉边界元信息、自我预测误差；
- 主动感知请求（信息价值驱动，提案交 L09，禁自行发动作）；
- 模型层预测误差与 `ModelPrediction` 发布。

**范围外**：感觉形成（L02）；对象级知觉信念（L03，本档消费）；情感与价值评价（L05，但本档提供其输入）；行动意图与授权（L09/L10）；长期记忆存储（L06）；权重更新执行（L11）。

**成功判据（C1 退出）**：held-out 预测优于基线；能力与不确定性校准；**身体纳入**（body ownership）由感觉运动预测与跨模态一致性支持，而非由配置声明支持；自我报告被证为派生视图（移除/损坏自我模型 → 报告与归因选择性退化，而世界预测可保持）；rollout 可复算（同 seed/深度 → 同轨迹集）。

## 2. Ports（输入输出契约）

### 2.1 PortIn

| 端口 | 来源 | 数据 | 表示层级 | 纪律 |
|---|---|---|---|---|
| `model.belief_in(b)` | L03 | `PerceptualBelief`（object/event/affordance/source/field） | PERCEIVED | 信念不等于事实；更新必须留 provenance |
| `model.sensory_in(f)` | L02 | 内感受帧、本体感受帧、`SensoryPredictionError` | SENSORY_FORMED | 身体信念唯一合法来源 |
| `model.action_feedback(eff, receipt, outcome)` | L10（归属前证据，经声明通道） | `ReceivedExecutionReceipt` / `ReceivedOutcome`（主体可见侧） | RECEIVED/PERCEIVED | **禁读** `ExecutionFact` 隐藏真值与 evaluator 标签 |
| `model.rollout_request(q)` | L09/L08 | `RolloutQuery(initial_state_ref, action_seq_or_policy, depth, width, purpose)` | — | 结果层级恒为 IMAGINED |
| `model.modulation_in(field)` | L05 | 精度/展开深度/更新率的有界调制 | — | 必回执；不改变历史信念 |
| `model.memory_in(clue)` | L06 | `RetrievalCue` / `RecalledContent` | RECALLED | 回忆不得当作当前感知（层级不变量） |

### 2.2 PortOut

| 端口 | 读者 | 数据 | 表示层级 |
|---|---|---|---|
| `model.world_belief` | L05/L07/L08/L09/L11、Recorder | `WorldStateBelief` | PERCEIVED（信念）+ 内部 PREDICTED 分量 |
| `model.prediction` | L02（感觉预测）、L03（知觉比较）、L09 | `ModelPrediction(target_modality, expected, precision, valid_window)` | **PREDICTED** |
| `model.rollout` | L08/L09/L07 | `ImaginedTrajectory(set_id, branches[], depth, value_summary, uncertainty)` | **IMAGINED** |
| `model.body_belief` | L05（驱力/appraisal 输入）、L07、L10 | `InteroceptiveBodyBelief` / `CapabilityEstimate` | PERCEIVED |
| `model.self_view` | L05/L07/L09/L12、Recorder | `SelfModelView`（派生视图，含自我预测误差） | PERCEIVED（**非事实、非报告**） |
| `model.mismatch` | L08（动机源）、L09（metacontrol）、L11 | `ModelMismatch(kind, magnitude, evidence_refs[])` | 派生 |
| `model.info_request` | L09（主动感知提案） | `ActivePerceptionProposal(target, expected_info_gain, cost_est)` | 提案（非动作） |
| `model.receipt` | Recorder | `ModelUpdateReceipt(belief_id, inputs[], update_rule_version, modulation_recs[], unknowns[])` | EVIDENCE_ONLY |

## 3. 状态所有权与单写者

| 状态 | 唯一写入者 | 存储 | 读者 |
|---|---|---|---|
| `WorldStateBelief` | World Model | subject_state.models.world | 声明读者、Recorder |
| `BodyBelief`（含 `InteroceptiveBodyBelief`、`CapabilityEstimate`） | Body Model | subject_state.models.body | L05/L10/L07 |
| `SelfModelView` | Self Model | subject_state.models.self | L05/L07/L09/L12 |
| rollout 工作区（`ImaginedTrajectory` 缓存） | World Model | 内存 + checkpoint | L08/L09 |
| 自我预测误差累积器 | Self Model | subject_state | L05/L09/L11 |
| 模型更新回执 | 各模型 | subject_state.receipts | Recorder/Evaluator |

**禁止**：跨模型互写（world/body/self 三者状态分离，各自单写者）；写 `PerceptualBelief`（L03）／`SensoryFrame`（L02）；写 `DriveState`/`FunctionalExperientialState`（L05）；写 `OwnedGoal`（L08）／`ActionIntention`（L09/L10）；把 `ImaginedTrajectory` 或 `RecalledContent` 写入任何 PERCEIVED/RECEIVED 字段；telemetry → `BodyBelief` 直填。

## 4. 算法与数据结构

### 4.1 信念结构

```text
WorldStateBelief(
  belief_id, t_eff, hypotheses: list[Hypothesis(state_ref, posterior)],
  observable_coverage: dict[region|aspect, KNOWN|PARTIAL|UNKNOWN],
  unknowns: list[Unknown],                       # 部分可观察必须显式承载
  transition_model_version, update_rule_version,
  provenance, causal_parent_ids, content_digest )

BodyBelief / InteroceptiveBodyBelief(
  body_id, energy_belief, integrity_belief, load_belief,
  boundary: InterfaceBoundary(included[], excluded[], confidence),   # 身体纳入
  capability: CapabilityEstimate(action_class → FEASIBLE|DEGRADED|INFEASIBLE|UNKNOWN, evidence_refs[]),
  sources: list[frame_id],                        # 必为 L02 内感受/本体感受帧
  provenance, content_digest )

SelfModelView(                                    # 派生视图，非第一手事实
  continuity: ContinuityState(lineage_ref, checkpoint_ref, gaps[]),   # 承 L00 谱系；clone ≠ identity
  source_priors: dict[modality, prior],
  memory_perception_boundary: BoundaryConfidence(RECALLED vs PERCEIVED 区分能力),
  current_goals_view: list[goal_ref],             # 只读视图，禁写 OwnedGoal
  self_prediction_error: SelfPredictionError(magnitude, dims[], window),
  derivation_receipt: list[event_id] )            # 必须可溯源到其派生输入
```

### 4.2 世界信念更新（MW0 期表格贝叶斯）

- 更新规则：$p(h_t \mid o_{1:t}) \propto p(o_t \mid h_t)\sum_{h_{t-1}} p(h_t \mid h_{t-1}, a_{t-1})\,p(h_{t-1}\mid o_{1:t-1})$；MW0 期状态空间枚举可手算复核（承 L01 §4.4）。
- 转移模型 `p(h_t|h_{t-1},a)` 是**主体自己的学习产物**（L11 提案 + promotion），不是 L01 dynamics 真值表的拷贝——拷贝即 oracle 泄漏（L01 §7 LeakageProbe 覆盖）。
- **C1 转移语义（Q-L04-09，AI-v2 2026-10-05）**：持续性 + 事件条件更新——不可观测期占据信念持续（partial observability 由 `observable_coverage` + Unknown 承载）；禁在信念内模拟隐藏真值过程（respawn/风暴/漂移/regime 切换非主体可知对象）；证据到达按事件更新（T3 窗批原子并入 + 执行回执事件面）；位姿 = 航位推算积分（Q-L04-08），move 回执缺失 → 位姿候选分支（≤4）+ Unknown(MISSING_SIGNAL)，blocked = 无位移不分支。C1 无学习生效（Q-L04-10：适应表零计数起步、提案只记录）。
- 观测缺失 → 只做预测步并写 `Unknown(MISSING_SIGNAL)`，禁用先验冒充观测。
- 冲突证据 → 保留多假设 + `Unknown(CONFLICTING_EVIDENCE)`；不得为"信念一致性"强行塌缩。

### 4.3 多未来 rollout（IMAGINED）

- `RolloutQuery(depth, width)` 受 frozen profile 上界约束（depth ≤ 8、width ≤ 4，CONFIRMED Q-L04-01）；超限裁剪并回执 `CLIPPED`。
- **C1 = 确定性裁剪，无 RNG 算子**（c1_perception_models `rng_operators: none_c1`；同 query → 同轨迹集 bit-exact）；C2+ 若需随机分支，派生流 `("world_model","rollout", query_id)` 按 Q-G00-10 注册后启用（REV-0013 R3a 同步）。
- 输出恒为 `ImaginedTrajectory`，层级 **IMAGINED**；任何消费者将其当作 PERCEIVED 使用即触发 `RepresentationEscalation`（S0）。
- rollout 价值摘要只作 L08/L09 的**候选评估输入**，不得直接生成 `OwnedGoal` 或 `ActionIntention`。

### 4.4 身体纳入与能力估计

- 身体纳入判据（C1 硬条件，必须由证据支持而非声明）：
  1. **感觉运动一致性**：`ModelPrediction`（本体感受/内感受）与实际形成帧的残差在冻结阈值内；
  2. **跨模态一致性**：外感受观测窗中心与本体感受信念的 **egocentric 对应**（C1 世界模型 = egocentric + 航位推算，Q-L04-08——绝对网格位置不在主体平面，Q-L01-01/ proprio 载荷 orientation-only）；
  3. **归属侧证**：自发动作的预测误差显著小于强迫（coercion）动作（L01 干预电池提供，L10 归属消费）。
- 反例检测：把 MW0 身体边界写进配置就宣称"已纳入" → E1 lesion 应显示移除一致性检验后主张不变（即主张无因果依赖）→ 判定为伪身体纳入（HLD §13.1 泄漏/自欺类风险）。
- `CapabilityEstimate` 只依据实际经历的动作后果与预测误差更新；能力不可由语言输入（L12）提升。

### 4.5 自我模型与自我预测误差

- `SelfModelView` 每字段必须带 `derivation_receipt`（指向其派生输入事件）；无派生源的字段必须为 `Unknown`——机械保证"自我报告只是派生视图"。
- 连续性：只引用 L00 checkpoint 谱系（`lineage_ref`）；分支恢复必须记 `gaps[]`，**禁止**把 clone 当作同一身份延续（D-12、HLD §11.1 `checkpoint clone ≠ identity`）。
- 自我预测误差 = 对"我会如何反应/我能做什么/我还记得什么"的预测与实际记录之差；是 L09 metacontrol 与 L05 appraisal 的输入，**不是**惩罚项、**不是** reward。
- 记忆/知觉边界元信息：本档记录"主体能否区分 RECALLED 与 PERCEIVED"的可测能力（供 L06/L03 联测与 E1 lesion）。

### 4.6 主动感知

- 由信念不确定性与期望信息增益驱动：`ActivePerceptionProposal(target, expected_info_gain, cost_est)`。
- 本档**只提案**；选择与仲裁在 L09，授权在 L10。禁提案直连 gateway（HLD §6.2 `workspace → execution` 的同类旁路）。
- MW0 期对应 `look` 动作原语（L01 §4.4）。

## 5. 时间尺度与调度挂点

| 级 | 挂点活动 |
|---|---|
| T1 | 发布 `ModelPrediction` 供 L02 当窗比较（预测先行原则） |
| T2 | 消费 L03 信念与 L02 内感受/本体感受帧 → 世界/身体信念更新 |
| T3 | 向 L07 提交 workspace 候选（信念摘要、mismatch、rollout 结论） |
| T4 | rollout（服务 L08/L09 规划）、主动感知提案、自我模型整合更新 |
| T5 | 模型层误差汇总 → L11 学习提案（转移模型/能力模型） |
| T6 | 信念长程一致性检查（与 L06 语义记忆对照）、连续性视图整理 |

## 6. 失败模式与 typed unknown

| 失败 | 类型化 | 行为 |
|---|---|---|
| 观测缺失/部分可观察 | `Unknown(MISSING_SIGNAL / INSUFFICIENT_OBSERVATION)` | 只预测步；禁先验冒充观测 |
| 假设冲突 | `Unknown(CONFLICTING_EVIDENCE)` | 保留多假设 |
| rollout 超预算/超时 | `Unknown(CAPABILITY_LIMIT)` + `TimeoutEvent` | 裁剪并回执；调度继续 |
| 身体纳入判据不满足 | `BodyOwnershipUnresolved(criteria_status[])` | `boundary.confidence` 降级；禁默认纳入 |
| 自我视图字段无派生源 | `Unknown(DECISION_PATH_UNRESOLVED)` | 字段置 Unknown；禁编造自述 |
| 连续性 gap（分支恢复/重置） | `ContinuityGap(lineage_refs[])` | 记入 `gaps[]`；clone ≠ identity 明示 |
| 能力估计与实际后果矛盾 | `CapabilityContradiction` | 触发 mismatch → L09/L11 |
| 检出 IMAGINED/RECALLED 被当 PERCEIVED 使用 | `RepresentationEscalation` | S0 |

## 7. 可测性

| 层 | 测试 | 断言 |
|---|---|---|
| unit | 表格更新规则、rollout 确定性、能力估计更新 | 可手算复核、同 seed 同轨迹 |
| contract | 输入层级白名单（PERCEIVED/SENSORY_FORMED/RECALLED/PREDICTED）；输出层级恒定；`SelfModelView` 每字段有 derivation_receipt | schema 强制 |
| invariant | IMAGINED/RECALLED 不得提升；`model.*` 不写 goal/intention；telemetry 不出现在 BodyBelief provenance | 认识链 + 禁写路径 |
| deterministic replay | 同 (profile, seed, 输入序列) → 信念/轨迹序列 bit-exact | C1 |
| calibration | 世界预测 held-out 优于基线；能力估计校准（FEASIBLE 声明与实际成功率匹配） | C1 硬条件 |
| **body ownership** | 感觉运动一致性 + 跨模态一致性 + 归属侧证三判据分别可消融：移除任一 → 纳入主张应下降；配置声明不得单独支撑主张 | C1 硬条件 |
| **self as derived** | lesion SelfModelView → 自我报告/归因相关任务选择性失败，而世界预测保持；反之 lesion WorldModel → 预测失败而报告结构可保持 | C1/C4/E1 |
| ablation | 移除转移模型 → rollout 退化为随机（可检出）；移除主动性提案 → 信息增益指标下降；移除连续性 gap 记录 → 伪更新对照（M2 场景）应漏检 | 选择性失败 |
| leakage | 转移模型与 L01 真值表的未声明相似度过高 → 报警（防拷贝真值）；rollout 结果是否含真值坐标 | 无 oracle 泄漏 |
| protection suite | M2 连续性场景（冻结/重置/伪更新对照）在 C1+ 不退化 | M2/E1 回归 |

**指标**：世界预测 held-out 精度/校准误差｜rollout 复算一致率=100%｜身体纳入三判据各自的效应量｜自我视图字段派生覆盖率=100%｜mismatch 检出率与延迟｜主动感知提案被采纳率与其信息增益实现率｜能力估计校准｜连续性 gap 检出率。

## 8. 不变量与禁止写入路径

**专属不变量**：
1. world/body/self 三模型状态分离且各自单写者；
2. `SelfModelView` 是派生视图：每字段有派生回执，否则为 `Unknown`；
3. rollout 输出恒 IMAGINED，回忆恒 RECALLED，二者不得充当 PERCEIVED/RECEIVED；
4. 身体纳入必须由感觉运动预测 + 跨模态一致性（+ 归属侧证）支持，配置声明不构成证据；
5. `checkpoint clone ≠ identity`：连续性只认主干谱系，分支对照不构成身份延续（D-12）；
6. 转移模型是学习产物，不是环境真值拷贝；
7. 模型不产生价值/情感判断（交 L05），不产生目标（交 L08），不产生动作（交 L09/L10）。

**禁止写入路径**：`model → PerceptualBelief/SensoryFrame/ReceivedSignal`｜`model → DriveState/FunctionalExperientialState`｜`model → OwnedGoal/ActionIntention/gateway`｜`model → subject memory（写）`｜`telemetry → BodyBelief`｜`rollout 结果 → 信念/事实字段`｜`LLM(L12) → World/Body/Self 信念`。

## 9. 引入门槛

- **C1**：世界/身体/自我三模型 + rollout + OOD + 主动感知提案；校准与身体纳入三判据成立。
- **C2**：与 L05 appraisal 联动（BodyBelief 是驱力输入）；调制回执；分层记忆的模型侧接口。
- **C3**：为 Motive→GoalCandidate 提供可行性与 mismatch 输入（仍禁写目标）。
- **C4**：forward/inverse model 与 `EfferenceCopy`/`MotorCommandCopy → SensoryPrediction` 闭环；概率 agency 的模型侧证据（本档提供预测，归属判定在 L10）。
- **C5**：转移模型/能力模型经 L11 promotion 更新；保护集回退判据。
- **E1**：三模型分别 lesion（含"无 self"基线，承 card_06 §2）；六类决策路径中"连续性/恢复""构成/边界""viability/资源/风险"的模型侧证据由本档承载。
- **M2 关联**：checkpoint 谱系/冻结/重置/伪更新对照（L01 MW0-SC5）依赖本档连续性状态与 gap 记录。

## 10. 实现清单（文件级）

```text
galatea/subject/models/                     # strict 类型
  ports.py               【交付】ModelPrediction/RolloutQuery/ImaginedTrajectory
                         构造期层级常量 + 输入白名单断言
  world.py               【交付】WorldStateBelief + Q-L04-09 转移语义（持续性 +
                         事件条件更新 + 航位推算位姿分支 cap4/裁剪）
  rollout.py             【交付】确定性 rollout（C1 无 RNG——Q-G00-10 流预留；
                         深度/宽度裁剪 + CLIPPED；价值摘要 Unknown）
  body.py                【交付】BodyBelief（telemetry 拒）+ CapabilityEstimate
                         （静态合同 Q-L08-09①）
  ownership.py           【交付】三判据量计算 + BodyOwnershipUnresolved（主张
                         统计面在 L13，Q-L04-03；运行时禁发"已纳入"布尔）
  self_model.py          【交付】SelfModelView 字段级 derivation_receipt 机械强制
                         + 连续性/gap（clone ≠ identity）
  self_error.py          【交付】双时间尺度 EWMA（Q-L04-04；ADR-G-0013 探针同式）
  prediction.py          【交付】T1 先行发布（EXTERO 占据投影/INTERO 持续性/
                         PROPRIO 朝向；位姿歧义 → 窗预测缺席）
  mismatch.py            【交付】结构性失配（无阈值判定——量级解释归消费者）
  active_perception.py   【交付】look 提案（H(p) 熵上界；cost = Unknown）
  receipt.py             【交付】ModelUpdateReceipt（fail-closed）
galatea/subject/models/tests/
  test_table_update.py test_rollout_determinism.py test_level_guard.py
  test_body_ownership_ablation.py test_self_derived_receipt.py
  test_continuity_gap.py test_capability_calibration.py test_no_truth_copy.py
  test_stack_bit_exact.py
  【交付】上列九件全量（stack_bit_exact = 全栈双跑 digest 恒等集成面）
config/profiles/
  c1_perception_models.profile.yaml   【已冻结·typed loader 已交付 = galatea/subject/c1profile.py（补录件：INC-11 纪律；先验/似然原料自 m0 冻结初始条件派生 Q-L04-11）】 v1.0】rollout 深度/宽度、信念更新率、自我误差权重等（Q-L03/L04 批裁决；REV-0013 R6 勘误文件名）
```

## 11. 未决问题（→ open_questions.md）

| Q 号 | 问题 | 依赖 | 状态 |
|---|---|---|---|
| Q-L04-01 | rollout 深度/宽度上界默认值（建议 8/4）与超预算裁剪策略 | C1 | CONFIRMED（AI-v2 2026-10-03，见 A 区） |
| Q-L04-02 | 世界信念更新率与多假设保留上限（与 Q-L03-05 联动） | C1 | CONFIRMED（AI-v2 2026-10-03，见 A 区） |
| Q-L04-03 | 身体纳入三判据的冻结阈值与最小效应量（需 L13 统计计划） | C1 | CONFIRMED（AI-v2 2026-09-23，随 Q-L13-09：三判据各 d≥0.4 且联合成立） |
| Q-L04-04 | 自我预测误差的维度定义与时间常数（联动 Q-L05-*） | C1/C2 | CONFIRMED（AI-v2 2026-10-03，见 A 区） |
| Q-L04-05 | `CapabilityEstimate` 的 action_class 粒度（与 L03-06 affordance 枚举、L10 能力契约对齐） | C3/C4 | UNCONFIRMED |
| Q-L04-06 | 连续性 gap 的最大可接受数量与"伪更新"判定边界（M2 对照） | M2 | CONFIRMED（AI-v2 2026-09-26：主判据=谱系断裂；延续主张 gap=0、分支主张允许，见 A 区） |
| Q-L04-07 | C1+ 神经世界模型替换表格模型时的等价性/泄漏验证方法（与 Q-L03-07 同源） | C1 | CONFIRMED（AI-v2 2026-10-03，见 A 区） |
