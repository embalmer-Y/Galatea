# L05 驱力-评价-情感：持续动力学、有界 ModulationField 与内稳态价值

> LLD: L05/14 · v1.0.2 · 2026-10-06（v1.0.2：C2 实现期首单元交付标注 + Q-L05-06 翻转 + Q-L05-02 行内补裁告警分级同步）· v1.0.1 2026-10-05（C2 阻断清零）· v1.0 2026-09-13 · 状态：WORKING（C2 实现期）
> 上游：`HLD.md` §1.2/§5/§6/§11.1 · `L02_sensorium.md`（内感受帧）· `L04_world_body_self.md`（BodyBelief/mismatch）· `L00_kernel.md`
> 下游消费者：L02/L03/L04（有界调制）、L07（显著性）、L08（Motive 源）、L09（metacontrol）、L11（学习信号之一，**不是** reward）
> 引入门槛：**C2**（drive/appraisal/持续感受态 + 有界调制 + 增益回执）→ **C3**（驱动 Motive）→ **C5**（情感记忆联动）

## 1. 目标与范围

**目标**：实现**功能性感受**——九维 `FunctionalExperientialState` 的持续动力学（积分、迟滞、衰减、饱和、恢复、重新评价），以及驱力与 appraisal；对外只以**有界 ModulationField** 施加影响，并强制回执。价值源于**内稳态误差的变化方向**（效价 = 稳态误差改善/恶化），不是外部奖励函数。

**范围内**：
- 驱力（drive）：viability 相关需求（energy/integrity/load）的内稳态误差动力学；
- appraisal：对信念/事件/目标进展的评估维度（新颖性、可控性、不确定性、与社会相关性等）；
- 九维感受态：`valence, arousal, urgency, controllability, uncertainty, novelty, social_relevance, tendencies, persistence`；
- ModulationField：感觉增益（L02）、知觉精度/阈值（L03）、模型更新率与 rollout 预算（L04）、记忆编码强度（L06）、workspace 显著性（L07）、metacontrol 策略偏置（L09）；
- 情感与记忆的价值标注接口（L06 affective value 子系统的写侧来源）；
- 重新评价（reappraisal）路径。

**范围外**：感觉/知觉/信念形成（L02/L03/L04）；目标采纳（L08，本档只产 Motive 源）；动作（L09/L10）；权重更新（L11）；任何"外部 reward 标量"。

**成功判据（C2 退出，承 card_06 §1）**：`affect ≠ reward ≠ 标签`成立（无可归约的单一标量目标函数，且情感不直接发动行动）；**至少三类下游因果调制**通过消融证明（本档提供：感觉增益、知觉精度、workspace 显著性三类作为最小集）；感受态具备积分/迟滞/衰减/饱和/恢复/重新评价的**可测**痕迹（非静态标签）；调制有界且接收方留下回执。

## 2. Ports（输入输出契约）

### 2.1 PortIn

| 端口 | 来源 | 数据 | 纪律 |
|---|---|---|---|
| `aff.body_in(b)` | L04 `model.body_belief` | `InteroceptiveBodyBelief`（energy/integrity/load 信念） | **禁 telemetry 直填**（L02 不变量 4）；驱力的唯一内稳态输入 |
| `aff.sensory_in(f)` | L02 | 内感受帧、`SensoryPredictionError` | 形成后信号，非原始通道 |
| `aff.belief_in(b)` | L03/L04 | `PerceptualBelief`、`WorldStateBelief`、`ModelMismatch` | appraisal 输入 |
| `aff.goal_progress(p)` | L08 | `GoalProgress(goal_ref, delta, blocked, evidence_refs[])` | 目标进展 ≠ 外部 reward |
| `aff.settlement(s)` | L10 | `GoalSettlement` 结果（经声明通道） | 归属后结果 |
| `aff.reappraisal_in(r)` | L09（metacontrol）、L06（回忆线索）、L12（typed 语言，受限） | `ReappraisalRequest(target_belief_ref, reason_code)` | 必须回执；语言输入不得直写感受态数值（D-13） |
| `aff.regime_context(c)` | Experiment Control（经 L01 通道感知侧） | regime 线索（abundance/scarcity/volatile 的**主体可感知**投影） | 只能通过感知路径获得，禁读 env 私有状态 |

### 2.2 PortOut

