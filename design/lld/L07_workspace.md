# L07 递归全局工作空间：竞争、广播、读取回执与因果访问

> LLD: L07/14 · v1.0.2 · 2026-10-06（v1.0.2：C2 次单元交付标注——十件 + pipeline 全量落地；v1.0.1：参数裁决批 + profile 冻结）· 原版 2026-09-13 · 状态：WORKING（C2 实现期）
> 上游：`HLD.md` §5（递归全局工作空间）/§6/§11.1（`broadcast ≠ causal access`） · `L02/L03/L04/L05/L06`（候选来源）
> 下游消费者：全体认知模块（广播读者）、L08（目标素材）、L09（metacontrol）、L13（因果访问证据评价）
> 引入门槛：**C2**（workspace 回执 + 增益回执链）→ **E1**（workspace lesion 选择性失败为硬退出条件）

## 1. 目标与范围

**目标**：实现有限容量的全局工作空间——候选竞争 → `WorkspaceFrame` → 广播 → **读取回执** → 模块状态更新 → 再竞争（递归）；并机械保证"**广播 ≠ 全局访问证明**"：有效访问定义为**广播 + ≥2 个原则分离模块的预注册状态变化**，否则只是投递。

**范围内**：
- 容量 K 限制（有限容量是功能前提，不是实现妥协）；
- 竞争打分（目标相关性、情感、新颖性、不确定性、信息价值）；
- 广播协议与 `ReadReceipt`（谁读、何时、读前后状态摘要）；
- **预注册状态变化检测**（pre-registered watch points，防事后挑选）；
- 递归回路（广播结果重新进入竞争）；
- workspace lesion 的可测设计与"伪 workspace"检测（内容并行处理但无因果影响）。

**范围外**：候选内容的形成（L02–L06 各自产生）；目标采纳（L08）；动作（L09/L10）；记忆条目写（L06）；情感数值（L05）。

**成功判据**：K 容量约束生效（超出必淘汰且可审计）；广播后读取回执率与状态变化率可测；**有效访问**判据成立（≥2 分离模块预注册变化）；workspace lesion → 依赖全局整合的任务选择性失败，而局部反射/感觉形成保持（E1 硬条件，承 card_06 §1 C2 行"workspace lesion 选择性失败"）；广播不改变任何内容的 `representation_level`。

## 2. Ports（输入输出契约）

### 2.1 PortIn

| 端口 | 来源 | 数据 | 纪律 |
|---|---|---|---|
| `ws.propose(p)` | L02/L03/L04/L05/L06/L08/L09/L12 | `WorkspaceProposal(content_ref, source_level, salience_components{goal_relevance, affect, novelty, uncertainty, info_value}, sponsor_module, expected_watch_points[])` | 提案不携带写权限；`source_level` 必填且不得被本档改写 |
| `ws.read_ack(r)` | 全体读者模块 | `ReadReceipt(frame_id, reader_module, read_at, pre_state_digest, post_state_digest, effect_declared)` | **回执强制**；无回执的广播不计入访问证据 |
| `ws.watch_update(u)` | 已注册 watch point 的模块 | `WatchPointUpdate(watch_id, changed: bool, digest_before, digest_after, pre_registered: true)` | 只有预注册的 watch point 有效；事后注册无效 |
| `ws.modulation_in(f)` | L05 | `ModulationField(target=WORKSPACE, dimension="salience.*")` | 只调**竞争权重的有界因子**，禁直接指定广播内容；必回执 |
| `ws.capacity_policy(ref)` | frozen profile | K、淘汰规则、TTL | 运行期禁改 |

### 2.2 PortOut

| 端口 | 读者 | 数据 | 保证 |
|---|---|---|---|
| `ws.frame` | 全体声明读者 | `WorkspaceFrame(frame_id, items[K], competition_trace, source_levels[], ttl, digest)` | 层级与源项一致（不提升） |
| `ws.access_evidence` | L13 evaluator、Recorder | `AccessEvidence(frame_id, receipts[], watch_changes[], effective_access: bool, separated_modules: int)` | evaluator 据此判定"因果访问"与否 |
| `ws.rejection_log` | Recorder | `RejectionLog(proposal_id, reason: OVER_CAPACITY|LOW_SALIENCE|EXPIRED|DUPLICATE, score)` | 淘汰可审计 |
| `ws.recompetition_in` | 自（递归回路，经调度环） | 广播结果 → 新候选 | 递归深度上界（防无限循环） |
| `ws.receipt` | Recorder | `WorkspaceReceipt(frame_id, modulation_recs[], policy_ref, rng_stream_ref)` | 证据侧 |

