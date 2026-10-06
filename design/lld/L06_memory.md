# L06 记忆：八子系统、来源类型、检索、巩固与遗忘控制

> LLD: L06/14 · v1.0.4 · 2026-10-06（v1.0.4：C2 次单元交付标注——五子系统的 C2 件全量落地；v1.0.3：参数裁决批 + profile 冻结）· v1.0.2 2026-10-02（交付计数勘误）· 原版 2026-09-13 · 状态：WORKING（C2 实现期；M2 依赖件已交付）
> 上游：`HLD.md` §4.2/§5/§6/§11.1（`recorder ≠ memory`） · `L02/L03/L04`（帧/信念/模型状态） · `L05`（AffectiveValueTag） · `L00_kernel.md`（三库分离，`subject_memory.db` 由本档独占写）
> 下游消费者：L03（线索）、L04（回忆对照）、L07（候选）、L08（承诺/规范）、L09（经验策略）、L11（重放）
> 引入门槛：**C2**（分层记忆 + 来源类型）→ **C5**（持续写入/巩固/遗忘控制/保护集，与 L11 联动）

## 1. 目标与范围

**目标**：实现主体的八个记忆子系统，使"经历"能以**非初始化路径**从一轮延续到下一轮（M2 退出纪律的认知载体）；每条记忆必带**来源类型**与 `representation_level`，回忆恒为 RECALLED，禁提升为知觉或事实。`recorder ≠ memory`：独立记录器不是主体记忆，主体不得读取 recorder 真值来"补记忆"。

**范围内（八子系统，承 card_02 §1）**：
1. `working`（工作记忆，短寿、与 L07 协同但独立所有权）
2. `episodic`（情景：经历序列，含主体动作与后果）
3. `semantic`（语义：抽象规律/概念，由情景提炼）
4. `procedural`（程序性：技能/控制策略经验）
5. `affective_value`（情感价值标注，写侧来自 L05 标签）
6. `prospective`（前瞻性：待办/承诺提醒，来源限 L08 OwnedGoal）
7. `autobiographical`（自传体：自我连续性叙事，来源限 L04 `SelfModelView`）
8. `metamemory`（元记忆：对记忆可靠性的认识，含"我记得 vs 我推断"边界）

**范围外**：证据记录（L13 recorder，append-only 外部）；模型权重（L11/registry）；WorkspaceFrame（L07 独占，本档只提供候选）；任何 `recorder → belief/memory` 的真值回灌。

**成功判据**：记忆检索带来源类型且不可伪造来源；RECALLED 不被下游当作 PERCEIVED（层级守卫）；遗忘与巩固可控且不损保护集；M2 场景下"经历经非初始化路径进入下一轮"可证（冻结/重置/伪更新三类对照，承 L01 MW0-SC5）；`subject_memory.db` 对 orchestrator 只读、对 recorder 隔离（承 L00 §3）。

## 2. Ports（输入输出契约）

### 2.1 PortIn

| 端口 | 来源 | 数据 | 表示层级 | 纪律 |
|---|---|---|---|---|
| `mem.encode_working(item)` | L07（workspace 广播后）、L09 | `WorkingItem(frame_refs[], salience, ttl)` | 随源层级 | ttl 有限；禁无限驻留 |
| `mem.encode_episodic(ep)` | L09/L10（经历切片）、L02/L03 帧引用 | `EpisodeSlice(activity_window_id, frames[], beliefs[], actions[], outcomes[], attributions[], ts)` | 混合（逐项标注） | 必须引用事件 id，禁拷贝真值 |
| `mem.value_tag(tag)` | L05 | `AffectiveValueTag(memory_ref, valence, arousal, persistence)` | — | **L06 是唯一写者**，L05 只提案 |
| `mem.self_in(view)` | L04 | `SelfModelView` 派生 | PERCEIVED（派生视图） | 写入 autobiographical 时必须带 derivation_receipt |
| `mem.goal_in(g)` | L08 | `OwnedGoal` / `GoalSettlement` 引用 | — | prospective 唯一合法来源 |
| `mem.retrieve(q)` | L03/L04/L07/L08/L09 | `RetrievalQuery(kind, cues[], top_k, budget_cycles, purpose)` | — | 返回 RECALLED，附可靠度与来源类型 |
| `mem.replay_request(r)` | L11（T5） | `ReplayRequest(selection_policy, budget)` | — | 只读访问；产候选，不改原记忆 |
| `mem.consolidation_tick()` | L00 调度（T6） | — | — | 巩固/遗忘/语义抽象的唯一触发点 |

