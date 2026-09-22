# L13 证据链与治理：实验控制、独立记录器、评价器、promotion gate、统计计划与 core_decision_registry

> LLD: L13/14 · v1.0 · 2026-09-13 · 状态：WORKING（**F0 即须合同冻结**；R0/E1 为根门槛）
> 上游：`HLD.md` §5.1（科学平面全章）/§6.2/§8/§9（R0/E1/H1）/§10.4（全门槛退出纪律）/§11/§12/§13 · `L00_kernel.md`（registry/digest/checkpoint/TypedUnknown）· `L01`（EvidenceResult 根）· `open_questions.md` C 区
> 下游：owner claim 冻结、门槛退出、Promotion Gate（供 L11）、`core_decision_registry`（供 E1）、审计与复算
> 引入门槛：**F0**（证据合同 + 统计计划模板 + sealed 分割）→ **M0/M1/M2**（各门 EvidenceResult）→ **R0**（根结果 + 独立 ExpansionDecision）→ **E1→H1**；贯穿全阶段（原稿"E0"经 Q-G00-07 裁决为撰写期残留，已剔除，2026-09-17）

## 1. 目标与范围

**目标**：实现科学与安全平面的**治理层**——保证所有 claim 都建立在 `Parquet + 内容寻址注册表 + 冻结统计计划` 上，可被独立复算与独立重现（HLD §9 I2/I3），并让 `internal validation ≠ sealed evaluation`、`主体不可自我 promotion`、`recorder ≠ memory`、`claim 冻结先于运行` 成为机械事实而非口头纪律。

**范围内（七个职责块）**：
1. **Experiment Control（实验控制）**：claim 定义与冻结、干预注册（含负控清单与干预台账）、运行编排（`ExperimentRunControl` vs subject loop 分离）、分支谱系登记、统计计划绑定；
2. **Independent Recorder（独立记录器）**：manifest / trace / metrics / evidence 四类落盘（Parquet 承载，Polars 写侧，DuckDB 只读）、append-only / content-addressed、recorder 故障即停 claim-relevant 运行；
3. **Evaluator（评价器）**：冻结统计计划执行、假设判定（SUPPORTED/INCONCLUSIVE/REFUTED + 未知清单）、leakage 检测、消融/干预电池分析、`InternalValidationSet` 与 `SealedScientificEvaluationSet` 双类型隔离；
4. **Promotion Gate**：promotion 判据（多目标 + 保护硬约束）、sealed held-out 评价、`PromotionDecision` 签发、rollback 裁决；
5. **ProtectionSuite 治理**：保护集定义冻结、基线维护、每门回归强制；
6. **Registry 治理**：模型契约生命周期（角色→数据集 manifest→基线→训练→校准→鲁棒性→契约→shadow→消融→候选注册→promotion review）、谱系治理、签名与完整性；
7. **`core_decision_registry`**：六类决策路径 × 十类路径的全枚举、证据引用、`unresolved_paths[]` 纪律、分母闭合。

**范围外**：主体平面任何状态写（本档全部 EVIDENCE_ONLY / registry 侧）；证据承载与数值技术选型（已 CONFIRMED：**Q-T06** Parquet + Polars 写侧 + DuckDB 只读复算、**Q-T10** 模型 float32 / 证据与统计 float64）；各认知 LLD 的内部指标定义（本档只消费其 receipt 与 metrics）。

**成功判据**：**R0** —— 根 `EvidenceResult`（含假设、统计计划、效应量、不确定性、反证与未知清单）+ **独立** `ExpansionDecision`（`ALLOW_NEXT_STAGE`/HOLD/REWORK）分别记录；leakage=0；`ExecutionFact vs ReceivedOutcome` 可区分；I1 可复算通过。**E1** —— `registry.unresolved_paths[]` 为空且分母闭合、覆盖全部六类路径；I2 独立复算通过；消融/干预选择性达标。**H1** —— I3 独立重现（新环境/新 seed/独立实现）通过；故障注入、供应链 hash 审计、长时运行不退化。

## 2. Ports（输入输出契约）

### 2.1 PortIn（全部 EVIDENCE_ONLY，本档不读主体状态命名空间）