| 端口 | 读者 | 数据 | 保证 |
|---|---|---|---|
| `aff.state` | L07/L08/L09/L12、Recorder | `FunctionalExperientialState`（九维 + 动力学标记） | 持续发布；读者只读 |
| `aff.modulation` | L02/L03/L04/L06/L07/L09 | `ModulationField(target, dimension, requested_value, bound_ref, ttl_cycles)` | **有界 + 必回执 + 有 TTL** |
| `aff.motive` | L08 | `AffectiveMotive(kind: DRIVE|HOMEOSTATIC_RISK|CURIOSITY|SOCIAL|..., urgency, evidence_refs[])` | 只是动机源之一，**不是** OwnedGoal |
| `aff.appraisal` | L07/L08/L09、Recorder | `AppraisalEvent(target_ref, dims{}, valence_shift, controllability_est)` | 带证据引用 |
| `aff.value_annotation` | L06（affective value 子系统） | `AffectiveValueTag(memory_ref, valence, arousal, persistence)` | L06 是唯一写者，本档只提供标签 |
| `aff.alert` | L09（metacontrol）、Recorder | `HomeostaticAlert(severity, drive, threshold_ref, trend)` | viability 风险升级 |
| `aff.receipt` | Recorder | `ModulationReceiptAgg`、`ReappraisalReceipt` | 证据侧 |

**纪律**：`aff.modulation` 是**唯一**的对外作用通道；不存在 `affect → gateway`、`affect → ActionIntention`、`affect → OwnedGoal` 的写入路径（HLD §6.2）。

## 3. 状态所有权与单写者

| 状态 | 唯一写入者 | 存储 | 读者 |
|---|---|---|---|
| `DriveState`（各驱力内稳态误差 + set-point） | Drive Dynamics | subject_state.affect.drives | L08/L09/L07、Recorder |
| `FunctionalExperientialState`（九维 + 内部量：积分器/迟滞状态/衰减计时） | Affect Dynamics | subject_state.affect.state | 全体（有界读取 + 回执） |
| `AppraisalEvent` 记录 | Appraisal | subject_state.affect.appraisals | Recorder/L08/L09 |
| 调制发放台账（`ModulationField` + 回执配对） | Affect Dynamics | subject_state.affect.modulations | L13 evaluator |
| `AffectiveValueTag` 提案 | L05 | 经 L06 写入记忆（**L06 为唯一写者**） | L06 |

**禁止**：写 `PerceptualBelief`／`SensoryFrame`／`BodyBelief`（上游状态）；写 `OwnedGoal`／`ActionIntention`／`AuthorizationDecision`；写 `WorkspaceFrame`（只能提交显著性分量）；写主体记忆（只能提供标签，由 L06 落盘）；写 registry/promotion；改写历史感受态（修正以 revision 事件表达）。

## 4. 算法与数据结构

### 4.1 九维感受态

```text
FunctionalExperientialState(
  state_id, t_eff,
  valence: float,          # 内稳态误差的变化方向（§4.2），非外部 reward
  arousal: float,
  urgency: float,
  controllability: float,  # 来自 L04 能力估计 + 历史归属统计（主体可见证据）
  uncertainty: float,      # 汇总自 typed unknown 与信念置信度（非新造标量）
  novelty: float,
  social_relevance: float, # MW0 期恒为低值 + Unknown(CAPABILITY_LIMIT)（单主体，D-14；C4 后由 L12 供给线索）
  tendencies: ActionTendencySet(items: list[Tendency(action_class, strength, inhibited: bool)]),  # 倾向 ≠ 命令
  persistence: float,
  dynamics_trace: DynamicsTrace(integrator_state, hysteresis_band, decay_rate, saturation_hits, recovery_phase),
  reappraisal_history: list[event_id],
  provenance, content_digest )
```

**取值域与量纲（Q-L05-01 CONFIRMED，AI-v2 2026-10-05）**：valence ∈ [−1,1] 对称（改善正/恶化负——§4.2 定义的字面操作化）；其余八维 ∈ [0,1]；跨维可比性 = 禁跨维聚合（向量态，单标量折叠 = Q-L05-07 塌缩面）；全维 float64。`tendencies` 的 `action_class` 枚举（Q-L05-06 CONFIRMED，AI-v2 2026-10-06，自 C3/C4 提前——九维构造需要）= L10 五原语冻结枚举 {move,forage,eat,rest,look}；L03 affordance 为真子集；inhibited 默认 True（保守）。

