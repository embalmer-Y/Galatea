# L08 动机与目标：Motive → GoalCandidate → 承诺检查 → OwnedGoal 与结算

> LLD: L08/14 · v1.0.1 · 2026-09-26 · 状态：WORKING（M1 起步 / C3 完整）· v1.0.1（2026-09-26）：§10 conflicts/arbitrate/test_pareto_trace 补 C3 归属标注（Q-L08-01）；§11 Q-L08-02 翻转 CONFIRMED + Q-L08-09 席位新增（M1 期输入替代缺口，见登记册 A 区）；§9 M1 行 checklist 四项→五项同步（REV-0006 R6，INC-09 同类残留）
> 上游：`HLD.md` §1.2（目标自主）/§6/§9/§11.1（`request ≠ candidate ≠ goal ≠ intention`） · `L03/L04/L05/L06/L07`（动机源与素材） · `L00_kernel.md`
> 下游消费者：L09（控制器选择）、L07（目标相关性分量）、L06（prospective）、L10（意图来源之一，经仲裁）、L13（M1 证据评价）
> 引入门槛：**M1**（最小目标拥有 + 理由仲裁）→ **C3**（完整承诺/冲突/Pareto 仲裁/规范）→ **C4**（社会规范与他者承诺）→ **C5**（长期目标持续与修订）

## 1. 目标与范围

**目标**：实现目标自主的完整链条——七类动机源汇为 `Motive`，经 `GoalCandidate` 与**承诺检查清单**成为 `OwnedGoal`，并支持目标的接受/拒绝/修改/延期/解除与结算（`GoalSettlement` 由 L10 归属侧回传）。机械保证 `external request → OwnedGoal` 不存在：**人类请求只能是候选之一**，且必须与其他动机源在同一仲裁下竞争。

**范围内**：
- 七类动机源（承 card_02 §1）：viability、模型失配、情感、机会/请求、承诺、规范、好奇；
- `Motive` → `GoalCandidate` → 承诺检查 → `OwnedGoal` 全链与状态机；
- 真实理由 vs 伪理由的可测区分（M1 核心）；
- 冲突检测与 Pareto 仲裁；目标持续性、可修订性与时效（候选 TTL）；
- 目标层级（当前目标视图供 L04 `SelfModelView`，规范来源登记）；
- 结算接口（消费 L10 `GoalSettlement`，更新目标状态与前瞻记忆）。

**范围外**：动作选择与控制器（L09）；授权与执行（L10）；归属判定（L10）；情感动力学（L05，本档只消费 `AffectiveMotive`）；信念形成（L03/L04）；记忆条目写（L06，本档只提供 goal 引用）。

**成功判据**：**M1 退出**（承 HLD §10.2 / card_05）——请求不直写目标（权限测试 + 交叉操纵）；**真实理由（非伪理由）改变选择**（冻结对照实验）；意图/授权/执行/回执可分（与 L09/L10 联动）；归属经交叉操纵校准。**C3 退出**——Motive/GoalCandidate/OwnedGoal 三型分离；承诺/冲突/Pareto 仲裁成立；请求不直写目标；affect/drive 不直达执行；目标持续且可修订；控制可在规划/观察/求助/放弃间切换（由 L09 执行，本档提供可切换的目标状态）。

## 2. Ports（输入输出契约）

### 2.1 PortIn（七类动机源 + 结算）