### 2.2 PortOut

| 端口 | 读者 | 数据 | 表示层级 |
|---|---|---|---|
| `mem.recall` | L03/L04/L07/L08/L09 | `RecalledContent(memory_ref, subsystem, source_type, level=RECALLED, reliability, retrieved_at, unknowns[])` | **RECALLED** |
| `mem.cue` | L03 | `RetrievalCue(kind, refs, confidence)` | RECALLED（只作先验线索） |
| `mem.prospective_due` | L08/L09 | `ProspectiveReminder(goal_ref, due_condition, origin_receipt)` | — |
| `mem.metamemory` | L09（metacontrol）、L04（边界元信息） | `MemoryReliability(subsystem, domain, est_confidence, evidence_refs[])` | 派生 |
| `mem.consolidation_receipt` | Recorder、L11 | `ConsolidationReceipt(promoted[], abstracted[], forgotten[], protection_checked, parent_digests[])` | EVIDENCE_ONLY |
| `mem.episodic_export` | L11（重放）、Recorder | 只读事件引用列表 | EVIDENCE_ONLY |

**纪律**：`source_type ∈ {PERCEIVED, SELF_GENERATED, RECALLED_DERIVED, LANGUAGE_INPUT, IMAGINED_DERIVED, UNKNOWN}`——**来源类型是强制字段**；`UNKNOWN` 来源的记忆不得用于自我连续性主张或归属证据。`LANGUAGE_INPUT` 记忆禁写入 episodic/autobiographical 的"经历"字段（D-13：语言不能写 episodic experience）。

## 3. 状态所有权与单写者

| 状态 | 唯一写入者 | 存储 | 读者 |
|---|---|---|---|
| 八子系统的记忆条目与索引 | Memory（各子系统单写者，统一在本档） | **subject_memory.db**（本档独占写，承 Q-T05） | 声明读者（只读）、L11 |
| `AffectiveValueTag` 落盘 | Memory（依 L05 提案） | subject_memory.db | L05/L07/L08 |
| 巩固/promotion 谱系（记忆侧 `parent_digests`） | Memory（T6） | subject_memory.db + registry 引用 | L11/L13 |
| `WorkingItem` 缓冲 | Memory | 内存 + checkpoint | L07/L09 |
| metamemory 统计 | Memory | subject_memory.db | L09/L04 |

**禁止**：`orchestrator → subject memory`（L00 §8 强制，CI 权限测试）；recorder/evaluator 写入主体记忆；主体读取 recorder 真值生成记忆（`recorder truth → belief/memory`）；L05/L08 直接写记忆条目（只能提案/引用）；本档写 `PerceptualBelief`/`WorkspaceFrame`/`OwnedGoal`/模型状态。

## 4. 算法与数据结构

### 4.1 记忆条目通用结构

```text
MemoryItem(
  memory_id, subsystem: enum{WORKING, EPISODIC, SEMANTIC, PROCEDURAL,
                             AFFECTIVE_VALUE, PROSPECTIVE, AUTOBIOGRAPHICAL, METAMEMORY},
  source_type: enum{PERCEIVED, SELF_GENERATED, RECALLED_DERIVED, LANGUAGE_INPUT, IMAGINED_DERIVED, UNKNOWN},
  representation_level: RECALLED 读取时恒定（写入时记录源层级 source_level）,
  content_ref: ArtifactRef,             # 大对象只读引用 + digest（禁内联真值拷贝）
  source_events: list[event_id],        # 完整溯源；空即 UNKNOWN
  affective: AffectiveValueTag?,
  strength: float, last_access: int, access_count: int,
  reliability: float | Unknown,         # metamemory 估计
  consolidation_state: enum{LABILE, CONSOLIDATING, CONSOLIDATED, PROTECTED, ARCHIVED, FORGOTTEN},
  parent_digests: list[str],            # 语义抽象/巩固的谱系（承 L00 registry）
  valid_scope, provenance, content_digest )
```