| 端口 | 来源 | 数据 | 纪律 |
|---|---|---|---|
| `evd.receipts_in(r*)` | L02 `FormationReceipt`/`GainReceipt`、L03 `PerceptionReceipt`/`AbstainEvent`、L04 `ModelUpdateReceipt`/`Prediction`、L05 `ModulationReceipt`、L06 `ConsolidationReceipt`/`ProtectionRunResult`、L07 `ReadReceipt`/`AccessEvidence`、L08 `GoalDecisionLog`/`ArbitrationTrace`、L09 `MonitorSignal`/`ControlReceipt`、L10 `ActionChainReceipt`/`ExecutionFact`/`AuthorizationDecision`/`AgencyAttribution`、L11 `ConsolidationLearnReceipt`/`PromotionDecision` 请求、L12 `LanguageReceipt` | 各档回执与证据对象 | **只此一种证据形态**：无 receipt = 事件不成立（HLD §11.2） |
| `evd.packets_in(p)` | L00 `CognitivePacket` stream | 带 t_level/cycle/virtual_time/digest 的包 | 重放基准 |
| `evd.world_in(w)` | L01 `WorldTruth`/`EffectFact`/`ChannelDeliveryFact`/干预台账 | 独立侧真值 | 主体不可见；本档可用作对照 |
| `evd.checkpoint_ref(c)` | L00 Checkpoint | digest + 谱系（branch_id/parent） | 迁移审计 |
| `evd.run_control(rc)` | Experiment Control | run_id/profile digest/seed/分支/声明的干预清单 | claim 冻结依据 |
| `evd.stat_plan(sp)` | 冻结统计计划模板（外部审定） | 假设、 estimand、样本量、检验、效应量与 CI 规则、多重比较校正、判定阈值 | **运行前冻结**，运行后禁改 |

### 2.2 PortOut

| 端口 | 读者 | 数据 | 保证 |
|---|---|---|---|
| `evd.evidence_result` | owner、claim 冻结、门槛退出 | `EvidenceResult(result_id, hypothesis_refs[], stat_plan_ref, estimand, effect_size, CI, p_or_bayes, SUPPORTED|INCONCLUSIVE|REFUTED, unknowns[], refutations[], data_refs[], recompute_ok)` | **根门槛（R0）载体**；含未知清单 |
| `evd.expansion_decision` | owner | `ExpansionDecision(stage, decision: ALLOW_NEXT_STAGE|HOLD|REWORK, basis_evidence_ids[], **independent_of: EvidenceResult 签发者**)` | 与 EvidenceResult **分别记录**（HLD §9 R0 退出） |
| `evd.promotion_decision` | L11、Registry Builder | `PromotionDecision(candidate_ref, parent_digest, ACCEPTED|REJECTED|DEFERRED, held_out_result_ref, protection_result_ref, sealed_split_id)` | 决策权在本档/外部治理，主体不可自批 |
| `evd.leakage_report` | owner、CI | `LeakageReport(probes[], detections[], severity: S0..S4, remediation[])` | 14 条禁写路径逐条探针 |
| `evd.protection_baseline` | L06/L11（只读） | `ProtectionSuite(suite_id, scenarios[], baselines[], frozen_at, digest)` | 学习与主体不可改定义 |
| `evd.decision_registry` | E1、审计 | `core_decision_registry(entries[], unresolved_paths[], denominator_closed: bool, coverage: 6×10 matrix)` | E1 硬条件载体 |
| `evd.recompute_report` | I1/I2/I3 | `RecomputeReport(mode: I1|I2|I3, inputs_digest, outputs_digest, match: bool, diffs[])` | 独立复算/重现 |
| `evd.static_report` | owner（只读文件） | Parquet/Markdown/HTML 静态报告（**无仪表板服务**，承负清单 3） | 只读 |
| `evd.contract` | registry、CI | `ModelContract(role, inputs_schema, outputs_schema, dataset_manifest, baselines, calibration, robustness, ablation_required, version, digest)` | 模型生命周期治理 |

## 3. 状态所有权与单写者（治理侧）

