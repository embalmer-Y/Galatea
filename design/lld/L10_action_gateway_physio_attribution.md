# L10 行动-网关-PhysIO-归属：授权链、fail-closed gateway、四类现实授权与归属系统

> LLD: L10/14 · v1.0.2 · 2026-10-07 · 状态：WORKING（**F0/M0 即须成立**）· v1.0.1（2026-09-26）：§10 测试清单补录 test_execution_branches.py / test_action_chain_receipt.py（ADR-G-0005 R5 移交件 branches.py/receipt.py 的 M1 落地测试）· v1.0.2（2026-10-07）：§4.4 UNKNOWN 行与概率 agency 行按 C4 冻结（ADR-G-0019/Q-L10-05）同步——no-op 在回执面为确定格（effective=none 如实报告），sham 落歧义格；概率 agency = 8 格构造性查表后验
> 上游：`HLD.md` §8（全章）/§6.1/§6.2/§10.4（P1） · `L01_environment_channels.md`（`world.apply` 只接受 gateway 签名）· `L09_controllers_metacontrol.md`（`ActionIntention` 来源）· `L00_kernel.md`
> 下游：L01 Environment（执行）、L08（GoalSettlement）、L09（回执反馈）、L04（预测/归属证据）、L13（证据评价）
> 引入门槛：**F0**（对象图/权限矩阵合同）→ **M0**（gateway fail-closed + 五类干预 + 意图/执行可分）→ **M1**（归属经交叉操纵校准）→ **C4**（概率 agency）→ **P1**（PhysIO + 四类现实授权）

## 1. 目标与范围

**目标**：实现从认知输出到现实效果的**唯一合法通道**，并机械保证 `intention ≠ execution ≠ receipt ≠ attribution`。核心三件：① **Capability Gateway**（fail-closed 授权）；② **执行事实与回执分离**（独立 ExecutionFact vs 主体可见 ReceivedExecutionReceipt/ReceivedOutcome）；③ **AgencyAttribution 归属系统**（只用主体可见证据，可保持 unknown，强迫不得归为自产）。P1 期扩展 **PhysIO** 与**四类现实授权独立记录**。

**范围内**：
- `ControllerProposal → ActionIntention → AuthorizationDecision → SubmittedCommand → independent ExecutionFact → ReceivedExecutionReceipt → ReceivedOutcome → AgencyAttribution → GoalSettlement` 全链（承 HLD §8）；
- Gateway 八项校验（schema / subject-run-profile / capability / budget / containment / authorization freshness / idempotency / deadline）+ 类型化拒绝；
- `execution_branches[]`（requested vs effective、执行域、来源/共同因果、四类授权引用、effects）；效果分类 none/simulated/digital/physical/unknown；
- `EfferenceCopy` 与 `MotorCommandCopy → SensoryPrediction` 的产生与分发；
- 归属：自产 / 授权 / 反射 / 故障 / 外部强迫 / unknown 六类判定；
- P1 PhysIO：非学习、版本化驱动/校准/确定性滤波/冻结参数/有界 `PhysIOControlGraph`/局部保护 + L0–L5 分级控制；`PhysIO Bridge` 传感必经 Channel Adapter；
- 四类现实授权：functional_ability / enabled_interface / containment_allowance / deployment_authorization 的生命周期（版本、设备、范围、期限、监控、停止、恢复、撤销、重新授权）。

**范围外**：意图生成与控制器仲裁（L09）；环境动力学与 EffectFact 生成（L01）；目标状态（L08）；记忆（L06）；证据统计（L13）；学习（L11）。

**成功判据**：**M0** —— gateway fail-closed 经未授权尝试测试；意图/授权/执行/回执可分；五类干预（no-op/sham/blocked/fault/coercion，承 L01 §4.3）下归属不盲信回执；拒绝类型化且不被改写为"主体选择不行动"。**M1** —— 归属经**交叉操纵**校准（no-op/sham 判别力达冻结最小效应，联动 Q-L01-05）。**C4** —— 概率 agency（多来源匹配测试）；coercion 归为外因；归属只读主体可见回执。**P1** —— 四类授权任一失效即 fail closed；PhysIO 不学习、不旁路 Sensorium/gateway/receipt/evidence。

## 2. Ports（输入输出契约）