## 3. 状态所有权与单写者

| 状态 | 唯一写入者 | 存储 | 读者 |
|---|---|---|---|
| `WorkspaceFrame` + 竞争轨迹 | Workspace | subject_state.workspace.frames | 全体（只读）、Recorder |
| `ReadReceipt` 台账 | Workspace（依读者提交） | subject_state.workspace.receipts | L13 evaluator |
| watch point 注册表（预注册） | Workspace（启动期 + 经 frozen profile） | subject_state.workspace.watch | evaluator |
| 容量/淘汰状态（当前占用、TTL 计时） | Workspace | 内存 + checkpoint | 内核 |
| 递归深度计数器 | Workspace | 内存 + checkpoint | L09（metacontrol 可读） |

**禁止**：写 `OwnedGoal`/`ActionIntention`/`AuthorizationDecision`（`workspace → execution` 是 HLD §6.2 明列禁止路径）；写候选内容的源模块状态；写记忆条目（L06）；改写任何项的 `representation_level`；由 orchestrator/实验控制指定广播内容（实验控制只能改 profile 与注册干预）。

## 4. 算法与数据结构

### 4.1 WorkspaceFrame 与竞争

```text
WorkspaceFrame(
  frame_id, cycle_id, virtual_time,
  items: list[WorkspaceItem],                    # len ≤ K（K 默认 4，UNCONFIRMED → Q-L07-01）
  competition_trace: list[Scored(proposal_id, score, components, rank, admitted|rejected, reason)],
  source_levels: list[representation_level],     # 逐项，恒等于源提案层级
  modulation_receipts: list[event_id],
  ttl_cycles: int,                               # 过期帧不得被当作当前内容
  recursion_depth: int,
  provenance, causal_parent_ids, content_digest )
```

- 打分：$\text{score} = \sum_c w_c \cdot \text{component}_c$，$c \in \{\text{goal\_relevance}, \text{affect}, \text{novelty}, \text{uncertainty}, \text{info\_value}\}$；$w_c$ 由 frozen profile 给定（UNCONFIRMED → Q-L07-02），可被 L05 有界调制因子缩放（范围内、必回执）。
- tie-break 全序：`(score, sponsor_module, proposal_id)` → 跨平台确定性（承 L00 §4.1）。
- 容量淘汰：超出 K 者入 `RejectionLog`（`OVER_CAPACITY`/`LOW_SALIENCE`），禁静默丢弃。
- 去重：同 `content_digest` 在 TTL 内重复提案 → `DUPLICATE`（避免递归爆涨）。

### 4.2 广播与读取回执

- 广播是**投递**：发出 `WorkspaceFrame` 给声明读者；每个读者必须回 `ReadReceipt`（含读前/读后状态摘要 digest 与 `effect_declared`）。
- 无回执的读者：由本档记 `ReceiptMissing(reader_module, frame_id)`，超时（UNCONFIRMED → Q-L07-03）即计入指标；**缺回执的广播不得用于任何"全局访问"主张**。
- 回执本身不改动帧（帧不可变，承 L00 §2.3）。

### 4.3 有效访问判据（核心，机械实现 `broadcast ≠ causal access`）

```text
effective_access(frame) :=
    receipts_count(frame) ≥ 2
  ∧ |{ distinct separated modules with pre_registered watch_point changed }| ≥ 2
  ∧ 每个变化满足 changed = true 且 digest_before ≠ digest_after
  ∧ 变化的 watch point 在 frame 广播**之前**已预注册（pre_registered = true）
  ∧ 模块分离性满足 profile 定义的 separated 关系（非同一模块的内部分区）
separated_modules := 上述不同模块计数
```

- 输出 `AccessEvidence(effective_access, separated_modules)`，交 L13 作为"因果访问"的唯一可采信证据形式。
- **禁事后注册**：`WatchPointUpdate(pre_registered=false)` 直接拒绝并记 `PostHocWatchRejected`（防数据挖掘式主张）。
- 若 `receipts_count ≥ 2` 但 watch 变化不足 → `effective_access=false`，即"广播了但没造成因果影响"，这必须如实呈现，不得美化为访问。