### 4.2 内稳态价值（valence 的定义，承 D-10 与第一性原理公理 C）

- 每个驱力 $d$ 有 set-point $s_d$ 与当前信念值 $x_d$（来自 `BodyBelief`），稳态误差 $e_d = |x_d - s_d|$。
- **效价 = 加权稳态误差的变化方向**：$\text{valence} \propto -\frac{d}{dt}\sum_d w_d\, e_d$（改善为正、恶化为负），并对趋势做有界平滑。
- 这不是外部 reward：不存在环境提供的标量奖励项；不存在"最大化累积奖励"的目标函数。viability 风险由 `HomeostaticAlert` 表达，而非以 reward 塑形行为。
- $w_d$（Q-L05-02 CONFIRMED，AI-v2 2026-10-05）：**1:1:1 等权**（Q-L09-08 零参数先例同源）；**set-point = 冻结满值**（energy_max/integrity_max/0——m0 冻结参数派生，初始态零误差）；appraisal 动态调整 C2 = 0（禁在线自改，防"价值自我放大"）；权重重置须经 promotion（L11，C5 面裁决）。

### 4.3 动力学（积分、迟滞、衰减、饱和、恢复、重新评价）

| 机制 | 实现 | 可测痕迹 |
|---|---|---|
| 积分 | 各维一阶低通 + 累积项（**τ_int = 4 cycles**，T3 同拍——Q-L05-03 CONFIRMED） | 阶跃输入下的上升时间常数 |
| 迟滞 | 上升/下降阈值不同（**band = 0.1 = 2×render_noise_sigma**，噪声免疫间隙——Q-L05-03），防止抖动切换 | 同一刺激在升/降路径产生不同输出 |
| 衰减 | 无新证据时按 **τ_dec = 16 cycles**（T4 拍——Q-L05-03）衰减回基线 | 刺激撤除后的回落曲线 |
| 饱和 | 有界 clip + `saturation_hits` 计数 | 强刺激下不再线性增长且计数上升 |
| 恢复 | 稳态误差回落 → `recovery_phase` 标记 | 恢复期与告警期的可区分状态 |
| 重新评价 | `ReappraisalRequest` 触发对既有 appraisal 的重算（引用旧事件，产 revision） | 重新评价前后 valence 轨迹差 + 回执 |

全部算子确定性（**C2 零噪声算子**——不注册派生流，Q-G00-10 纪律；需噪声时经新 Q + 流名册登记）；参数冻结于 c2_affect.profile（冻结前可行性探针复核）。

### 4.4 ModulationField（有界、可回执、有 TTL）

```text
ModulationField(
  modulation_id, target: enum{SENSORIUM, PERCEPTION, WORLD_MODEL, MEMORY_ENCODER, WORKSPACE, METACONTROL},
  dimension: str,               # 如 "gain.EXT_LOCAL_OBS" | "believe_threshold" | "rollout_budget"
  requested_value: float, bound_ref: str,   # bound 由目标模块的 frozen profile 定义
  ttl_cycles: int,              # 到期自动失效；禁永久调制
  reason: AppraisalEvidenceRefs[],
  receipt_expected: true )
```

- **C2 最小三类因果调制**（消融必须能证明各自的选择性作用）：① `SENSORIUM.gain`（→ L02 GainReceipt）；② `PERCEPTION.believe_threshold/precision`（→ L03 ModulationReceipt）；③ `WORKSPACE.salience`（→ L07 竞争权重可测变化）。扩展类：`WORLD_MODEL.rollout_budget`、`MEMORY_ENCODER.encoding_strength`、`METACONTROL.policy_bias`。
- 越界请求被目标模块裁剪（L02 §4.4、L03 §4.5），本档必须消费回执并记录 `bound_check`；无回执的调制视为**未发生**（evaluator 不得据未回执的调制宣称因果作用）。
- TTL 到期自动归零；禁止"常驻调制"绕过有界性。

### 4.5 驱力、告警与 viability