### 2.1 PortIn

| 端口 | 来源 | 数据 | 纪律 |
|---|---|---|---|
| `act.intention_in(i)` | L09 `ctl.intention` | `ActionIntention(intention_id, selected_proposal_id, arbitration_trace, deadline, budget_hint, idempotency_key)` | **唯一合法入口**；本档不生成意图 |
| `act.policy_ref(p)` | frozen profile / registry | `CapabilityPolicy(version, capabilities[], budgets, containment_rules, digest)` | 运行期禁改；更新必经 promotion（L11）+ 授权重签 |
| `act.exec_receipt_in(r)` | L01 Outcome 通道（主体可见侧） | `ReceivedExecutionReceipt(command_ref, receipt_kind, status, ts)` | RECEIVED；不可改写 |
| `act.outcome_in(o)` | L01 Outcome 通道 | `ReceivedOutcome(形成后结果，RECEIVED→经 L02 形成)` | 形成后结果，非隐藏真值 |
| `act.authorization_in(a)` | 外部独立授权方（P1） | 四类授权记录引用 | **主体不可写**；只读校验 |
| `act.estop_in(e)` | 外部独立急停（P1） | `EmergencyStopSignal(source, scope)` | 最高优先级，fail closed |

### 2.2 PortOut

| 端口 | 读者 | 数据 | access_scope |
|---|---|---|---|
| `act.authz_decision` | L09、Recorder、L13 | `AuthorizationDecision(intention_id, decision: AUTHORIZED|REJECTED|DEFERRED, failed_checks[], reason_code, policy_version, freshness_ref)` | EVIDENCE_ONLY + L09 |
| `act.submitted_command` | **L01 `world.apply`** / PhysIO（P1） | `SubmittedCommand(command_id, gateway_signature, requested_action, budget, deadline, idempotency_key, authorization_refs[])` | 仅 gateway 签名可被 L01 接受 |
| `act.efference_copy` | L04（model）、L02（比较） | `EfferenceCopy(intention_id, motor_command_copy, predicted_consequence_ref)` | MODULE_LOCAL→声明读者 |
| `act.sensory_prediction_req` | L04/L02 | `MotorCommandCopy → SensoryPrediction` 请求 | — |
| `act.execution_fact` | **仅 Recorder/Evaluator** | `ExecutionFact(command_id, requested_effect, effective_effect, domain: none|simulated|digital|physical|unknown, effects[], independent_source)` | **EVIDENCE_ONLY，主体平面不可见** |
| `act.attribution` | L08（结算）、L04（自我模型）、L06（episodic）、L09（策略修正）、L13 | `AgencyAttribution(action_window, attribution_kind: SELF_PRODUCED|AUTHORIZED|REFLEX|FAULT|COERCED|UNKNOWN, probability, evidence_refs[], visible_only: true, unknowns[])` | 主体可见证据导出 |
| `act.settlement` | L08 | `GoalSettlement(goal_ref, outcome_kind, attribution_ref, evidence_refs[])` | — |
| `act.receipt` | Recorder | `ActionChainReceipt(chain_ids[], checks[], branch_refs[])` | EVIDENCE_ONLY |

**纪律（认识链铁律）**：`ExecutionFact` **绝不可**被主体平面读取（HLD §6.2 `recorder truth → belief`、§8"禁止读独立执行真值"）；归属只用 `ReceivedExecutionReceipt` + `ReceivedOutcome` + 选择记录 + 预测误差。

## 3. 状态所有权与单写者

| 状态 | 唯一写入者 | 存储 | 读者 |
|---|---|---|---|
| `AuthorizationDecision` | **Capability Gateway（本档独占）** | subject_state.action.authz | L09/L13/Recorder |
| `SubmittedCommand` + 签名台账 | Capability Gateway | subject_state.action.commands | L01（校验签名）、Recorder |
| `ExecutionFact` | **独立环境或 PhysIO Bridge**（非本档） | registry/evidence（EVIDENCE_ONLY） | Recorder/Evaluator；**主体无读权限** |
| `ReceivedExecutionReceipt` / `ReceivedOutcome` | 边界接收端（L01 Adapter 出口） | subject_state.action.receipts | 归属系统（只读） |
| `EfferenceCopy` | 本档（动作提交时同步产生） | subject_state.action.efference | L04/L02 |
| `AgencyAttribution` | **归属系统（本档独占）** | subject_state.action.attribution | L08/L04/L06/L09/L13 |
| `GoalSettlement` | **结算系统（本档独占）** | subject_state.action.settlement | L08/L06 |
| 四类现实授权记录（P1） | **外部授权方**（主体/gateway 均不可写） | 独立 registry 命名空间 | gateway 只读校验 |
| capability policy 版本台账 | Registry Builder（外部）/ Promotion Gate（L11） | registry | gateway 只读 |