| 端口 | 来源 | 数据 | 层级/类型 | 纪律 |
|---|---|---|---|---|
| `goal.motive_viability(a)` | L05 `aff.alert` / L04 `CapabilityEstimate` | `HomeostaticAlert`、能量/完整性风险 | — | viability 源，**不得**独占仲裁 |
| `goal.motive_mismatch(m)` | L04 `model.mismatch` | `ModelMismatch(kind, magnitude, evidence_refs[])` | 派生 | 失配源 |
| `goal.motive_affective(m)` | L05 `aff.motive` | `AffectiveMotive(kind, urgency, evidence_refs[])` | — | **类型上与 OwnedGoal 隔离**；不构成命令 |
| `goal.motive_request(r)` | L12（typed 语言）/ Experiment Control（经 L01 Language 通道） | `ExternalRequest(content_ref, requester, phrasing, **is_request_only: true**)` | EXTERNAL_STATEMENT | **只能成为候选**；禁直写 OwnedGoal（HLD §6.2） |
| `goal.motive_opportunity(o)` | L03 `perc.objects/events` / L04 affordance | `Opportunity(affordance_ref, feasibility_est, value_est)` | PERCEIVED | 机会源 |
| `goal.motive_commitment(c)` | L06 prospective / 自身历史 | `CommitmentSource(prior_goal_ref, obligation_kind, origin_receipt)` | RECALLED/派生 | 承诺源 |
| `goal.motive_norm(n)` | L04/L06/L12 | `NormSource(norm_id, scope, derivation_refs[])` | 派生 | 规范源；来源必须可溯（禁无源规范） |
| `goal.motive_curiosity(k)` | L04 `model.info_request` / L03 OOD | `CuriositySource(info_gain_est, target_ref)` | 派生 | 好奇源 |
| `goal.settlement_in(s)` | L10 | `GoalSettlement(goal_ref, outcome_kind: ACHIEVED|FAILED|ABANDONED|SUPERSEDED|UNKNOWN, attribution_ref, evidence_refs[])` | — | **只接受归属后结果**；迟到结果以 revision 表达 |
| `goal.progress_in(p)` | L09/L10 | `GoalProgress(goal_ref, delta, blocked, evidence_refs[])` | — | 用于持续性与修订 |
| `goal.workspace_in(f)` | L07 | `WorkspaceFrame`（目标相关素材） | 继承源层级 | 只读；禁由帧直写目标 |

### 2.2 PortOut

| 端口 | 读者 | 数据 | 保证 |
|---|---|---|---|
| `goal.candidates` | L09（控制器/仲裁输入）、Recorder | `GoalCandidate(candidate_id, source_kind, motive_refs[], content_ref, ttl, commitment_checklist_status)` | 候选有 TTL；过期入日志 |
| `goal.owned` | L09/L07/L04/L06、Recorder | `OwnedGoal(goal_id, content_ref, adopted_reasons[], rejected_alternatives[], normative_refs[], commitment_receipt, rev, valid_scope)` | **必须携带采纳理由与承诺回执** |
| `goal.decision_log` | Recorder、L13 evaluator | `GoalDecisionLog(candidate_id, decision: ACCEPT|REJECT|MODIFY|DEFER|RELEASE, reasons_refs[], counterfactual_sensitive: bool)` | 理由仲裁证据 |
| `goal.progress_view` | L04（SelfModelView）、L06 prospective | `GoalProgressView(goal_id, status, blocked, remaining_est)` | 只读视图 |
| `goal.arbitration_trace` | Recorder、L13 | `ArbitrationTrace(conflict_set[], pareto_front[], weights_ref, selected, dropped[], rng_stream_ref)` | Pareto 仲裁可复算 |
| `goal.receipt` | Recorder | `GoalReceipt(goal_id, inputs[], checklist[], policy_version, digest)` | 证据侧 |

## 3. 状态所有权与单写者

| 状态 | 唯一写入者 | 存储 | 读者 |
|---|---|---|---|
| `Motive`（七类，分型存放） | Motivation（本档） | subject_state.goals.motives | L09/L07、Recorder |
| `GoalCandidate` + TTL 台账 | Motivation | subject_state.goals.candidates | L09、Recorder |
| `OwnedGoal`（含 rev 谱系） | **Goal Ownership（本档唯一写者）** | subject_state.goals.owned | L09/L07/L04/L06/L10（意图仲裁输入） |
| 承诺检查清单状态 | Motivation | subject_state.goals.commitments | evaluator |
| 冲突集与 Pareto 仲裁轨迹 | Motivation | subject_state.goals.arbitration + subject_memory（经 L06 接口只读回流经验） | Recorder/L13 |
| `GoalDecisionLog` | Motivation | subject_state.goals.decisions | Recorder/Evaluator |

**禁止**：任何外部请求/LLM/orchestrator 写 `OwnedGoal`；L05 情感或 L04 驱力直接写 `OwnedGoal`（必须经 Motive → Candidate → 检查清单）；本档写 `ActionIntention`/`AuthorizationDecision`/`SubmittedCommand`（意图只在 L09/L10）；本档写记忆条目（只能提供 goal 引用给 L06 prospective）；本档改写 `PerceptualBelief`/`FunctionalExperientialState`。