### 4.2 检索（带可靠度、有预算、确定性）

- 打分：$\text{score} = \alpha\cdot\text{cue\_sim} + \beta\cdot\text{strength} + \gamma\cdot\text{recency} + \delta\cdot|\text{affective.valence}| + \epsilon\cdot\text{reliability}$，权重冻结于 profile（UNCONFIRMED → Q-L06-02）；MW0 期 cue_sim 为枚举匹配（可手算）。
- tie-break 全序：`(score, subsystem, memory_id)`，保证跨平台确定性（承 L00 §4.1 精神）。
- 预算：`budget_cycles` 超限 → 返回部分结果 + `Unknown(INSUFFICIENT_OBSERVATION)`，禁静默截断。
- 无命中：返回空 + `Unknown(MISSING_SIGNAL)`，**禁用语义近邻或先验冒充回忆**（记忆污染风险）。

### 4.3 编码、强度与遗忘控制

- 编码强度受 L05 `MEMORY_ENCODER.encoding_strength` 有界调制（须回执，承 L05 §4.4）。
- 强度衰减：按 τ_sub 指数衰减（各子系统不同，UNCONFIRMED → Q-L06-03）；访问增强（有上限，防爆涨）；情感标注提升 persistence。
- **遗忘是显式状态转移**（`FORGOTTEN` + 保留 tombstone 与 digest 谱系），不是删除：tombstone 使"曾经记得但忘记"可审计，且保护集条目的遗忘必须被拒（§4.5）。

### 4.4 巩固与语义抽象（T6）

```text
T6 巩固流水线（顺序固定，可复算）：
  选取候选（LABILE 且 strength 达阈 / 情感标注高 / 被重放选中）
  → 语义抽象（同类情景 → SEMANTIC 条目，parent_digests 指向源情景）
  → 程序性提炼（成功的控制/技能经验 → PROCEDURAL，仅供 L09 提案参考，不写策略权限）
  → 保护集检查（§4.5）
  → 状态迁移 + ConsolidationReceipt（写侧 digest 入 registry）
```
- 抽象必须保留 `parent_digests`，使任一语义结论可回溯到源情景（防伪抽象）。
- 巩固**不得**改变已有条目的 `source_type`/`source_events`（来源不可篡改）。

### 4.5 保护集（防灾减灾性遗忘，承 card_06 C5/E1）

- `ProtectionSuite`（L11 定义场景，本档执行记忆侧检查）：被标 `PROTECTED` 的条目在遗忘/巩固/更新中不可被降级或删除；尝试即 `ProtectionViolation` 并阻断（S2 → 阻断阶段退出，承 HLD §13.3）。
- M2 对照场景（L01 MW0-SC5）：冻结（checkpoint 后恢复）、重置（清空 working/episodic 但保留谱系）、伪更新（声称延续但谱系断裂）三类对照下，记忆侧必须给出**可区分**的结果签名（`ContinuityGap` 与 `parent_digests` 断裂可检出）。

### 4.6 metamemory（元记忆）

- 维护各子系统在各域的可靠度估计（命中率、来源明确率、被证伪率），供 L09 metacontrol（"我该不该相信我的记忆"）与 L04 记忆/知觉边界。
- `RECALLED vs PERCEIVED` 混淆率是一等指标：以受控实验（呈现 vs 回忆线索交叉）测量；混淆率升高 → 降级 autobiographical 主张权（不得用于连续性论证）。

## 5. 时间尺度与调度挂点