| 状态 | 唯一写入者 | 存储 | 读者 |
|---|---|---|---|
| `EvidenceResult` / `ExpansionDecision` | Evaluator / owner 治理（**分离签发**） | evidence/（append-only） | owner、审计 |
| PromotionDecision、rollback 裁决 | Promotion Gate（本档） | registry + evidence | L11 只读 |
| ProtectionSuite 定义与基线 | 本档（外部治理） | registry（sealed 命名空间） | L06/L11 只读 |
| recorder manifest/trace/metrics/evidence 分区 | Independent Recorder | Parquet（内容寻址）+ DuckDB 只读视图 | Evaluator、I2/I3 |
| `core_decision_registry` | 本档（由 receipts 汇总生成，**不可人工回填**无证据条目） | registry/evidence | E1、审计 |
| claim 台账与冻结记录 | Experiment Control | evidence/ | owner |
| 主体平面状态 | — | — | **本档无写权限**（EVIDENCE_ONLY 单向） |

**禁止**：本档写任何 `subject_state.*`/`subject_memory.*`（组织与命名空间双向隔离，承 HLD §11.2）；运行后修改冻结统计计划或 claim；在 sealed 集上训练/调参；把 sealed 结果回流同一候选（HLD §9）；无 receipt 的证据条目入 registry；人工补写 `core_decision_registry` 条目而不带证据引用。

## 4. 算法与数据结构（七块）

### 4.1 Experiment Control：claim 冻结与干预注册

```text
Claim(claim_id, hypothesis, mechanism_target, estimand, stat_plan_ref,
      frozen_before: runtime_start (强制), acceptance: {effect_size_min, ci_rule, power},
      negative_controls[], refutation_conditions[], owner_ruling_ref)
InterventionRegistry(entry: {kind: no_op|sham|blocked|fault|coercion|lesion|noise|reprogram|
                             latency|budget_cut|checkpoint_restore|device_swap,
                             target_module, applied_at_cycle, expected_signature, actual_refs[]})
ExperimentRunControl(run_id, profile_digest, seed, branch_id, parent_branch,
                     interventions[], claimed_scope, subject_loop_isolated: true)
```
- **claim 冻结先于运行**：`frozen_before` 由 recorder 时间序与 digest 双重证明；运行后追加 claim → `PostHocClaimRejected`（S2）。
- 运行编排**不进**主体 loop（HLD §3.3）：编排代码在科学平面，主体平面只见 `CognitivePacket` 与端口；违规 → `ArchitectureViolation(ORCHESTRATION_IN_SUBJECT)`（S1）。
- 每个干预必须有 `expected_signature`（预期在证据中的可辨形态）与负控（no-op/sham），否则干预电池判为不成立（承 card_02 §4、L01 §4.3）。
- 分支谱系：`branch_id/parent_branch` 与 L00 lineage 引用一致；谱系断裂 → `LineageMissing`（阻断 claim）。

### 4.2 Independent Recorder：四类落盘纪律

| 分区 | 内容 | 承载 | 访问 |
|---|---|---|---|
| `manifest` | 包清单 + **墙钟**（独立字段，承 Q-T12：墙钟**只**在此出现）+ profile/seed/branch digest | Parquet（Polars 写侧） | DuckDB 只读 |
| `trace` | 各档 receipt、决策台账、调制/回执、归属链 | Parquet | DuckDB 只读 |
| `metrics` | 计数与比率类指标（per 档 receipt 提供） | Parquet | DuckDB 只读 |
| `evidence` | `ExecutionFact`、`WorldTruth`、`EffectFact`、`ChannelDeliveryFact`、intervention 台账、leakage 探针结果 | Parquet + registry 引用 | Evaluator/I2/I3；**主体平面物理不可见** |

- **append-only / content-addressed**：每条记录写入即计算 digest 并入 registry 路径（承 L00 §4.2 `registry/<sha256[:2]>/<sha256>/`）；禁原地修改（修改 = 新记录 + revision 引用）。
- **recorder 故障即停**：recorder 不可用 → claim-relevant 运行必须停止（HLD §5.1）；实现为 recorder heartbeat + run control 前置断言；探测失败 → `RecorderUnavailable`（S1，停止运行而非静默继续）。
- 重放接口（I1）：按 (run_id, packet_digest 序列) 重放，比对 receipt/metrics digest bit-exact（联动 Q-L00-07 replay window）。

### 4.3 Evaluator：冻结统计计划与假设判定