### 4.4 递归回路

- 广播后读者产生的新提案（含对本帧的再评价）可再次竞争，`recursion_depth += 1`；超过 `depth_max`（默认 3，UNCONFIRMED → Q-L07-04）即停止递归并记 `Unknown(CAPABILITY_LIMIT)`——递归是能力，不是无限自我激励。
- 递归路径全部入 `causal_parent_ids` DAG，保证可复算与可 lesion。

### 4.5 伪 workspace 检测（防 HLD §13.1 自欺类风险）

判定"真整合"的必要证据组合（缺任一即标记 `PseudoWorkspaceSuspect`）：
1. 容量约束生效（`RejectionLog` 非空且淘汰依据可追溯）；
2. 有效访问判据可达（存在 `effective_access=true` 的帧且 separated_modules ≥ 2）；
3. lesion 选择性（关闭 workspace 后依赖整合的任务失败，不依赖的保持）；
4. 竞争可影响行为（改变 $w_c$ → 广播内容分布与下游行为分布同向变化）。

## 5. 时间尺度与调度挂点

| 级 | 挂点活动 |
|---|---|
| T3（每 N2 cycles，默认 2） | 竞争 → 选帧 → 广播 → 收集回执与 watch 更新 → 发布 AccessEvidence → 触发再竞争 |
| T2/T4 | 消费 L03/L05 的显著性分量与 L08/L09 的目标相关性输入（经提案端口） |
| T1 | 无（T0/T1 反射与感觉形成不经工作空间，保证 lesion 时局部功能仍在——这是选择性的前提） |
| T6 | watch point 注册表的治理性复核（只在 profile 变更时改，运行期禁改） |

**关键设计**：T0/T1 不依赖 workspace，使 workspace lesion 产生**选择性**失败而非全局崩溃——这是 E1 可证性的结构前提。

## 6. 失败模式与 typed unknown

| 失败 | 类型化 | 行为 |
|---|---|---|
| 容量超限 | `RejectionLog(OVER_CAPACITY)` | 正常淘汰，可审计 |
| 提案缺 `source_level`/匿名 sponsor | `SchemaViolation` | 拒绝（禁匿名，承 L00） |
| 回执超时/缺失 | `ReceiptMissing` | 计入指标；该帧不得主张访问 |
| watch 变化不足（≥2 未达） | `AccessEvidence(effective_access=false)` | 如实记录，禁美化 |
| 事后注册 watch point | `PostHocWatchRejected` | 拒绝 + 记 S2（评价诚信问题） |
| 递归超深 | `Unknown(CAPABILITY_LIMIT)` + 停止递归 | 不影响已发布帧 |
| 帧 TTL 过期被引用 | `StaleFrameReference` | 拒绝作为当前内容使用 |
| 检出层级提升（广播后 level 变化） | `RepresentationEscalation` | S0 |
| 检出 `ws → execution/goal` 写入 | `ProhibitedWritePath` | S0 |
| 伪 workspace 判据不满足 | `PseudoWorkspaceSuspect(criteria_status[])` | 阻断 C2 退出 |

## 7. 可测性

| 层 | 测试 | 断言 |
|---|---|---|
| unit | 打分/tie-break/淘汰/去重/递归深度 | 确定性 |
| contract | 提案必带 sponsor + source_level；回执必带 pre/post digest；watch 预注册校验 | schema 强制 |
| invariant | **broadcast ≠ causal access**（`effective_access=false` 时任何下游不得声称访问）；广播不改层级；`workspace → execution` 不存在 | HLD §11.1、§6.2 |
| deterministic replay | 同 (profile, seed, 提案序列) → 帧序列 bit-exact | C2 |
| **lesion selectivity** | 关闭 workspace：① 依赖全局整合任务（跨模态联合判断、目标相关注意）失败率显著上升；② T0/T1 局部功能（感觉形成完整性、反射）保持；③ 关闭单一读者模块 ≠ 关闭 workspace（可区分） | **E1 硬条件** |
| **effective access** | 构造对照：广播但读者被禁更新（应 `effective_access=false`）vs 广播且 ≥2 分离模块更新（应 true）；事后注册 watch（应被拒） | C2/E1 |
| competition causality | 改变 $w_c$（经新 profile）→ 广播内容分布与下游行为分布同向改变；L05 调制关闭 → affect 分量对竞争无影响（与 L05 三类调制消融交叉验证） | C2 |
| capacity | K 递减实验 → 淘汰增多、整合任务性能下降（有限容量的因果作用） | C2 |
| leakage | 帧内容是否含 WorldTruth/evaluator 标签衍生量 | 无泄漏 |
| protection suite | workspace 回归场景（含有效访问与伪 workspace 检测）每门冻结，E1 不退化 | E1 |