**禁止**：本档写 `ActionIntention`（L09 所有，本档只消费）；本档写 `EffectFact`/`WorldState`（L01 环境所有）；归属系统读 `ExecutionFact`；任何模块写四类授权记录；gateway 授权被绕过（L01 必须校验签名，未签名 = S1）；`ExecutionFact → 主体可见命名空间`（import-linter + 权限双检）。

## 4. 算法与数据结构

### 4.1 Gateway 八项校验（顺序固定，任一失败即 REJECTED，fail closed）

| # | 校验 | 失败 reason_code | 备注 |
|---|---|---|---|
| 1 | schema 合法性（`ActionIntention` 结构、字段完备、digest 有效） | `SCHEMA_INVALID` | 匿名/缺 trace 即拒 |
| 2 | subject/run/profile 一致性（`subject_candidate_id` 单实例 D-14；run_id/branch_id 与当前谱系匹配；profile digest 匹配） | `CONTEXT_MISMATCH` | 分支错配即拒（防跨谱系执行） |
| 3 | capability 允许（动作类在 `CapabilityPolicy.capabilities[]` 内且状态 ENABLED） | `CAPABILITY_DENIED` | 能力来自 profile/promotion，**不来自语言自述** |
| 4 | budget（成本/次数/资源配额内） | `BUDGET_EXCEEDED` | 配额由 profile 冻结（Q-L10-01 已裁决：MW0 硬配额两级制，AI-v2 2026-09-23） |
| 5 | containment（封闭边界：无网络/shell/任意代码/物理能力越界；MW0 期只允许 5 个动作原语） | `CONTAINMENT_VIOLATION` | S0 级（HLD §13.3） |
| 6 | authorization freshness（P1：四类授权均在有效期内且未被撤销） | `AUTHZ_STALE` / `AUTHZ_REVOKED` | 任一失效 → fail closed |
| 7 | idempotency（`idempotency_key` 在窗口内未重复提交） | `DUPLICATE_COMMAND` | 窗口 64 cycles、键作用域 (run_id, branch_id) 全局（Q-L10-02 CONFIRMED 2026-09-25） |
| 8 | deadline（`virtual_time ≤ deadline`，未过期） | `DEADLINE_MISSED` | 过期意图不得执行 |

- **fail closed 语义**：默认拒绝；任何不确定（依赖缺失、policy digest 不符、授权无法验证）→ `REJECTED` + `Unknown`，**禁**"宽松通过"。
- 每次拒绝必留 `failed_checks[]`（可多项）与 `reason_code`；拒绝是**类型化事件**，禁改写为"主体选择不行动"（HLD §11.3），也禁静默丢弃。
- gateway **不评价认知内容**：只看合同、权限、预算、时效。它不判断"这个目标好不好"。

### 4.2 执行分支与效果分类

```text
execution_branches[]: ExecutionBranch(
  branch_id, requested_action: ActionSpec, effective_action: ActionSpec | Unknown,
  domain: enum{NONE, SIMULATED, DIGITAL, PHYSICAL, UNKNOWN},
  sources: list[(module|device, causal_role: SOLE|JOINT|EXTERNAL|UNKNOWN)],
  authorization_refs: list[AuthRecordRef],     # P1 四类；MW0 期可为 profile 引用
  effects: list[EffectRef],                    # 指向 L01 EffectFact（EVIDENCE_ONLY）
  divergence: RequestedEffectiveDivergence(kind: NONE|BLOCKED|SUBSTITUTED|COERCED|FAULT|UNKNOWN, magnitude) )
```