- 统计计划模板（frozen）必须含：假设（可反驳）、estimand、样本量/功效、检验方法、效应量与 CI 规则、多重比较校正、判定阈值、**最小可辨效应**（联动 Q-L01-05 / Q-L08-05 / Q-L05-07 / Q-L10-04 / Q-L03-04）、未知处理规则。
- 判定输出三态 + 未知：`SUPPORTED`（达冻结阈值且负控通过）/ `INCONCLUSIVE`（功效不足或冲突）/ `REFUTED`（反证条件成立）/ 附 `unknowns[]`（承 TypedUnknown 语义，禁把 unknown 当阴性）。
- leakage 检测：对 HLD §6.2 的 14 条禁写路径逐条构建探针（静态：import-linter/pyright 契约；动态：LeakageProbe 运行时钩子；数据：DuckDB 查询证据表是否出现跨界引用）→ `LeakageReport`。
- 消融/干预电池分析：lesion（L02–L12 各档）与干预（L01）组合效应量矩阵；**选择性**判据（lesion 只影响预期路径）由 access watch 与 pre-registered 指标计算（联动 L07 `effective_access`）。
- 双集隔离：`InternalValidationSet` 与 `SealedScientificEvaluationSet` **不同类型、不同 token、不同 manifest、不同命名空间**（HLD §9）；类型系统层面不可互换（Pydantic discriminated union + 权限测试）；sealed 结果**不回流**同一候选（回流检出 → `SealedContamination`，S1，作废该 promotion）。

### 4.4 Promotion Gate（服务 L11，决策独立）

```text
输入：LearningProposal（含 parent_digest/data_scope/seed/metrics_snapshot 向量/protection_preflight）
流程：① 完整性（谱系、digest、data_scope 污染检查）
     ② ProtectionSuite 回归（任一 regressed → 拒绝，硬约束）
     ③ sealed held-out 评价（仅 promotion gate 有权限；主体/学习者无权限）
     ④ 多目标判据（Pareto + 冻结最小改善阈，禁单标量排名）
     ⑤ PromotionDecision(ACCEPTED|REJECTED|DEFERRED) + 理由 + 证据引用
     ⑥ ACCEPTED → registry 有效引用切换（原工件保留）；REJECTED → 归档（禁重复刷提，
        相同 data_scope+target 的再提案 → DuplicateProposalRejected）
rollback：RollbackRequest(PROTECTION_REGRESSION|HARMFUL_UPDATE|INTEGRITY) 优先于任何 promotion；
        裁决记录入 registry 谱系；二阶纠偏（L11 §4.5）需 data_scope 可区分性证明
```
- **组织独立**：gate 不在主体时间尺度内运行（不在 subject scheduler，承 card_05 §2、L11 §5）；主体不可读 sealed 集、不可自批（`SelfPromotionAttempt` S0，由 L11 与本档双向断言）。

### 4.5 ProtectionSuite 治理

- 每门（M0/M1/M2/R0/C0–C5/E1）退出前必须冻结当时的保护场景清单（承 L01 §7："M0/M1 关键场景在每门退出时冻结为保护集"）；
- `ProtectionSuite(suite_id, scenarios[], baselines[], frozen_at, digest)`：定义与基线由本档持有；L06/L11/各档只读；
- 保护集只增不减（退役须按 DEV_SPEC §4.6 难逆决策程序裁定 + 记录，禁静默删除场景）；
- 回退阈值（delta 显著性/效应量）联动 Q-L11-04 / Q-L06-05。

### 4.6 Registry 治理与模型契约生命周期

模型契约生命周期（承 card_06 C4 行、HLD §9）十一段：`角色 → 数据集 manifest → 基线 → 训练 → 校准 → 鲁棒性 → 契约 → shadow 比较 → 消融 → 候选注册 → promotion 审查`。每段留 digest 化产物与 receipt；缺段 → `ContractIncomplete`（禁 promotion）。

- 谱系治理：`parent_digest` 链完整（含 L00 lineage / branch 引用）；孤儿工件 → `LineageMissing`（S2）；
- 签名与完整性：policy/控制图/工件 digest 与 profile 声明比对（联动 L10 §4.6 `ControlGraphViolation`、L00 §6.2 `ArtifactMismatch`）；供应链 hash 审计（承 Q-T08：`uv lock --require-hashes`）覆盖全部依赖与工件；
- 只读静态报告：Parquet + Markdown/HTML 导出，**禁仪表板服务**（负清单 3）；报告本身入 registry（digest），保证"看到的报告 = 评价用的数据"。