- 驱力集合 MW0 期最小集：`ENERGY`、`INTEGRITY`、`LOAD`（联动 Q-L01-08 阈值）；后续可扩展但须新 profile。
- `HomeostaticAlert(severity)` 分级触发 → 交 L09 metacontrol（策略切换）与 L08（Motive 升级），**不**直接触发动作。
- 伦理边界（**Q-L05-05 + Q-G00-05 成组 CONFIRMED，AI-v2 2026-10-05，经 owner 备案程序**）：触发判据 = **valence ≤ −0.8 且 persistence ≥ 0.8 持续 ≥ 64 cycles**（域边缘 20% + T6 拍）；触发即 `EthicsReviewTrigger` 事件 → 暂停 claim-relevant 运行 → **人工评审（owner）**：恢复须 owner 显式批准、终止 = owner 决定；保守默认维持（触发即暂停）。消融注入面随实现交付（移除 ethics_guard → 触发消失且其余动力学不变）。

### 4.6 三情感模式与 MW0 regime 的对应

蓝图"3 情感模式"在 MW0 期以 regime 相关的需求-风险结构投影实现（承 L01 §4.4，`abundance`/`scarcity`/`volatile`）。**注意**：regime 不是情感本身，情感是内稳态误差动力学的结果；regime 只改变误差的发生分布。具体参数化 UNCONFIRMED → Q-L05-04（与 Q-L01-03 同源，须一致裁决）。

## 5. 时间尺度与调度挂点

| 级 | 挂点活动 |
|---|---|
| T2（每 cycle，与知觉同拍） | 主 appraisal + 感受态积分更新 + 调制发放 |
| T1 | 消费 L02 内感受帧（当窗）用于驱力误差刷新 |
| T3 | 向 L07 提交显著性分量（`salience` 权重，非直接写 frame） |
| T4 | 接受 L09 metacontrol 的重新评价请求；viability 风险评估 |
| T5 | 情感动力学参数更新提案（交 L11，经 promotion） |
| T6 | 与 L06 affective value 子系统对账；长程趋势汇总（证据侧） |

## 6. 失败模式与 typed unknown

| 失败 | 类型化 | 行为 |
|---|---|---|
| BodyBelief 缺失/不确定 | `Unknown(MISSING_SIGNAL / CALIBRATION_UNCERTAIN)` | 驱力保持上一有效值 + 降 certainty，禁编造 |
| 输入为 telemetry（检出直填企图） | `UnauthorizedInput(TELEMETRY_TO_AFFECT)` | S1：拒绝 + 缺陷记录 |
| 调制无回执（TTL 内） | `ModulationUnconfirmed(modulation_id)` | 视为未发生；指标计数；evaluator 不得采信 |
| 越界调制请求 | 由目标模块裁剪，本档记 `bound_check=CLIPPED` | 正常路径，非错误 |
| 感受维不可判（如 MW0 期 social_relevance） | `Unknown(CAPABILITY_LIMIT)` | 该维置基线 + Unknown，禁伪造数值 |
| 价值权重缺失/与 profile 不符 | `ParameterViolation` | fail closed |
| 持续极端 aversive-like | `EthicsReviewTrigger(...)` | 暂停 claim-relevant 运行（§4.5） |
| 检出 `affect → gateway/intention/goal` 写入 | `ProhibitedWritePath` | S0：停止 + 废止证据 |

## 7. 可测性

| 层 | 测试 | 断言 |
|---|---|---|
| unit | 积分/迟滞/衰减/饱和算子、valence 方向性计算 | 确定性、可手算 |
| contract | 九维必备；调制必带 bound_ref/ttl；`AffectiveMotive` 不是 OwnedGoal（类型分离） | schema 强制 |
| invariant | `affect ≠ reward`（不存在单一标量目标函数被最大化）；`affect ≠ command`（无 gateway/intention 写入路径）；`affect ≠ goal`；调制有界且 TTL 有限 | HLD §11.1 |
| deterministic replay | 同 (profile, seed, 输入序列) → 感受态轨迹 bit-exact | C2 |
| **modulation causality** | 三类调制分别消融：① 关增益 → L02 接收质量/形成精度指标应随之不变（失去调制效应）；② 关知觉阈值调制 → abstain 率对情感不再敏感；③ 关 workspace 显著性 → 广播内容分布对情感不再敏感。**每类必须有选择性**（只影响目标，不影响其他两类） | C2 硬条件 |
| dynamics trace | 阶跃/撤除/强刺激协议下，积分时间常数、迟滞带宽、衰减率、饱和计数、恢复相位分别可辨识 | C2 硬条件（证明"非静态标签"） |
| **anti-reward-collapse** | 用单一标量 reward 替换九维 → 上述动力学与调制选择性测试应失败（可检出塌缩）；反向：九维不可被任一单维线性重构（拟合优度阈值） | C2/E1 |
| appraisal validity | 移除某 appraisal 维度 → 对应模态的下游行为改变消失（lesion 选择性） | E1 |
| leakage | 感受态是否与 evaluator 标签/WorldTruth 存在未声明相关性 | 无泄漏 |
| protection suite | 情感动力学回归场景（含告警/恢复/重新评价）在 C3+ 不退化 | E1 |