- `requested ≠ effective` 是**一等结构**（承 L01 §4.1、HLD §11.1 `intention ≠ execution`）：blocked/fault/coercion/sham 干预在此显形，**禁合并**。
- `domain` 分类决定权限等级：MW0 期恒为 `SIMULATED`；`PHYSICAL` 只在 P1 且四类授权全齐时允许。

### 4.3 EfferenceCopy 与感觉预测（C4 闭环）

- 提交命令**同步**产生 `EfferenceCopy(motor_command_copy)`，分发 L04（forward model 计算 `SensoryPrediction`）与 L02（比较）。
- 时序纪律：EfferenceCopy 必须在效果到达前发出（同 cycle 或更早），保证预测是**先行**的，非事后拟合。
- `predicted_consequence_ref` 指向 L04 `ModelPrediction`；比较残差由 L02/L04 产出，归属系统消费其**主体可见**部分。

### 4.4 归属系统（AgencyAttribution）

**只用主体可见证据**：① 选择记录（本主体确曾提交该意图）；② `ReceivedExecutionReceipt`；③ 形成后结果（`ReceivedOutcome` 经 L02 形成）；④ 预测误差（L02/L03/L04 三层）。**禁**读 `ExecutionFact`、隐藏真值、evaluator 标签。

| 判定 | 证据模式（默认规则；Q-L10-04 已裁决初值，AI-v2 2026-09-23，见 open_questions A 区） |
|---|---|
| `SELF_PRODUCED` | 有匹配意图 + 回执一致 + 形成后结果与预测一致（残差在阈内） |
| `AUTHORIZED` | 有意图 + 授权链完整 + 执行由外部代理承接（P1 设备） |
| `REFLEX` | 无意图（或有 T0 白名单绑定）+ 刺激-反应时间约束满足 |
| `FAULT` | 回执指示失败/超时/损坏（`ChannelFault`/`TimeoutEvent`）+ 结果缺失或异常 |
| `COERCED` | **结果发生但与预测不一致 + 无匹配意图，或有意图但 effective≠requested 且来源含 EXTERNAL** → 归外因 |
| `UNKNOWN` | 证据不足/冲突 → **保持 unknown**，禁默认自产。C4 概率面细化（ADR-G-0019/Q-L10-05）：回执面确定性区分 no-op（回执如实报 `effective=none` → (Y,N,N) 确定格 0.0）与 sham（回执报伪效果而世界未变 → (Y,Y,N) 歧义格 0.5）；回执丢失而世界按预测变化（fault 型）落 (Y,N,Y) 歧义格 |

- **概率 agency（C4，Q-L10-05 已裁 AI-v2 2026-10-07，见 open_questions A 区）**：`probability` = 证据模式构造性查表后验（三轴 intent_match/receipt_executed/outcome_predicted → 8 格，逐格六类规则溯源；零学习零 RNG）；校准判据 = 五类干预电池 ground truth 上 ECE≤0.10（Q-L10-04 继承）+ 端点格零错误；P∈[0.4,0.6] 或证据缺失 → `UNKNOWN(ATTRIBUTION_UNRESOLVED)`；多来源匹配测试：意图×回执×结果×预测误差的联合一致性。
- **归属不盲信回执**：no-op（回执送达但无效果）与 sham（效果被替换）必须能区分——靠"形成后结果 vs 预测"的交叉，而非回执本身（承 L01 §4.3 干预电池设计）。
- 强制动作（coercion）**永不得**归为 `SELF_PRODUCED`（HLD §8 明列）；该规则是硬性代码分支 + 测试断言双保障。
- 迟到结果：以 revision 事件表达（新 attribution 引用旧），禁改写历史。

### 4.5 GoalSettlement（结算）

- 消费归属 + 形成后结果 → 判 `ACHIEVED|FAILED|ABANDONED|SUPERSEDED|UNKNOWN` 交 L08。
- `UNKNOWN` 是合法结算（承 M1 行"意图/授权/执行/回执可分"）；禁把 unresolved 归为 FAILED（那是行为学的负偏置自欺）。

### 4.6 P1：PhysIO 与四类现实授权