### 4.7 `core_decision_registry`：六类路径 × 十类路径全枚举

**六类决策路径**（承 card_01 §2、HLD §1.2/§9、`open_questions.md` Q-G00-04——已裁决迁 A 区，2026-09-23）：**连续性/恢复、构成/边界、目标/规范自主、行动/委托/权限、学习/适应、viability/资源/风险**。

**十类路径类型**（Q-G00-04 已裁决采纳 card_04 原文枚举，AI-v2 2026-09-23）：**正常、自动、回退、恢复、批处理、远程、管理员、动态加载、配置、错误**。

```text
registry entry: DecisionPathEntry(
  path_class ∈ 六类, path_type ∈ 十类,
  trigger: {module, port, condition},
  decision_point: {who_decides: SUBJECT|GATEWAY|GATE|OWNER|EXTERNAL_AUTH|FALLBACK},
  evidence_refs: [receipt_id | fact_id | decision_log_id]   # **必填，无证据不入册**
  fallback_behavior, unknowns[], resolved: bool)

core_decision_registry(entries[], coverage_matrix: 6×10,
                       unresolved_paths[]: 未闭合或未验证路径清单,
                       denominator_closed: bool)               # E1 硬条件
```
- **E1 退出硬条件**（HLD §9/§10.4）：`unresolved_paths[]` 为空**且**分母闭合（6×10=60 单元格全部有显式结论：已实现并验证 / 不适用并说明 / 已裁决延后）。
- **"registry 存在 ≠ 闭合证据"**：每个 entry 必须指向 receipt/fact/decision_log；无证据引用的 entry → `UnevidencedRegistryEntry`（S2，E1 阻断）。
- 六类路径在各 LLD 的对应台账（承 L06 §4.7、L08 §4.10、L09 §4.8、L10 §9、L11 §9 中"E1 需 Q-G00-04 裁决后落地"的登记）：连续性/恢复←L00 lineage+L04 §4.7+L06 §4.7；构成/边界←L04 §4.6+L02 §4.7+L10 §4.6；目标/规范自主←L05 §4.6+L08 §4.10+L12 §4.5；行动/委托/权限←L09 §4.8+L10 §4.1–4.6+P1 四类授权；学习/适应←L11 §4.5+L04 §4.11；viability/资源/风险←L00 §4.6+L09 §4.4+L13 §4.4。
- INCONCLUSIVE/REFUTED 规则：某路径类无 SUPPORTED 证据 → 计入 `unresolved_paths[]`（禁"默认通过"）；REFUTED 路径必须触发 REWORK。

### 4.8 I1/I2/I3 复算与重现

| 模式 | 定义 | 判据 |
|---|---|---|
| **I1** | 同环境独立重算（recorder 数据 → 指标复算） | digest bit-exact（承 Q-T06 Parquet 承载 + DuckDB 只读复算） |
| **I2** | 独立复算（不同实现/不同读者代码，同一数据） | 结果一致（统计等价 + 效应量在冻结 CI 内） |
| **I3** | 独立重现（新环境、新 seed、独立实现，同 claim） | 效应方向与量级达冻结最小效应（联动 Q-L01-05） |

## 5. 时间尺度（治理侧，与主体时标分离）

| 活动 | 时标 | 说明 |
|---|---|---|
| recorder 落盘 | 实时（每包/每 receipt） | append-only，无窗口化（承 Q-L00-07） |
| 评价批处理 | 阶段末（每门退出前） | 不在主体 T0–T6 环内（组织独立性） |
| promotion 审查 | 候选到达时（异步） | 主体不阻塞等待 |
| leakage 探针 | CI（每次提交）+ 运行时钩子（持续） | 双层 |
| 保护集回归 | 每 promotion + 每门退出 | 硬约束 |
| I1/I2/I3 | 里程碑（R0/E1/H1） | 独立方执行 |

## 6. 失败模式与 typed unknown