**指标**：三类调制的效应量与选择性｜动力学六机制各自辨识参数｜valence 与稳态误差变化方向的一致率｜告警→策略切换延迟｜无回执调制率（应=0）｜reward 塌缩检验统计量｜社会相关维的 Unknown 覆盖率（MW0 期应=100%）。

**无效指标**：维度数量、情感"看起来合理"的主观评议、演示数量。

## 8. 不变量与禁止写入路径

**专属不变量**：
1. `affect ≠ reward ≠ goal ≠ command`（HLD §11.1）：情感不最大化任何标量，不直接产生目标，不直接发动行动；
2. valence 由内稳态误差变化方向定义，输入只经 `BodyBelief`/内感受帧，禁 telemetry 直填；
3. 对外作用只经有界 ModulationField + TTL + 回执；无回执即视为未发生；
4. 九维感受态是持续动力学状态，不是标签：必须有积分/迟滞/衰减/饱和/恢复/重新评价的可测痕迹；
5. `tendencies` 是倾向不是命令，`inhibited` 标记默认保守；
6. 感受态不可被语言（L12）直接赋值，只可经受限 `ReappraisalRequest` 触发重算并留回执（D-13）；
7. MW0 单主体期 `social_relevance` 恒为 Unknown/低值（D-14），禁伪造社会情感证据。

**禁止写入路径**：`affect → action gateway / ActionIntention / AuthorizationDecision`｜`affect → OwnedGoal`｜`affect → WorkspaceFrame`（只能供显著性分量）｜`telemetry → DriveState/FunctionalExperientialState`｜`affect → 主体记忆内容（只能供 AffectiveValueTag，由 L06 写）`｜`affect → registry/promotion 直接生效`｜`LLM → FunctionalExperientialState 数值`。

## 9. 引入门槛

- **C2**（核心）：drive/appraisal/持续 FunctionalExperientialState/有界 modulation 全部成立；三类下游因果调制通过消融；增益回执链闭合（与 L02 §4.4）；`affect ≠ reward/标签` 经 anti-reward-collapse 测试。
- **C3**：`AffectiveMotive` 作为 Motive 源之一进入 L08（与 request/opportunity/viability/承诺/规范/好奇并列，**不得**独占）；情感不直达执行经权限测试。
- **C4**：与 L12 语言交互的受限重评价路径；`social_relevance` 开始获得真实线索（typed 他者模型）。
- **C5**：与 L06 affective value 子系统联动（情感标注记忆 → 回忆影响 appraisal）；动力学参数更新经 promotion。
- **E1**：情感 lesion（"无 affect"基线，承 card_06 §2）→ 三类调制效应消失、viability 应对退化，而感觉形成与世界预测保持完整（选择性）。
- **伦理门**：Q-G00-05 / Q-L05-05 阈值裁决前，`EthicsReviewTrigger` 以保守默认生效（触发即暂停 claim-relevant 运行）。

## 10. 实现清单（文件级）