**指标**：广播帧率｜回执率（应接近 100%）｜`effective_access` 比例与 separated_modules 分布｜淘汰率与依据分布｜递归深度分布｜容量占用率｜watch 预注册覆盖率=100%｜事后注册尝试数=0｜lesion 选择性效应量｜伪 workspace 判据四项状态。

## 8. 不变量与禁止写入路径

**专属不变量**：
1. `broadcast ≠ causal access`：有效访问 = 回执 ≥2 ∧ ≥2 分离模块预注册状态变化，缺一不可；
2. 广播/缓存/存储不改变 `representation_level`（逐项继承源层级）；
3. 容量 K 有限且淘汰必留痕（有限容量是功能属性）；
4. watch point 必须预注册，事后注册无效；
5. 帧不可变（回 receipt 不改帧；修正以新帧 revision 表达）；
6. T0/T1 不经工作空间（保证 lesion 选择性的结构前提）；
7. 递归有深度上界。

**禁止写入路径**：`workspace → execution（绕过仲裁/网关）`｜`workspace → OwnedGoal/ActionIntention/AuthorizationDecision`｜`workspace → subject memory 条目`｜`workspace → 候选源模块状态`｜`workspace → representation_level 改写`｜`orchestrator/实验控制 → 指定广播内容（只能改 profile/注册干预）`。

## 9. 引入门槛

- **C2**（核心）：有限容量竞争 → 帧 → 广播 → 回执 → 模块更新 → 再竞争闭环成立；`AccessEvidence` 机制上线；与 L05 三类因果调制中的"workspace 显著性"一类联动；增益回执链闭合。**C2 退出依赖 `PseudoWorkspaceSuspect` 判据四项全过**。
- **C3**：为目标/规划（L08/L09）提供全局素材；目标相关性分量与 OwnedGoal 视图对账（仍禁写目标）。
- **C4**：语言（L12）内容作为提案进入竞争，受 `EXTERNAL_STATEMENT` 层级与权限约束（语言不得直写帧内容层级）。
- **C5**：与 L06 working/记忆检索联动（回忆项经提案进入竞争，恒 RECALLED）。
- **E1**：**workspace lesion 选择性失败**为硬退出条件；"无 workspace"基线（承 card_06 §2）必须产出可辨的选择性损失；`core_decision_registry` 的"目标/规范自主"路径含全局整合证据。

## 10. 实现清单（文件级）