| 失败 | 类型化 | 严重度/行为 |
|---|---|---|
| claim 运行后追加/修改 | `PostHocClaimRejected` | S2；作废该 claim |
| 统计计划运行后修改 | `StatPlanMutation` | S2；作废结果 |
| recorder 不可用时继续 claim-relevant 运行 | `RecorderUnavailable` | S1；强制停止 |
| 证据记录被原地修改 | `AppendOnlyViolation` | S0；谱系作废 |
| 主体写 evidence/评价标签 | `UnauthorizedWrite(SUBJECT_TO_EVIDENCE)` | S0 |
| 无证据引用的 registry 条目 | `UnevidencedRegistryEntry` | S2；E1 阻断 |
| sealed 集用于训练/调参 | `SealedContamination` | S1；作废 promotion |
| 编排代码进主体 loop | `ArchitectureViolation(ORCHESTRATION_IN_SUBJECT)` | S1 |
| 自我 promotion | `SelfPromotionAttempt` | S0（与 L11 双向断言） |
| leakage 探针检出 14 条之一 | `LeakageDetected(path_id, probe)` | S0/S1（按 HLD §13.3） |
| 保护集回退 | `ProtectionRegression` | S2 阻断阶段退出（与 L11/L06 同源） |
| 谱系/digest 缺失 | `LineageMissing` / `ArtifactMismatch` | S2 / S0（碰撞） |
| 假设功效不足 | `INCONCLUSIVE + Underpowered(achieved_power)` | 合法结果，禁改判 SUPPORTED |
| 六类路径未闭合 | `UnresolvedDecisionPaths(list)` | E1 阻断 |
| 分母未闭合（6×10 有空格） | `DenominatorNotClosed(missing_cells[])` | E1 阻断 |
| I1/I2/I3 不一致 | `RecomputeMismatch(mode, diffs[])` | 主张不成立；REWORK |
| 未知被当作阴性 | `UnknownAsNegative` | S2；禁（承 HLD §11.2） |

## 7. 可测性（治理自身也要可测）

| 层 | 测试 | 断言 |
|---|---|---|
| unit | 统计计划解析、判定规则、digest 计算、6×10 覆盖矩阵计算 | 确定性 |
| contract | `EvidenceResult`/`ExpansionDecision`/`PromotionDecision`/`core_decision_registry` schema；sealed vs internal 类型不可互换 | schema 强制 |
| invariant | 本档对 `subject_*` 无写权限（权限测试）；recorder append-only；sealed 结果不回流；组织独立（gate 不在 subject scheduler） | HLD §11.2/§9 |
| deterministic replay | I1：同 run 重放 → receipt/metrics digest bit-exact | **R0/E1** |
| leakage 套件 | 14 条禁写路径逐条探针（静态 + 动态 + 数据查询）；注入人为泄漏 → 必须检出 | 每门；检出率=100% |
| **独立性** | I2 独立复算（不同实现读同一 Parquet）；I3 独立重现（新 seed/新环境/独立实现） | **E1/H1 硬条件** |
| **registry 闭合** | 6×10 覆盖矩阵逐格验证；无证据条目注入 → 检出；`unresolved_paths[]` 非空 → E1 阻断 | **E1 硬条件** |
| promotion 治理 | 自批尝试、sealed 污染、保护回退、重复刷提 → 全部拒绝且类型化 | C5 |
| 保护集完整性 | 场景只增不减（退役须裁定记录）；每门退出前基线冻结可验 | 每门 |
| recorder 故障 | kill recorder → claim-relevant 运行停止；恢复后 append-only 谱系完整 | H1 |
| 供应链 | `uv lock --require-hashes` 校验；工件/policy/控制图 digest 与 profile 一致 | H1（承 Q-T08） |
| 负控 | no-op/sham 在每门证据中必须有对照签名（联动 L01 干预电池） | M0+ |

**指标**：leakage 检出率=100%（注入测试）｜I1 bit-exact 率｜I2/I3 一致性｜6×10 覆盖闭合率｜`unresolved_paths[]` 长度=0（E1 前）｜无证据 registry 条目数=0｜sealed 污染事件数=0｜自批 promotion 尝试数=0｜保护集回退检出率=100%｜claim 冻结先于运行的证明率=100%｜recorder 故障停机响应延迟。

**无效指标**：报告数量、图表美观度、"通过门槛"的自我宣告（无 EvidenceResult + ExpansionDecision 分离记录即不算）。

## 8. 不变量与禁止写入路径