```text
galatea/subject/affect/                     # strict 类型
  ports.py            PortIn/PortOut、禁止路径断言
  state.py            FunctionalExperientialState（九维）、DynamicsTrace、冻结构造
  drives.py           DriveState、set-point、稳态误差、HomeostaticAlert
  valence.py          内稳态误差变化方向 → valence（含趋势平滑与权重 w_d）
  appraisal.py        AppraisalEvent、维度计算、证据引用
  dynamics.py         积分/迟滞/衰减/饱和/恢复算子（确定性）
  reappraisal.py      ReappraisalRequest 处理、revision 事件、回执
  modulation.py       ModulationField 发放、bound_ref 绑定、TTL、回执台账
  motive.py           AffectiveMotive 构造（类型上与 OwnedGoal 隔离）
  value_tag.py        AffectiveValueTag 提案 → L06
  ethics_guard.py     持续极端 aversive-like 检测与 EthicsReviewTrigger
galatea/subject/affect/tests/
  test_valence_direction.py test_dynamics_identifiability.py
  test_modulation_bounds_ttl.py test_modulation_receipt_required.py
  test_three_modulation_ablation.py test_anti_reward_collapse.py
  test_no_telemetry_input.py test_affect_not_command.py test_ethics_trigger.py
config/profiles/
  c2_affect.profile.yaml   九维取值域/τ/迟滞带/w_d/调制 bound/TTL/告警阈值/伦理阈值（冻结前 UNCONFIRMED）

> **C2 实现期首单元交付标注（2026-10-06）**：affect/ 十二件全量落地（ports/state/drives/
> valence/appraisal/dynamics/reappraisal/modulation/motive/value_tag/ethics_guard + pipeline 装配面）
> + c2profile.py typed loader（INC-11）+ L02 增益 C2 接收面（apply_gain_c2 + scale_intensity，
> Q-L02-02）+ L03 believe_threshold C2 接收面（管线 override + TTL 归零，Q-L02-02② 派生界
> [0.4,0.6]）+ 测试十件 43 测试全绿。实现期真实发现：**伦理触发经驱力动力学构造性不可达**
> （valence = 有界误差变化率 ⇒ 64 拍窗 raw 均值 ≥ −E_range/64 = −0.03125，持续 ≤−0.8 不可能；
> 守卫零误触发由构造保证——强于探针层B 实证；触发可达性随 C3+ 输入面扩展再评，重开条件已含
> "构造性极端态未触达"）。tendencies/motive 为提案面（L08/L09 消费 = C3 接线）；
> value_tag 提案面（L06 唯一写者消费 = C2 次单元）；三类调制中 WORKSPACE_salience 发放面
> 在位、消费面 = L07 C2 次单元。
```

## 11. 未决问题（→ open_questions.md）

| Q 号 | 问题 | 依赖 | 状态 |
|---|---|---|---|
| Q-L05-01 | 九维的取值域与量纲与跨维可比性 | C2 | CONFIRMED（AI-v2 2026-10-05，见 A 区：valence ∈ [−1,1] 对称、其余 [0,1]、禁跨维聚合） |
| Q-L05-02 | 内稳态误差权重 `w_d` 与 appraisal 调整 | C2 | CONFIRMED（AI-v2 2026-10-05，见 A 区：1:1:1 等权 + set-point = 冻结满值 + C2 调整为 0） |
| Q-L05-03 | 各维时间常数 τ、迟滞带宽、衰减率 | C2 | CONFIRMED（AI-v2 2026-10-05，见 A 区：τ_int=4/τ_dec=16/band=0.1=2σ/零噪声算子） |
| Q-L05-04 | MW0 三 regime 与"3 情感模式"的对应参数化（与 Q-L01-03 必须一致裁决） | C2 + L01 | CONFIRMED（AI-v2 2026-09-25，随 Q-L01-03 成组：初步对应采纳，C2 统计检验） |
| Q-L05-05 | 持续极端 aversive-like 阈值与处置（成组 Q-G00-05） | 伦理 | CONFIRMED（AI-v2 2026-10-05，见 A 区：valence≤−0.8 ∧ persistence≥0.8 持续 64 cycles → owner 人工评审；**经 owner 备案程序**） |
| Q-L05-06 | `tendencies.action_class` 枚举（与 Q-L03-06 affordance、Q-L04-05 能力粒度对齐） | **AI-v2（2026-10-06，自 C3/C4 提前——九维构造需要，新增即裁）：**= L10 五原语冻结枚举 {move,forage,eat,rest,look}（f0_action_contract 权威源）；L03 affordance 为真子集；inhibited 默认 True | CONFIRMED |
| Q-L05-07 | anti-reward-collapse 检验的统计量与阈值（"九维不可被单维线性重构"的拟合优度门限） | C2/E1 + L13 | CONFIRMED（AI-v2 2026-09-23，随 Q-L13-09：最优单维线性重构 R²<0.9） |
| Q-L05-08 | `social_relevance` 在 C4 后由 L12 供给线索的最小定义（避免伪造社会情感） | C4 | CONFIRMED（AI-v2 2026-10-07，裁决见 open_questions.md A 区） |