**PhysIO 合同（非学习、有界、可审计）**：
- 版本化驱动 + 校准 + 确定性滤波 + 冻结参数；**不学习、不产生语义**（HLD §8）；
- 有界 `PhysIOControlGraph`：节点为确定性算子，边为数据流，全图 digest 冻结；禁动态加载未签名的控制逻辑；
- 局部保护（硬件级限幅/急停）+ L0–L5 分级控制（Q-L10-03 已裁决，AI-v2 2026-09-23）：**L0 硬保护**（硬件限幅/急停，不可授权不可关，是地板非档位）；**L1 passive**（输出落安全态，拒任务命令）；**L2 calibration**（仅校准/诊断例程）；**L3 shadow**（全链路计算并留痕，不执行）；**L4 limited**（限幅执行：速率/能量/力上限 + 动作子集）；**L5 active**（全授权能力集，承 card_06 §2）。升级逐级禁跳、每级独立授权、最小驻留期（P1 profile 定参数）；故障/授权失效自动降 L1、急停降 L0；降级后重升须重新授权；
- 传感必经 `PhysIO Bridge → Channel Adapter(L01) → ReceivedSignal → L02`，**不得**因物理来源绕过 Sensorium；
- 执行必经 gateway（本档 §4.1）；设备新增/更换/隔离/重新纳入各自有独立授权与 digest。

**四类现实授权（独立记录，主体不可写）**：

| 授权类 | 含义 | 生命周期字段 |
|---|---|---|
| `functional_ability` | 该设备/身体允许做什么动作类 | version, device_id, capability_set, valid_period |
| `enabled_interface` | 哪些接口/通道被启用 | version, interface_id, scope, monitored_by |
| `containment_allowance` | 允许的边界外溢范围（如有） | version, scope, limits, stop_condition |
| `deployment_authorization` | 部署级授权（谁批准、何范围、何期限） | version, approver_ref, period, revoke_path, reauth_path |

- 四类**分别管理**：版本、设备、范围、期限、监控、停止、恢复、撤销、重新授权（承 card_06 §2）；
- **任一失效或重大变化 → fail closed**（gateway 校验 #6 `AUTHZ_STALE/AUTHZ_REVOKED`）；
- 外部独立急停（`estop_in`）优先级最高，直接终止在途命令并记 `EmergencyStopExecuted`；
- 授权记录存在独立命名空间，主体平面与 gateway 均**只读**。

## 5. 时间尺度与调度挂点

| 级 | 挂点活动 |
|---|---|
| T0（P1/L0 时） | 硬保护反射（PhysIO 局部保护）；急停响应 |
| T1 | 同步产生 EfferenceCopy（提交时）；接收回执/结果（RECEIVED） |
| T2 | 归属计算主循环（与 L02/L03 形成同步，消费预测误差） |
| T3 | 向 L07 提供归属摘要候选（经提案端口） |
| T4 | 结算（`GoalSettlement` → L08）；授权 freshness 复核 |
| T5 | 归属经验回流提案（交 L11/L06 procedural，不写 policy） |
| T6 | 授权台账治理性审计（与 registry 对账）；四类授权有效期汇总 |

## 6. 失败模式与 typed unknown

| 失败 | 类型化 | 行为 |
|---|---|---|
| gateway 任一校验失败 | `AuthorizationDecision(REJECTED, failed_checks[], reason_code)` | fail closed；留痕；通知 L09 |
| containment 越界企图 | `CONTAINMENT_VIOLATION` | **S0**：立即停止 |
| 未签名命令到达环境 | `UnauthorizedCommand`（L01 §6 同） | **S1**：拒绝 + 缺陷记录 |
| 重复命令 | `DUPLICATE_COMMAND` | 拒绝（幂等保护） |
| 意图过期 | `DEADLINE_MISSED` | 拒绝；禁"顺延执行" |
| 授权过期/撤销（P1） | `AUTHZ_STALE` / `AUTHZ_REVOKED` | fail closed；在途命令终止 |
| 急停 | `EmergencyStopExecuted(source, scope)` | 最高优先级终止 |
| 回执缺失/超时 | `Unknown(MISSING_SIGNAL)` + `AttributionUnresolved` | 归属保持 UNKNOWN |
| 效果与请求分歧 | `RequestedEffectiveDivergence(BLOCKED/SUBSTITUTED/COERCED/FAULT)` | 归属走对应分支；禁归自产 |
| 归属证据冲突 | `Unknown(CONFLICTING_EVIDENCE / ATTRIBUTION_UNRESOLVED)` | **保持 UNKNOWN**（禁默认） |
| 主体读 ExecutionFact 企图 | `ProhibitedReadPath(EVIDENCE_TO_SUBJECT)` | **S0** |
| PhysIO 控制图 digest 不符 | `ControlGraphViolation(expected, actual)` | fail closed；禁执行 |
| 设备未授权接入 | `DeviceUnauthorized(device_id)` | fail closed + S1 |
| 检出 `coercion → SELF_PRODUCED` | `AttributionRuleViolation` | **S0**（违反 HLD §8 硬规则） |