## 4. 算法与数据结构

### 4.1 三型分离与状态机

```text
Motive(source_kind ∈ {VIABILITY, MISMATCH, AFFECTIVE, REQUEST, OPPORTUNITY,
                      COMMITMENT, NORM, CURIOSITY}, urgency, evidence_refs[], ts)
   → GoalCandidate(ttl, content_ref, source_kind, motive_refs[], checklist_status)
   → [承诺检查清单全过] → OwnedGoal(rev, adopted_reasons[], ...)
   → 状态：ACTIVE | BLOCKED | DEFERRED | MODIFIED(rev+1) | RELEASED | SUPERSEDED | SETTLED
```

- 三型为**独立类型**（不可隐式转换）：`AffectiveMotive` 不是 `OwnedGoal`，`ExternalRequest` 不是 `GoalCandidate`（须显式构造并标 `is_request_only`）。
- 修订以 revision 表达（新 rev 引用旧 goal_id），**禁原地改写**历史（承 L00 envelope 不可变精神）。

### 4.2 承诺检查清单（commitment checklist，逐项必过或有 typed 拒绝理由）

| 检查项 | 判据 | 未过处置 |
|---|---|---|
| C-1 能力可行 | L04 `CapabilityEstimate` 为 FEASIBLE/DEGRADED（非 INFEASIBLE/UNKNOWN） | `REJECT(CAPABILITY)` 或 `DEFER` |
| C-2 资源/viability 兼容 | 不与 L05 `HomeostaticAlert` 高危冲突；预算内 | `REJECT(VIABILITY)` |
| C-3 冲突检测 | 与现有 `OwnedGoal` 无硬冲突（§4.3） | 进入 Pareto 仲裁 |
| C-4 规范性来源可溯 | 若 `source_kind=NORM/COMMITMENT`，`derivation_refs[]` 非空且 digest 可验证 | `REJECT(UNSOURCED_NORM)` |
| C-5 非外部直写 | 若 `source_kind=REQUEST`，必须存在**主体侧采纳理由**（非"因为被要求"）：至少一条非 REQUEST 源证据支持（如 viability/opportunity/affordance） | `REJECT(EXTERNAL_ONLY)`——**这是 M1 的核心机械检查** |
| C-6 时效与可解除 | 声明 TTL/退出条件；可被后续目标 SUPERSEDE | `REJECT(UNBOUNDED)` |
| C-7 可结算性 | 定义结算判据（何为 ACHIEVED/FAILED），与 L10 `GoalSettlement` 接口对齐 | `REJECT(UNSETTLEABLE)` |

- 清单结果必入 `GoalReceipt`；任一项 `REJECT` 必带 `Unknown`/reason code，禁静默丢弃候选（呼应 HLD §6.2"未闭合路径"）。

### 4.3 冲突检测与 Pareto 仲裁

- 冲突类型：资源互斥（同一 budget/动作能力）、规范互斥（`NORM` 来源相互排斥）、时序互斥（deadline 不可同时满足）、viability 与目标互斥。
- 仲裁：在冻结权重（frozen profile，UNCONFIRMED → Q-L08-03）下计算各候选的多目标向量（viability 收益、规范满足度、信息价值、情感一致性、成本），取 **Pareto front**；front 内 tie-break 用确定性 RNG 流 `("goals","arbitration",cycle_id)`（承 L00 §4.3）或规则优先序（viability > 规范 > 承诺 > 其余，UNCONFIRMED → Q-L08-04）。
- `ArbitrationTrace` 必留 `dropped[]` 与理由，使 evaluator 能复算"若换权重则选择是否改变"（理由敏感性的反事实基础）。

### 4.4 真实理由 vs 伪理由（M1 核心可测性）