| 级 | 挂点活动 |
|---|---|
| T1/T2 | working 缓冲刷新（短寿项过期回收） |
| T3 | 向 L07 提供候选（当前相关项 + 显著性分量），消费广播后写 working |
| T4 | 检索服务（L08/L09 的目标与规划查询） |
| T5 | 响应 L11 `ReplayRequest`（只读），产出重放候选序列 |
| T6（每 N5 cycles） | 巩固流水线：抽象/提炼/遗忘/保护集检查 + ConsolidationReceipt |

## 6. 失败模式与 typed unknown

| 失败 | 类型化 | 行为 |
|---|---|---|
| 检索无命中 | `Unknown(MISSING_SIGNAL)` | 返回空；禁近邻冒充 |
| 检索预算超限 | `Unknown(INSUFFICIENT_OBSERVATION)` | 部分结果 + 显式标记 |
| 来源缺失/不可判 | `source_type=UNKNOWN` + `Unknown(SOURCE_AMBIGUOUS)` | 可用于低阶联想，**禁**用于连续性主张与归属证据 |
| 保护集条目被要求遗忘 | `ProtectionViolation` | 阻断 + S2 缺陷 |
| 巩固谱系断裂（伪更新） | `LineageBreak(parent_digests)` | 阻断 promotion；M2 对照可检出 |
| 语言输入企图写 episodic/autobiographical 经历字段 | `UnauthorizedWrite(LANGUAGE_TO_EPISODIC)` | S1：拒绝 + 缺陷记录（D-13） |
| recorder/orchestrator 写入企图 | `ProhibitedWritePath` | S0（权限测试覆盖，承 L00 §7） |
| 条目 digest 校验失败 | `IntegrityViolation` | fail closed（承 L00 §6.2） |
| RECALLED 被下游当 PERCEIVED 使用（检出） | `RepresentationEscalation` | S0 |

## 7. 可测性

| 层 | 测试 | 断言 |
|---|---|---|
| unit | 检索打分与 tie-break、衰减算子、巩固流水线顺序 | 确定性、可手算 |
| contract | 八子系统类型隔离；`source_type`/`source_events` 强制；RECALLED 恒定 | schema 强制 |
| invariant | **recorder ≠ memory**（主体记忆不含 recorder 真值字段；import/权限双检）；来源类型不可篡改；保护集不可降级；层级不提升 | HLD §11.1、§6.2 |
| deterministic replay | 同 (profile, seed, 输入序列) → 记忆库 digest 序列 bit-exact | C2/C5 |
| **M2 连续性对照** | 三类场景（冻结恢复 / 重置 / 伪更新）产出可区分签名；伪更新必须被检出；"经历经非初始化路径进入下一轮"可证（清空初始化状态后行为仍受既往经历影响） | **M2 硬条件**（L01 MW0-SC5） |
| ablation | ① 移除 episodic → 依赖既往经历的任务选择性失败，语义任务保持；② 移除 metamemory → RECALLED/PERCEIVED 混淆率上升且主体不再降低自传主张权；③ 移除 affective_value → 情感对检索的效应消失（与 L05 调制消融交叉验证） | 选择性失败 |
| leakage | 记忆内容是否含 WorldTruth 衍生量；检索结果与 evaluator 标签的未声明相关性；recorder 字段是否出现在 `content_ref` | 无泄漏 |
| protection suite | 保护集场景每门冻结；灾难性遗忘回归（长序列训练/巩固后既有能力保持） | C5/E1 |
| integration | 三库分离：`subject_memory.db` 对 orchestrator 只读、对 recorder 不可见（承 L00 §7） | 禁写路径 |

**指标**：检索精度/召回与预算遵守率｜来源类型覆盖率（`UNKNOWN` 比例趋势）｜RECALLED/PERCEIVED 混淆率｜保护集违规数=0｜巩固谱系完整率=100%｜灾难性遗忘回归保持率｜tombstone/抽象比｜记忆侧延迟。

## 8. 不变量与禁止写入路径