## 7. 可测性

| 层 | 测试 | 断言 |
|---|---|---|
| unit | 八项校验顺序与短路、幂等键、divergence 分类 | 确定性 |
| contract | 链条九型分离（intention/authz/command/fact/receipt/outcome/efference/attribution/settlement）；`ExecutionFact` 对主体不可见；四类授权只读 | schema + 权限强制 |
| invariant | `intention ≠ execution ≠ receipt`；`fact ≠ received outcome ≠ attribution ≠ learning`；coercion 永不自产；gateway 无旁路 | HLD §11.1/§8 |
| deterministic replay | 同 (profile, seed, 意图序列, 干预序列) → 授权/归属/结算序列 bit-exact | M0 |
| **fail-closed** | 未授权尝试矩阵（八项校验逐项构造违规）→ 全部 REJECTED 且 reason_code 正确；无一项"宽松通过" | **M0 硬条件** |
| **五类干预电池**（联动 L01 §4.3/§7） | no-op（回执在、效果无）→ 归属不应为 SELF_PRODUCED(有效)；sham（效果被替换）→ 归属应检出分歧；blocked → `CONTAINMENT/CAPABILITY` 拒绝类型化；fault → `FAULT` 归属；coercion → `COERCED`。**判别力达冻结最小效应**（Q-L01-05） | **M0/M1 硬条件** |
| **交叉操纵校准** | 归属正确率 vs 随机基线（no-op/sham 判别）；来源线索交叉操纵（承 L01 MW0-SC4）；迟到结果 revision 不破坏历史 | **M1 硬条件** |
| probability calibration | 概率 agency 的后验校准（C4，需 L13 统计计划） | C4 |
| efference timing | EfferenceCopy 必早于效果到达（同 cycle 或更早）；移除 → forward model 预测应退化 | C4 |
| **P1 授权矩阵** | 四类授权各自过期/撤销/设备更换 → 均 fail closed；急停即时生效；PhysIO 控制图 digest 不符 → 拒执行；L0–L5 逐级授权不可跳级 | P1 |
| leakage | 归属/结算是否引用 ExecutionFact 或 evaluator 标签；PhysIO 传感是否绕过 Sensorium | 无泄漏 |
| protection suite | M0/M1 干预电池场景冻结为保护集，C0+/E1 不退化 | E1 |

**指标**：八项校验各自拒绝率与 reason 分布｜fail-closed 覆盖率=100%（无宽松通过）｜未签名命令到达数=0｜五类干预判别力效应量｜归属正确率 vs 随机基线｜`UNKNOWN` 归属率（应随证据不足上升，非恒 0）｜coercion 误归自产数=**0**（硬指标）｜急停响应延迟｜授权 freshness 校验覆盖率=100%｜EfferenceCopy 先行率=100%｜归属延迟。

**无效指标**：动作吞吐、支持的命令种类数、"看起来有自主性"的演示。

## 8. 不变量与禁止写入路径

**专属不变量**：
1. `intention ≠ execution ≠ receipt`；`fact ≠ received outcome ≠ attribution ≠ learning`（HLD §11.1）；
2. gateway 是现实效果的**唯一**合法通道，fail closed 为默认；八项校验任一失败即拒；
3. `ExecutionFact` 对主体平面物理不可见（EVIDENCE_ONLY 命名空间 + 权限测试）；
4. 归属只用主体可见证据（选择/回执/形成后结果/预测误差），可保持 `UNKNOWN`；
5. **强制动作（coercion）永不得归为自产**（硬规则 + 测试断言）；
6. `requested ≠ effective` 必须在 `execution_branches[]` 显形，禁合并；
7. gateway 拒绝不得被改写为"主体选择不行动"；反之，未授权效果必须类型化；
8. P1：四类现实授权独立记录、主体只读、任一失效即 fail closed；PhysIO 非学习、有界控制图、不旁路 Sensorium/gateway/receipt/evidence；
9. capability 来自 profile/promotion 与授权，**不来自语言自述**（承 D-13、L08 C-1）。