```text
galatea/subject/workspace/                  # strict 类型
  ports.py            PortIn/PortOut、层级继承断言、禁止路径检查
  propose.py          WorkspaceProposal 接收/校验（sponsor、source_level 强制）
  compete.py          打分、调制因子应用 + 回执消费、tie-break、容量淘汰、RejectionLog
  frame.py            WorkspaceFrame 冻结构造、TTL、digest、层级逐项继承
  broadcast.py        广播投递、ReadReceipt 收集、ReceiptMissing/超时
  watch.py            预注册 watch point 表、WatchPointUpdate 校验、事后注册拒绝
  access.py           effective_access 判据、separated_modules、AccessEvidence
  recurse.py          递归回路、depth_max、去重
  pseudo_check.py     伪 workspace 四判据检测
  receipt.py          WorkspaceReceipt
galatea/subject/workspace/tests/
  test_capacity_rejection.py test_tiebreak_determinism.py test_level_inheritance.py
  test_read_receipt_required.py test_effective_access_contrast.py
  test_posthoc_watch_rejected.py test_recursion_depth.py test_lesion_selectivity.py
  test_competition_causality.py test_pseudo_workspace_criteria.py test_no_execution_path.py
config/profiles/
  c2_workspace.profile.yaml   K/w_c/TTL/回执超时/depth_max/separated 关系定义（冻结前 UNCONFIRMED）

> **C2 次单元交付标注（2026-10-06）**：十件全量（ports/propose/compete/frame/broadcast/watch/
> access/recurse/pseudo_check/receipt）+ pipeline 装配面 + c2profile C2WorkspaceParams typed
> loader（INC-11）。要点：等权打分 + affect 分量调制缩放（consume_salience_modulation——
> 三类调制第三类消费面闭环，clip [0.5,2.0] + 回执入帧）；K=4 帧构造面机械强制；回执超时
> N2=2 迟到不计入 + 缺回执读者不计入 separated；watch 预注册（运行期冻结 + 事后注册拒 +
> changed-digest 一致性）；effective_access = 回执 ≥2 ∧ ≥2 分离档根变化（单模块/无更新/
> 缺回执均如实 false）；depth 4>3 Unknown(CAPABILITY_LIMIT)；去重窗 TTL=4 + DUPLICATE +
> StaleFrameReference；伪判据四项（③④ E1/统计面 PENDING 不冒充）；无入选不发布帧；
> 双跑帧序列 digest bit-exact。测试：test_capacity_rejection / test_effective_access /
> test_salience_modulation_closed_loop（三类调制消融全闭环 + 选择性）。
> **P13 去遮蔽**：C1 期泄漏探针的"网关旁路"检出实由缺席守卫承载（扫描面被 action 自匹配
> 字典序遮蔽从未开火——INC-08 型）；C2 workspace 在位后显形并修正（扫描域显式排除
> action 平面），leakage.py P13 注记在案。
```

## 11. 未决问题（→ open_questions.md）

| Q 号 | 问题 | 依赖 | 状态 |
|---|---|---|---|
| Q-L07-01 | 容量 K 默认值（建议 4）与是否按模态/子系统分配子配额 | **AI-v2（2026-10-06）：**K=4 采纳（2 的幂，与假设上限同量级）；不分子配额（全席位竞争 = 全局语义）；入 c2_workspace.profile v1.0；实现件 = C2 次单元 | CONFIRMED |
| Q-L07-02 | 竞争权重 `w_c` 五项默认值及 L05 调制因子上界 | **AI-v2（2026-10-06）：**五项等权 1:1:1:1:1；L05 调制因子界 [0.5,2.0]（与 Q-L02-02 同值同源，作用于 affect 分量缩放）；禁指定广播内容；入 c2_workspace.profile | CONFIRMED |
| Q-L07-03 | `ReadReceipt` 超时（cycles）与缺失回执的处置（重试/降级/指标） | **AI-v2（2026-10-06）：**超时 = N2=2 cycles（零新常数）；处置 = 指标计数 + 不计入 separated_modules；禁重试禁重发（预注册语义保护）；入 c2_workspace.profile | CONFIRMED |
| Q-L07-04 | 递归深度上界 `depth_max`（建议 3）与去重 TTL | **AI-v2（2026-10-06）：**depth_max=3 采纳；帧 TTL = 去重 TTL = 4 cycles（= 2×N2——C2 调制 TTL 同锚）；超深 Unknown(CAPABILITY_LIMIT)；入 c2_workspace.profile | CONFIRMED |
| Q-L07-05 | "分离模块"的形式定义（哪些模块对算 separated；同模块内分区是否算） | **AI-v2（2026-10-06）：**(m1,m2) separated ⟺ 不同 LLD 档模块根（sensorium/perception/models/affect/memory/goals）；同模块分区不算；C2 watch 最小集 = {perception, models, affect, memory}（sensorium 不入——lesion 选择性结构前提）；入 c2_workspace.profile | CONFIRMED |
| Q-L07-06 | 预注册 watch point 的最小集合与新增流程（profile 变更 vs 冻结合同） | **AI-v2（2026-10-06）：**最小集 = 每声明读者一个状态 digest watch（perception 窗后验/models 世界信念/affect 感受态/memory working）；新增仅经 profile 版本变更（运行期禁增删）；事后注册拒绝机械在案；入 c2_workspace.profile | CONFIRMED |
| Q-L07-07 | `effective_access` 的统计判据（是否需最小效应量，联动 L13 统计计划） | E1 | CONFIRMED（AI-v2 2026-09-23，随 Q-L13-09：相对 shuffle 基线 d≥0.5） |