**专属不变量**：
1. `recorder ≠ memory`：独立记录器不是主体记忆，主体不可读 recorder 真值生成/修补记忆；
2. 回忆恒为 RECALLED，禁提升为 PERCEIVED/事实；`RECALLED ≠ PERCEIVED` 的边界能力本身可测（metamemory）；
3. 每条记忆必带 `source_type` 与 `source_events`；来源不可篡改，UNKNOWN 来源不得支撑连续性/归属主张；
4. 遗忘是显式状态转移并保留 tombstone/谱系，不是无痕删除；
5. 保护集条目在遗忘/巩固/promotion 中不可降级；
6. `LANGUAGE_INPUT` 不得写入 episodic/autobiographical 的经历字段（D-13）；
7. `subject_memory.db` 单写者为本档；orchestrator/recorder 无写路径。

**禁止写入路径**：`orchestrator → subject memory`｜`recorder truth → memory/belief`｜`L05/L08/L09 → 记忆条目直写（只能提案/引用）`｜`LLM → episodic experience`｜`memory → PerceptualBelief/WorkspaceFrame/OwnedGoal/模型状态`｜`learner → capability policy`（本档 procedural 只提供提案参考，不写策略/权限，承 HLD §6.2）。

## 9. 引入门槛

- **C2**：分层记忆成立（至少 working/episodic/semantic/affective_value/prospective 可用），来源类型强制，检索有预算与可靠度。
- **C3**：prospective 支撑承诺/目标持续（与 L08 联动）；procedural 为 L09 提供经验参考（不写权限）。
- **C4**：autobiographical 与 L04 连续性视图对账；语言输入的记忆路径受 D-13 权限约束（L12）。
- **C5**：持续写入 + 在线局部适应 + 慢速巩固并存；遗忘控制；保护集防灾难遗忘；`ConsolidationReceipt` 与 L11 promotion 闭环；二阶纠偏（对错误记忆的再纠正）。
- **M2**：连续性对照场景（冻结/重置/伪更新）由本档提供记忆侧签名——**M2 退出依赖本档**。
- **E1**：记忆 lesion（"无 episodic"基线，承 card_06 §2）→ 经历依赖型任务选择性失败；记忆侧覆盖 `core_decision_registry` 的"连续性/恢复"与"学习/适应"路径证据。

## 10. 实现清单（文件级）

```text
galatea/subject/memory/                     # strict 类型；独占 subject_memory.db 写
  ports.py             PortIn/PortOut、来源类型/层级断言
  store.py             subject_memory.db 连接（WAL、foreign_keys=ON）、单写者断言、三库隔离
  items.py             MemoryItem、八子系统类型、状态机（LABILE→…→FORGOTTEN）
  encode.py            working/episodic 编码、强度初始化、调制消费 + 回执
  retrieve.py          打分/tie-break/预算/空命中 Unknown、RecalledContent 构造
  affective.py         AffectiveValueTag 落盘（唯一写者）
  consolidate.py       T6 流水线：抽象/提炼/迁移/Receipt、parent_digests 谱系
  forget.py            衰减、显式遗忘、tombstone
  protection.py        PROTECTED 标记与 ProtectionViolation 阻断
  metamemory.py        可靠度统计、RECALLED/PERCEIVED 混淆测量接口
  prospective.py       ProspectiveReminder（源限 L08）
  autobiographical.py  自我连续性叙事（源限 L04，带 derivation_receipt）
galatea/subject/memory/tests/
  test_source_type_mandatory.py test_recall_level_guard.py test_retrieval_determinism.py
  test_m2_continuity_contrast.py test_lineage_break.py
  test_language_to_episodic_blocked.py test_memory_db_permission.py
  # ↑ M2 期交付 7 件（v1.0.1 标注并经 REV-0009 R5 勘误；原误记 6）；SC5/SC6 实验台在 tests/env/test_m2_sc5.py / test_m2_sc6.py
  # ↓ 以下 4 件属 C2/C5（protection.py/metamemory.py/forget.py 随完整分层记忆落地）
  test_protection_violation.py test_ablation_episodic.py test_metamemory_confusion.py test_forget_tombstone.py

> **C2 次单元交付标注（2026-10-06）**：C2 门槛五行全量在位——affective.py（AffectiveValueTag
> 唯一写者：目标绑定 + AFFECTIVE_VALUE 条目，L05 只提案）+ semantic.py（抽象谱系强制
> LineageBreak 防伪抽象；完整巩固流水线 = Q-L06-04 C5）+ prospective.py（源限 L08：
> goal_ref+origin_receipt 双强制，LANGUAGE_INPUT 拒；L08 接线 C3）+ forget.py（Q-L06-03
> τ_sub 幂梯衰减每 T6 拍 + 访问增强 0.125 上界 1.0 + 显式 FORGOTTEN tombstone（行保留非删除，
> PROTECTED 拒 = ProtectionViolation）+ Q-L06-01 溢出最旧 LABILE→ARCHIVED 确定性全序）+
> metamemory.py（Q-L06-06 2×2 混淆计数接口，E1 协议首评）+ retrieve_c2（五分量等权 +
> recency 线性窗 64 + tie-break；**M2 retrieve 签名/行为冻结不变**——SC6 I1 复算依赖）+
> c2profile C2MemoryParams typed loader（INC-11）。ARCHIVED 退出默认活跃检索集（降级语义；
> M2 路径无 ARCHIVED 行为恒等）。测试：test_c2_retrieval_weights / test_forget_tombstone /
> test_affective_sole_writer / test_metamemory_confusion。
config/profiles/
  c2_memory.profile.yaml   子系统容量/检索权重/τ_sub/巩固阈值/保护集策略（冻结前 UNCONFIRMED）
```