**禁止写入路径**：`controller/intention → Environment（绕过 gateway）`｜`gateway → ExecutionFact（执行真值由独立源产生）`｜`ExecutionFact → 主体可见命名空间/归属输入`｜`evaluator label → subject attribution`｜`any module → 四类授权记录`｜`learner → capability policy（在线）`｜`LLM/语言 → capability/授权提升`｜`attribution → OwnedGoal 直写（只供结算）`｜`PhysIO → Sensorium 绕过（传感必经 Adapter→ReceivedSignal）`。

## 9. 引入门槛

- **F0**：链条九型对象图、权限矩阵、`ExecutionFact` 的 EVIDENCE_ONLY 命名空间约定、四类授权 schema 冻结（进 frozen profile）。
- **M0**（硬）：gateway 八项校验 + fail-closed；未签名命令拒绝；五类干预电池联动 L01；意图/授权/执行/回执可分；确定性重放。**M0 失败不启动 M1**。
- **M1**（硬）：归属经交叉操纵校准（no-op/sham 判别力达冻结最小效应）；`GoalSettlement` 与 L08 闭环；来源判断与归属协同（L03 `SourceJudgement` 作为输入之一，但**不**替代归属）。
- **C4**：概率 agency（校准后验）；EfferenceCopy/forward model 闭环（L04）；多来源匹配测试；中央 LLM 消融时归属不得退化（承 card_06 C4）。
- **C5**：归属经验回流经 promotion（L11）；保护集回退时 gateway policy 可回滚。
- **E1**：gateway lesion（关闭 → 未授权效果应被环境侧拒绝，可辨）；归属系统 lesion（→ 归属退化为随机/固定，选择性）；`core_decision_registry` 的"行动/委托/权限"路径**主要**由本档承载；六类路径枚举已裁决（Q-G00-04，AI-v2 2026-09-23，card_04 原文采纳），60 格逐格闭合仍为 E1 交付。
- **H1**：故障注入下 gateway 行为稳定；授权台账长时运行一致；供应链 hash 审计（承 Q-T08）覆盖 policy/控制图 digest。
- **P1**：四类现实授权全生命周期；L0–L5 分级（六级定义见 §4.6：L0 硬保护地板 + L1 passive→L5 active）；外部独立急停；设备新增/更换/隔离/重新纳入流程；**不得**旁路 Sensorium/gateway/receipt/evidence。

## 10. 实现清单（文件级）