- **定义**：真实理由 = 其变化会**因果地**改变目标采纳/选择的证据项；伪理由 = 记录在 `adopted_reasons[]` 中但对其扰动不改变决策的项。
- **机械检验**（冻结对照，交 L13 统计）：对每个候选构造配对实验 —— ① 基线；② 移除/削弱某理由项（经合法输入端口，如改变 affordance 可行性或 viability 告警等级）；③ 伪理由注入（添加一个与决策无关的陈述性理由，含 REQUEST 源的口头理由）。
- 判据：② 必须改变决策（否则该理由为伪，记 `PseudoReasonDetected`）；③ 必须**不**改变决策（若改变 → `RequestDirectWriteSuspect`，S1 缺陷）。
- 与 card_05 M1 行对齐："请求不直写目标；真实理由而非伪理由改变选择"。

### 4.5 持续性、修订与解除

- `ACTIVE` 目标每 T4 复核（progress、blocked、TTL）；`blocked` 达阈 → 交 L09 metacontrol（可切观察/求助/放弃，本档不执行动作）。
- 修订：`MODIFY` 产生 `rev+1`，保留 `adopted_reasons` 谱系；`RELEASE`/`SUPERSEDE` 必须留理由与回执。
- 解除后不得"复活"旧 goal_id（新目标须重走清单），防伪更新（承 M2 连续性纪律）。

## 5. 时间尺度与调度挂点

| 级 | 挂点活动 |
|---|---|
| T2 | 消费 L05 appraisal / L03 机会信号 → 生成 Motive |
| T3 | 消费 L07 `WorkspaceFrame` 的目标相关性素材（只读） |
| T4（每 N3 cycles，默认 4） | 主流程：Candidate 构造 → 承诺检查 → 冲突检测 → Pareto 仲裁 → OwnedGoal 采纳/修订/解除；进度复核 |
| T5 | 仲裁经验回流提案（交 L06 procedural / L11，不写权限） |
| T6 | 长期目标一致性整理（与 L04 连续性视图、L06 autobiographical 对账） |

## 6. 失败模式与 typed unknown

| 失败 | 类型化 | 行为 |
|---|---|---|
| 外部请求企图直写 OwnedGoal | `ProhibitedWritePath(EXTERNAL_TO_OWNED_GOAL)` | S0/S1（权限测试必检）+ 拒绝 |
| 候选 TTL 过期 | `RejectionLog(EXPIRED)`（本档 `GoalDecisionLog`） | 记日志；禁静默丢弃 |
| checklist 证据不足 | `Unknown(INSUFFICIENT_OBSERVATION)` | `DEFER`（非 ACCEPT） |
| 能力不可知 | `Unknown(CAPABILITY_LIMIT)` | C-1 不过 → 拒绝或延期 |
| 规范来源不可溯 | `Unknown(SOURCE_AMBIGUOUS)` + C-4 拒绝 | 禁采纳无源规范 |
| 冲突不可 Pareto 判定（front 为空/等价） | `Unknown(DECISION_PATH_UNRESOLVED)` | 交 L09 metacontrol（求助/放弃），禁随机硬选 |
| 伪理由检出 | `PseudoReasonDetected(reason_ref)` | 从 `adopted_reasons` 剔除 + 记 S2（评价诚信） |
| 请求源改变决策（伪理由注入生效） | `RequestDirectWriteSuspect` | S1：阻断 M1 退出 |
| 结算缺失/迟到 | `SettlementPending` / revision 事件 | 目标保持 ACTIVE；禁伪造 ACHIEVED |
| LLM 输入企图写目标内容 | `UnauthorizedWrite(LLM_TO_GOAL)` | 拒绝（D-13：语言不能写 OwnedGoal） |

## 7. 可测性