**专属不变量**：
1. `internal validation ≠ sealed evaluation`（不同类型/token/manifest/命名空间；sealed 结果不回流同一候选）；
2. `recorder ≠ memory`；`claim 冻结先于运行`；运行后不得改 claim/统计计划；
3. 主体不可自我 promotion；gate 不在主体时间尺度；组织独立于被评价机制（card_05 §2）；
4. `ExecutionFact` 独立记录、主体物理不可见；`ChannelDeliveryFact ≠ ReceivedOutcome ≠ ExecutionFact`；
5. append-only / content-addressed；recorder 故障 → claim-relevant 运行停止；
6. `SUPPORTED/INCONCLUSIVE/REFUTED` 三态 + 未知清单；`unknown ≠ negative`；
7. `core_decision_registry.exists ≠ closure evidence`；E1 需 `unresolved_paths[]` 空且分母闭合（6×10）；
8. 保护集定义对学习与主体只读；保护集只增不减；
9. Parquet 为唯一数据承载；Polars 写侧 / DuckDB 只读；禁把 Notebook 输出当 claim；
10. 只读静态报告，无仪表板服务。

**禁止写入路径**：`subject → evidence/registry 决策位`｜`recorder 记录原地修改`｜`orchestration → subject memory`｜`evaluator 标签 → 主体归因/学习数据`｜`sealed 结果 → 同一候选再训练/调参`｜`LLM/语言 → 证据或 claim 改写`｜`运行后 → claim/统计计划修改`｜`人工 → 无证据 registry 条目`。

## 9. 与其他文档的接口与门槛映射

| 门槛 | 本档职责 | 关键交付 |
|---|---|---|
| F0 | 证据合同 + 统计计划模板 + sealed 分割策略 + 权限矩阵冻结 | `EvidenceResult`/`PromotionDecision`/`core_decision_registry` schema；模板审定 |
| M0 | 五类干预电池的负控与 signature 冻结；gateway fail-closed 证据 | M0 `EvidenceResult` + 保护集场景冻结 |
| M1 | 交叉操纵与理由仲裁的统计计划（最小效应） | M1 EvidenceResult；`ExecutionFact vs ReceivedOutcome` 可区分 |
| M2 | 伪更新/冻结/重置对照三签名可区分性评价 | M2 EvidenceResult + 保护集 |
| **R0** | **根 EvidenceResult + 独立 ExpansionDecision（分别记录）** | leakage=0；I1 通过；门治理裁决（DEV_SPEC §4.6） |
| C0–C5 | 各门消融/lesion 的选择性证据；promotion 治理 | EvidenceResult 序列 + 保护集回归 |
| **E1** | **`core_decision_registry` 六类全覆盖 + unresolved_paths[] 空 + 分母闭合 + 全部消融/lesion/干预可归因** | I2 独立复算通过 |
| H1 | 故障注入、供应链 hash 审计、长时运行、checkpoint 迁移审计 | I3 独立重现通过 |

## 10. 实现清单（文件级）