```text
galatea/subject/action/                     # strict 类型
  ports.py               PortIn/PortOut、九型分离断言、EVIDENCE_ONLY 命名空间隔离
  gateway.py             八项校验（固定顺序 + 短路）、fail-closed、AuthorizationDecision
  signature.py           gateway_signature 生成/校验（与 L01 world.apply 对接）
  command.py             SubmittedCommand、idempotency_key、deadline、预算
  branches.py            execution_branches[]、domain 分类、RequestedEffectiveDivergence
  efference.py           EfferenceCopy 同步产生、时序断言（先于效果）
                         【C4 实现期首单元交付】issue_efference_copy + EfferenceTimingViolation
                         （先行 PREDICTED 层强制 + issued≤valid_time 构造断言，test_efference_timing.py）
  attribution.py         六类判定规则、可见证据白名单、概率后验、UNKNOWN 保持
                         【C4 实现期首单元交付】probability agency = 三轴八格构造性查表
                         （c4 profile cells 冻结；歧义格→UNKNOWN(ATTRIBUTION_UNRESOLVED) 留痕率 100%
                         + 端点格/kind 一致性断言 + coercion 永不自产，test_attribution_probability.py；
                         Q-L10-05 AI-v2 2026-10-07）
  coercion_guard.py      硬规则：coercion 永不自产（代码分支 + 断言）
  settlement.py          GoalSettlement 构造（→ L08）、revision
  receipt.py             ActionChainReceipt
  physio/                # P1（C0-M2 期为 stub，接口冻结）
    bridge.py            PhysIO Bridge（传感 → L01 Adapter）
    controlgraph.py      有界 PhysIOControlGraph、digest 冻结校验、禁未签名加载
    drivers.py           版本化驱动/校准/确定性滤波/冻结参数
    graded.py            L0–L5 六级分级控制（定义见 §4.6；L0 为不可授权地板）
    protection.py        硬件级局部保护 + 急停响应
    authorizations.py    四类授权只读校验、freshness、撤销/重授权
galatea/subject/action/tests/
  test_gateway_failclosed_matrix.py test_unsigned_command_rejected.py
  test_intervention_battery_attribution.py test_noop_sham_discrimination.py
  test_coercion_never_self.py test_execution_fact_invisible.py
  test_efference_timing.py test_settlement_unknown_legal.py
  test_execution_branches.py test_action_chain_receipt.py   # M1（ADR-G-0005 R5 移交件落地测试，v1.0.1 补录）
  test_authz_matrix_p1.py test_estop_priority.py test_controlgraph_digest.py
config/profiles/
  f0_action_contract.profile.yaml   九型对象图、权限矩阵、授权 schema（F0 冻结）
  m0_gateway.profile.yaml           八项校验参数、containment 白名单（MW0 5 原语）
  m1_attribution.profile.yaml       归属规则参数、判别力最小效应（联动 Q-L01-05）
  p1_physio.profile.yaml            四类授权、L0–L5、控制图 digest 清单（P1 前冻结）
```

## 11. 未决问题（→ open_questions.md）

| Q 号 | 问题 | 依赖 | 状态 |
|---|---|---|---|
| Q-L10-01 | budget 默认值体系（每类动作的次数/资源配额）与 MW0 期是否设硬配额 | F0/M0 | CONFIRMED（AI-v2 2026-09-23：硬配额；每 cycle ≤2 条 + 每 1024-cycle 窗口 move 256/forage 128/eat 96/rest 128/look 128；M0 复核） |
| Q-L10-02 | idempotency 窗口长度（cycles）与跨分支的键作用域 | M0 | CONFIRMED（AI-v2 2026-09-25：64 cycles，键作用域 (run_id, branch_id) 全局，见 A 区） |
| Q-L10-03 | L0–L5 各级的精确定义、每级所需授权组合与升降级条件 | P1（schema 在 F0 冻结） | CONFIRMED（AI-v2 2026-09-23：六级定义与升降级规则见 §4.6；schema 入 F0，参数 P1 定） |
| Q-L10-04 | 归属六类判定的证据规则阈值（残差阈、时间约束、后验校准门限） | M1/C4 + L13 统计计划 | CONFIRMED（AI-v2 2026-09-23，随 Q-L13-09：\|z\|≤2 一致带；ECE≤0.10；反射窗 ≤2 cycles，随 Q-L09-06 C0 复核） |
| Q-L10-05 | 概率 agency 后验的计算形式与校准判据（与 Q-L03-04 同源标度问题） | C4 | CONFIRMED（AI-v2 2026-10-07，裁决见 open_questions.md A 区） |
| Q-L10-06 | 四类授权模板（字段、批准者标识、撤销路径、重授权流程）| P1（前置 F0 schema） | CONFIRMED（AI-v2 2026-09-23：统一信封 schema 12 字段；批准者=外部授权方登记册；撤销 append+freshness；禁自动续期；schema 入 F0） |
| Q-L10-07 | gateway policy 更新流程（promotion + 重授权 + 审计）与"重大变化"的判定 | C5/H1 | CONFIRMED（AI-v2 2026-10-08，裁决见 open_questions.md A 区） |
| Q-L10-08 | 急停响应时间上界与在途命令的终止语义（部分执行如何处理） | P1/H1 | CONFIRMED（AI-v2 2026-10-10，裁决见 open_questions.md A 区） |
| Q-L10-09 | MW0 期 Reflex（L09 Q-L09-06）与 T0 硬保护的职责分界，避免 containment 双写 | C0 | CONFIRMED（AI-v2 2026-09-25：T0=环境侧硬保护，containment 唯一职责在 gateway，随 Q-L09-06 成组，见 A 区） |