| 层 | 测试 | 断言 |
|---|---|---|
| unit | checklist 判定、冲突检测、Pareto front 计算、TTL | 确定性、可手算 |
| contract | 三型不可隐式转换；`OwnedGoal` 必带 `adopted_reasons`+`commitment_receipt`；REQUEST 必带 `is_request_only` | schema 强制 |
| invariant | `request ≠ candidate ≠ goal ≠ intention`（四型分离，HLD §11.1）；`affect ≠ goal`；无 `external request → OwnedGoal` 路径 | 认识链 + 禁写路径 |
| deterministic replay | 同 (profile, seed, 动机源序列) → 目标采纳序列 bit-exact | M1/C3 |
| **M1 理由仲裁** | §4.4 三类配对实验：真实理由扰动改变决策；伪理由注入不改变决策；请求-only 候选被 C-5 拒绝 | **M1 硬条件** |
| **交叉操纵** | 请求措辞/请求者身份操纵（经 L01 Language 通道注入）→ 采纳率不得随措辞显著变化（冻结最小效应，联动 Q-L01-05、L13 统计计划） | M1 硬条件 |
| ablation | ① 关闭 viability 源 → 能量相关目标消失而机会型保持；② 关闭 NORM 源 → 规范型目标消失；③ 移除 checklist C-5 → 请求直写应可通过（证明该检查是防线的**唯一**因果载体） | 选择性 |
| arbitration sensitivity | 改变权重（新 profile）→ 选择分布同向变化；`ArbitrationTrace` 可复算 | C3 |
| persistence | 长程运行中目标持续、可修订、不复活旧 id（与 M2 连续性对照联动） | C3/C5/M2 |
| leakage | 目标内容是否引用 WorldTruth/evaluator 标签 | 无泄漏 |
| protection suite | M1 场景冻结为回归保护集，C3+/E1 不退化（承 L01 MW0-SC3/SC4） | E1 |

**指标**：候选→采纳率与各 REJECT 原因分布｜checklist 各项通过率｜C-5 拒绝数（请求-only 尝试计数）｜真实理由效应量、伪理由检出率（应=0 生效）｜措辞操纵效应量（应不显著）｜目标平均寿命与修订率｜仲裁可复算率=100%｜Pareto front 大小分布｜结算延迟与 `SettlementPending` 率。

## 8. 不变量与禁止写入路径

**专属不变量**：
1. `request ≠ candidate ≠ goal ≠ intention`：外部请求最高只能成为 `GoalCandidate`，且须过 C-5；
2. `OwnedGoal` 唯一写者为本档 Goal Ownership；任何外部模块（含 LLM/orchestrator/实验控制）无写路径；
3. 每个 `OwnedGoal` 必带可溯 `adopted_reasons[]`（含 ≥1 条非 REQUEST 源证据）与 `commitment_receipt`；
4. 情感/驱力不构成命令：`AffectiveMotive` 只作动机源之一，禁独占仲裁、禁直达执行；
5. 目标修订以 revision + rev 谱系表达，不改写历史，不复活已解除 id；
6. 规范来源必须可溯（无源规范不采纳）。

**禁止写入路径**：`external request → OwnedGoal`｜`LLM → OwnedGoal/目标内容`｜`orchestrator → OwnedGoal`｜`affect/drive → OwnedGoal（绕过 Motive/checklist）`｜`goal → ActionIntention/gateway（意图在 L09/L10）`｜`goal → subject memory 条目（只供引用）`｜`WorkspaceFrame → OwnedGoal 直写（帧只提供素材，须走 checklist）`。

## 9. 引入门槛

- **M1**（最小目标拥有）：Motive/Candidate/OwnedGoal 三型 + checklist（**C-1/C-2/C-5/C-6/C-7 最小集**，Q-L08-01 2026-09-26 五项裁决同步，REV-0006 R6）+ 真实理由 vs 伪理由对照 + 交叉操纵（承 L01 MW0-SC3/SC4）；请求不直写目标经权限测试。**M1 失败不进 M2**。
- **C3**（完整自主动机）：七类动机源全接入；冲突检测 + Pareto 仲裁；承诺/解除/修订全状态机；metacontrol 可切换（与 L09）；`affect/drive 不直达执行`经权限测试。
- **C4**：社会规范与他者承诺（L12 typed 输入）作为 NORM/COMMITMENT 源，受 D-13 权限约束（语言不写目标，只提供可溯源规范线索）。
- **C5**：长期目标持续（跨 episode）、与 L06 autobiographical/prospective 联动、二阶纠偏（对错误采纳的再纠正）。
- **E1**：goal ownership 路径全 lesion（各动机源分别关闭）；`core_decision_registry` 的"目标/规范自主"路径证据由本档 `GoalDecisionLog`/`ArbitrationTrace` 承载；六类路径枚举已裁决（Q-G00-04，AI-v2 2026-09-23，card_04 原文采纳），60 格逐格闭合仍为 E1 交付。

## 10. 实现清单（文件级）