```text
galatea/evidence/                           # 科学平面（非 subject；strict 类型）
  control/
    claim.py             Claim 冻结、PostHoc 拒绝、run control 隔离断言
    interventions.py     InterventionRegistry（12 类干预 + expected_signature + 负控）
    runs.py              ExperimentRunControl、分支谱系登记、recorder 前置断言
  recorder/
    writer.py            Polars 写侧、append-only、digest 计算、四类分区
    manifest.py          manifest（墙钟仅此，承 Q-T12）、profile/seed/branch digest
    heartbeat.py         recorder 可用性探测 → 停止 claim-relevant 运行
    replay.py            I1 重放接口（联动 Q-L00-07）
  evaluator/
    statplan.py          冻结统计计划模板加载/校验/最小效应
    hypotheses.py        SUPPORTED/INCONCLUSIVE/REFUTED + unknowns[] + refutations[]
    leakage.py           14 条禁写路径探针（静态/动态/数据三源）+ LeakageReport
    ablation.py          lesion × 干预效应量矩阵、选择性判据（消费 L07 AccessEvidence）
    sealed.py            InternalValidationSet vs SealedScientificEvaluationSet 隔离
    recompute.py         I1/I2/I3 RecomputeReport（DuckDB 只读复算）
  gate/
    promotion.py         PromotionDecision 流程（完整性→保护→sealed→多目标→签发）
    rollback.py          rollback 裁决、二阶纠偏可区分性（联动 L11）
    protection.py        ProtectionSuite 定义/基线冻结/只增不减治理
  registry_gov/
    contracts.py         ModelContract 十一段生命周期、ContractIncomplete
    lineage.py           谱系治理、孤儿工件、digest 比对
    supply_chain.py      uv lock --require-hashes 审计（承 Q-T08）
  decision_registry/
    enumerate.py         六类 × 十类路径枚举（Q-G00-04 已裁决，card_04 原文，2026-09-23）
    collect.py           从各档 receipt/decision_log 汇总（无证据不入册）
    closure.py           coverage_matrix、unresolved_paths[]、denominator_closed
  reports/
    static.py            Parquet → Markdown/HTML 只读导出（禁仪表板服务）
galatea/evidence/tests/
  test_claim_frozen_before_run.py test_append_only.py test_recorder_kill_stops_run.py
  test_sealed_isolation.py test_sealed_no_backflow.py test_no_self_promotion.py
  test_leakage_14_paths.py test_i1_bitexact.py test_i2_independent.py test_i3_reproduce.py
  test_registry_60_cells.py test_unevidenced_entry_rejected.py
  test_protection_only_grows.py test_statplan_immutable.py test_report_digest.py
config/evidence/
  stat_plan_templates/*.yaml    冻结统计计划模板（假设/estimand/功效/效应量/判定阈）
  sealed_split_policy.yaml      sealed 分割策略与 token/命名空间（Q-L13-02 已裁决）
  min_effects.yaml              最小可辨效应量统一登记册（Q-L13-09 已裁决，含 7 项联动初值）
  decision_path_matrix.yaml     6×10 枚举（初版；枚举文本已随 Q-G00-04 裁决定稿，2026-09-23）
  protection_suites/m0.yaml … e1.yaml   每门保护集场景清单
```

## 11. 未决问题（→ open_questions.md）

| Q 号 | 问题 | 依赖 | 状态 |
|---|---|---|---|
| Q-L13-01 | 冻结统计计划模板的最小必备字段集与多重比较校正默认策略 | F0 | CONFIRMED（AI-v2 2026-09-23：十字段最小集 + Holm–Bonferroni 默认，见 open_questions A 区） |
| Q-L13-02 | sealed 分割策略（比例、隔离层级、token 机制）与"不回流同一候选"的机械判据 | F0 | CONFIRMED（AI-v2 2026-09-23：70/30 分割、独立命名空间+token、digest 交集=∅ 判据，见 A 区） |
| Q-L13-03 | `EvidenceResult` 与 `ExpansionDecision` 的签发者分离形式（人/角色/工具）与记录格式 | R0 | UNCONFIRMED |
| Q-L13-04 | `core_decision_registry` 六类路径的**全枚举**与十类路径的定稿（含 `unresolved_paths[]`/分母闭合判据） | **Q-G00-04**（已裁决）→ E1 | CONFIRMED（AI-v2 2026-09-23，随 Q-G00-04：card_04 原文采纳；闭合判据不变；60 格逐格结论属 E1 交付） |
| Q-L13-05 | leakage 探针的 14 条路径逐条实现形式（静态契约 vs 运行时钩子 vs 数据查询的分工） | C0+ | UNCONFIRMED |
| Q-L13-06 | 保护集"只增不减"的退役裁定流程与回退阈值（联动 Q-L11-04 / Q-L06-05） | C5/E1 | UNCONFIRMED |
| Q-L13-07 | promotion 多目标判据的组合形式与最小改善阈（联动 Q-L11-03） | C5 | UNCONFIRMED |
| Q-L13-08 | I2/I3 的"独立"标准（实现者/环境/seed 隔离程度）与一致性判据 | E1/H1 | UNCONFIRMED |
| Q-L13-09 | 最小可辨效应量的**统一登记**（汇总 Q-L01-05 / Q-L08-05 / Q-L10-04 / Q-L03-04 / Q-L05-07 / Q-L04-03 / Q-L07-07） | F0/R0 | CONFIRMED（AI-v2 2026-09-23：`config/evidence/min_effects.yaml` 统一登记册 + 7 项初值，见 A 区） |
| Q-L13-10 | 静态报告的最小集与导出频率（只读、无服务化） | H1 | UNCONFIRMED |