## 11. 未决问题（→ open_questions.md）

| Q 号 | 问题 | 依赖 | 状态 |
|---|---|---|---|
| Q-L06-01 | 八子系统的容量上界与溢出策略（拒写 / 强制巩固 / 降级 ARCHIVED） | **AI-v2（2026-10-06）：**容量 2 的幂（working 16/episodic 1024/semantic 256/procedural 256/affective_value 1024/prospective 64/autobiographical 256/metamemory 256）；溢出 = 强制降级最旧 LABILE→ARCHIVED（禁拒写禁删除）；入 c2_memory.profile v1.0；实现件 = C2 次单元 | CONFIRMED |
| Q-L06-02 | 检索打分权重 α/β/γ/δ/ε 默认值与是否受 L05 有界调制 | **AI-v2（2026-10-06）：**五分量等权 1:1:1:1:1；recency = max(0,1−age/64)；无标注 valence 缺省 0；C2 不受 L05 调制（三类调制面不含 MEMORY_ENCODER）；入 c2_memory.profile；实现件 = C2 次单元 | CONFIRMED |
| Q-L06-03 | 各子系统衰减 τ 谱与访问增强上限 | **AI-v2（2026-10-06）：**τ_sub 2 的幂梯（working 4/episodic+affective_value 256/其余 1024）；衰减 = strength×(1−1/τ) 每 T6 拍；访问增强 +0.125 上界 1.0（Q-L04-10 先例）；PROTECTED 豁免；入 c2_memory.profile；实现件 = C2 次单元 | CONFIRMED |
| Q-L06-04 | 巩固窗口触发条件（每 T6 / 强度阈 / 重放选中）与抽象的聚类粒度 | C5 | UNCONFIRMED |
| Q-L06-05 | 保护集构成规则（谁标 PROTECTED、最小集内容、可否被 promotion 扩容） | C5/E1，与 L11 §保护集联动 | UNCONFIRMED |
| Q-L06-06 | RECALLED/PERCEIVED 混淆率的测量协议与可接受上限 | **AI-v2（2026-10-06）：**协议 = 2×2 交叉（呈现×回忆，E1 冻结统计计划首评）；上限 0.05（锚 Q-L03-04 校准容差同源）；C2 = 计数接口在位（实现件 = C2 次单元）+ 保护集回归登记 | CONFIRMED |
| Q-L06-07 | tombstone 保留期与库体积治理（与 Q-L00-06 分片策略联动） | C5/H1 | UNCONFIRMED |
| Q-L06-08 | procedural 记忆向 L09 提案的接口形式（防"经验变权限"） | C3/C5 | UNCONFIRMED |