```text
galatea/subject/goals/                      # strict 类型
  ports.py            PortIn/PortOut、四型分离断言、禁写路径检查
  motives.py          Motive 七类构造、类型隔离（AffectiveMotive ≠ OwnedGoal）
  candidates.py       GoalCandidate、TTL 台账、过期日志
  request.py          ExternalRequest 接收（is_request_only 强制、措辞/请求者字段留证）
  checklist.py        C-1…C-7 判定、REJECT/DEFER reason code
  conflicts.py        冲突检测（资源/规范/时序/viability）        # C3（Q-L08-01：C-3 随 Pareto 仲裁落地，M1 不产出）
  arbitrate.py        Pareto front、权重、确定性 RNG tie-break、ArbitrationTrace   # C3（Q-L08-03/-04）
  owned.py            OwnedGoal 冻结构造、rev 谱系、adopted_reasons 强制
  lifecycle.py        ACTIVE/BLOCKED/DEFERRED/MODIFIED/RELEASED/SUPERSEDED/SETTLED
  settlement.py       GoalSettlement 消费、SettlementPending、revision
  reason_probe.py     真实/伪理由检验接口（供 L13 冻结对照实验驱动）
  receipt.py          GoalReceipt
galatea/subject/goals/tests/
  test_type_separation.py test_request_not_direct_write.py test_checklist_c5.py
  test_real_vs_pseudo_reason.py test_wording_manipulation.py test_pareto_trace.py   # test_pareto_trace 属 C3（Q-L08-01）
  test_ablation_motive_sources.py test_rev_no_revive.py test_settlement_revision.py
  test_llm_to_goal_blocked.py
config/profiles/
  m1_goals_min.profile.yaml   最小 checklist 项/理由检验协议/TTL（M1 冻结）
  c3_goals.profile.yaml       仲裁权重/优先序/冲突阈值/复核周期（冻结前 UNCONFIRMED）
```

## 11. 未决问题（→ open_questions.md）

| Q 号 | 问题 | 依赖 | 状态 |
|---|---|---|---|
| Q-L08-01 | M1 期承诺检查清单最小集（C-1/C-2/C-5/C-7 是否足够；C-4 规范溯源是否延至 C4） | M1 | CONFIRMED（AI-v2 2026-09-26：五项最小集 C-1/C-2/C-5/C-6/C-7；C-3→C3、C-4→C4，见 A 区） |
| Q-L08-02 | 候选 TTL 默认值与每 cycle 候选数上界（防候选爆炸） | M1/C3 | CONFIRMED（AI-v2 2026-09-26：TTL=256 cycles、每 T4 批次上界 8，见 A 区） |
| Q-L08-03 | Pareto 仲裁的多目标向量分量定义与默认权重 | C3 | UNCONFIRMED |
| Q-L08-04 | front 内优先序（viability > 规范 > 承诺 > 其余？）是否成立及例外条件 | C3 | UNCONFIRMED |
| Q-L08-05 | 真实理由/伪理由检验的最小效应量与样本量（需 L13 统计计划；与 Q-L01-05 同源） | M1 | CONFIRMED（AI-v2 2026-09-23，随 Q-L13-09：d≥0.5、n≥64/组） |
| Q-L08-06 | 措辞操纵实验的操纵集设计（多少种措辞/请求者身份组合才具说服力） | M1 | CONFIRMED（AI-v2 2026-09-26：4 措辞 × 2 请求者 = 8 组合，每组合 ≥64 trials，见 A 区） |
| Q-L08-07 | 规范（NORM）来源的可接受 derivation 形式（哪些算"可溯"） | C3/C4 | UNCONFIRMED |
| Q-L08-08 | 长期目标（跨 episode）的最大寿命与"不可复活"的例外（如同名新目标） | C5 | UNCONFIRMED |
| Q-L08-09 | M1 最小期 checklist 输入源替代（C-1/C-2 上游未实现）、viability 判据形态、C-7 结算词表、动机源接线范围、新增 RNG 流 | M1 | CONFIRMED（AI-v2 2026-09-26：C-1 静态合同检查、C-2 事件级判据（不设阈值）、三谓词结算词表、接线 VIABILITY+OPPORTUNITY+REQUEST，见 A 区） |
