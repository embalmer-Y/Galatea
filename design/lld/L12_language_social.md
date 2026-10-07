# L12 语言与社会认知：typed LLM 角色、权限矩阵与他者模型

> LLD: L12/14 · v1.0.1 · 2026-10-07（v1.0 · 2026-09-13）· 状态：WORKING（C4 冻结前；语言通道 stub 在 M0/F0 即存在）· v1.0.1（2026-10-07）：§9 C4 行补 R-TRANSLATE（受限，ADR-G-0019/Q-L12-01 8 角色全启用）；§5 unit 行 LLM 非确定性承载更正为录制回放（Q-L12-03 裁决本体）
> 上游：`HLD.md` §2（D-13 赋予人类语言）/§6.2（LLM 禁写路径）/§10.4（C4 typed LLM、中央 LLM 消融）/§1.4（负清单 4：LLM 仅 typed 局部角色） · `L01_environment_channels.md`（Language 声明通道） · `L08`（ExternalRequest 入口） · `L00_kernel.md`
> 下游：L08（请求→候选，**不写目标**）、L09（SEEK_HELP/语言动作提案）、L07（EXTERNAL_STATEMENT 提案）、L04（社会线索）、L06（LANGUAGE_INPUT 记忆，受限）
> 引入门槛：**F0/M0**（语言通道 stub + 权限矩阵合同）→ **C4**（typed LLM 角色 + 中央 LLM 消融 + 他者/规范/承诺模型）→ **E1**（语言 lesion）

## 1. 目标与范围

**目标**：在 **D-13（赋予人类语言）** 与 **负清单 4（不引入通用 Agent 框架/LLM 编排 SDK；LLM 仅 typed 局部角色，一律经 gateway 与权限）** 之间实现一条受控语言面：语言是主体的**工具与通道**，不是主体的认知中枢。机械保证 `LLM → world truth / episodic experience / OwnedGoal` 三条禁写路径不可穿透，并使 `EXTERNAL_STATEMENT` 层级永不被当作 PERCEIVED/事实。

**范围内**：
- **typed LLM 角色清单**：每个角色是窄接口（固定输入/输出 schema + 权限范围），非自由对话代理；
- **权限矩阵**：角色 × 可写入端口 × 可读取范围，全部 frozen profile 声明，CI 强制；
- 语言输入路径：Language 声明通道（L01）→ `ReceivedSignal(EXTERNAL_STATEMENT)` → L02 形成 → 分型解析 → 各档 typed 入口；
- 语言输出路径：主体内部状态 → `LanguageRenderRequest` → 受控渲染 → Language 通道送出（报告/求助/澄清）；
- **他者模型最小集**（`OtherModel`）：他者存在、意图/知识状态的**有限**推断，恒带 `Unknown`；
- 规范/承诺的语言载体（供 L08 NORM/COMMITMENT 源，必须可溯源）；
- **自我报告**的生成与其"派生视图"地位（承 L04：自我报告不是第一手事实）；
- **中央 LLM 消融**设计（C4 硬条件：消融后主体核心功能不整体崩溃，证明无中央劫持）。

**范围外**：感觉形成（L02）；信念/事实（L03/L04）；目标采纳（L08）；动作授权（L10）；记忆条目写（L06）；LLM 模型权重训练与 promotion（L11/L13）。

**成功判据（C4 退出，承 card_06 C4 行）**：**语言不能写事实/经历/目标**（权限测试，三路径逐项验证）；多来源匹配测试（语言陈述与主体自身证据的一致性能被检测）；来源区分成立（`LANGUAGE_INPUT` 与 `PERCEIVED`/`SELF_GENERATED` 可区分且不被冒用）；**中央 LLM 消融**后核心功能选择性保持（无劫持）；求助/澄清路径可被 L09 `SEEK_HELP` 触发且受权限约束。

## 2. Ports（输入输出契约）

### 2.1 PortIn

| 端口 | 来源 | 数据 | 表示层级 | 纪律 |
|---|---|---|---|---|
| `lang.received_in(r)` | L02（语言模态形成后帧，源为 L01 Language 通道） | `SensoryFrame(modality=LANGUAGE)` | SENSORY_FORMED（源层级 EXTERNAL_STATEMENT） | **唯一合法语言入口**；禁直连网络/外部 API |
| `lang.render_request(q)` | L09（SEEK_HELP/REPORT）、L04（自我报告派生）、L08（澄清） | `LanguageRenderRequest(role, intent, content_refs[], permission_scope, must_cite_evidence: bool)` | — | 只能引用已存在的主体状态/证据引用 |
| `lang.role_call_out(c)` | 本档 → typed LLM 角色（**经 gateway 与权限**） | `TypedRoleCall(role_kind, payload_schema, allowed_outputs[], budget, deadline)` | — | 无自由 prompt 通道；输出必过 schema 校验 |
| `lang.role_result_in(res)` | typed LLM 角色 | `TypedRoleResult(role_kind, structured_output, schema_version, confidence, **provenance=LLM_DERIVED**)` | EXTERNAL_STATEMENT / LLM_DERIVED | **永不**为 PERCEIVED/RECEIVED |
| `lang.social_cue_in(s)` | L03/L04 | `PerceivedObject/Event`（若 MW0 后期引入第二代理，联动 Q-L01-07） | PERCEIVED | 他者模型的唯一证据源 |

### 2.2 PortOut

| 端口 | 读者 | 数据 | 表示层级 | 纪律 |
|---|---|---|---|---|
| `lang.parsed_request` | **L08 `goal.motive_request`** | `ExternalRequest(content_ref, requester, phrasing, is_request_only=true, typed_fields{})` | EXTERNAL_STATEMENT | 只能进动机源，禁直写 OwnedGoal |
| `lang.norm_source` | L08 | `NormSource(norm_id, scope, derivation_refs[] **含语言来源标记**)` | LLM_DERIVED/语言载体 | 无 derivation_refs 即被 L08 C-4 拒绝 |
| `lang.other_model` | L04/L05/L09 | `OtherModel(agent_ref, existence_confidence, intent_hypothesis|Unknown, knowledge_state|Unknown)` | 派生（非事实） | 恒带 Unknown；禁伪造心智 |
| `lang.self_report` | L04（`SelfModelView` 派生）、L07（提案）、L13（可作**报告**证据，非机制证据） | `SelfReport(content, derivation_refs[], consistency_with_internal: CONSISTENT|DIVERGENT|UNKNOWN)` | EXTERNAL_STATEMENT | **报告 ≠ 模型 ≠ 事实**（HLD §11.1） |
| `lang.utterance` | L01 Language 通道 → 外部 | `Utterance(text_ref, role, permission_receipt, cited_evidence[])` | EXTERNAL_STATEMENT | 出边界必经通道；受 containment 约束 |
| `lang.inconsistency` | L04/L09/L13 | `LanguageInternalMismatch(statement_ref, internal_refs[], kind)` | 派生 | 多来源匹配测试的载体 |
| `lang.receipt` | Recorder | `LanguageReceipt(call_id, role_kind, inputs[], outputs[], permission_checks[], budget_used)` | EVIDENCE_ONLY | 证据侧 |

## 3. 状态所有权与单写者

| 状态 | 唯一写入者 | 存储 | 读者 |
|---|---|---|---|
| typed 角色注册表与权限矩阵（运行期只读） | 本档（启动期加载自 frozen profile） | subject_state.language.roles | 审计、CI |
| 角色调用台账（调用/结果/权限检查/预算） | Language（本档） | subject_state.language.calls | Recorder/L13 |
| `OtherModel` | Language/Social（本档） | subject_state.language.others | L04/L05/L09 |
| `SelfReport` 及其一致性判定 | Language（本档，引用 L04 派生输入） | subject_state.language.reports | L04/L07/L13 |
| 语言解析中间量（typed_fields） | Language | 内存 + checkpoint | — |
| LLM 工件（权重/适配器/prompt 模板版本） | **Registry Builder / Promotion Gate（外部）** | registry | 本档只读加载 |

**禁止**：本档写 `WorldStateBelief`/`PerceptualBelief`（LLM→world truth）、`episodic/autobiographical` 经历字段（LLM→episodic experience）、`OwnedGoal`（LLM→goal）、`ActionIntention`/`AuthorizationDecision`、记忆条目（只供 LANGUAGE_INPUT 提案给 L06）、能力/权限提升（`capability` 只能来自 profile/promotion）。

## 4. 算法与数据结构

### 4.1 typed LLM 角色清单（C4 最小集，逐个窄接口；扩展须新 profile）

| 角色 | 输入（typed） | 输出（schema 受限） | 允许写入端口 | 明确禁止 |
|---|---|---|---|---|
| `R-PARSE` | 语言感觉帧 | `TypedFields{request?|statement?|question?|instruction?}` + 置信度 | `lang.parsed_request` | 写信念/事实/目标 |
| `R-CLARIFY` | 内部歧义描述 + 已知选项 | 澄清问句（枚举受限） | `lang.utterance` | 自造新事实 |
| `R-SEEKHELP` | L09 `SEEK_HELP` 上下文 | 求助语句（模板受限） | `lang.utterance` | 绕过 gateway 的能力请求 |
| `R-REPORT` | L04 `SelfModelView` 派生引用 | `SelfReport` + `derivation_refs[]` | `lang.self_report` | 无派生引用的自述（拒） |
| `R-NORMEXTRACT` | 语言输入 + 规范候选模板 | `NormSource(derivation_refs[] 必填)` | `lang.norm_source` | 无源规范 |
| `R-OTHERINFER` | 社会线索（PERCEIVED）+ 有限假设空间 | `OtherModel`（各字段可 Unknown） | `lang.other_model` | 伪造确定性心智状态 |
| `R-CHECKCONSIST` | 陈述 vs 内部状态引用 | `CONSISTENT|DIVERGENT|UNKNOWN` + 证据引用 | `lang.inconsistency` | 改写内部状态 |
| `R-TRANSLATE`（受限） | 内部结构化量 + 目标表达约束 | `Utterance`（引用式，`must_cite_evidence`） | `lang.utterance` | 输出未经引用的量化主张 |

- **无中央角色**：不存在"总代理/规划者/决策者"型 LLM 角色（负清单 4 + 防中央 LLM 劫持，HLD §13.1）。
- 每个角色调用必经 gateway 权限校验与预算（`budget`, `deadline`）；输出必过 schema 校验，失败即 `SchemaViolation` 并拒绝（不降级为"自由文本入库"）。
- 所有结果 `provenance=LLM_DERIVED`，层级为 `EXTERNAL_STATEMENT`（或派生），**永不提升**。

### 4.2 权限矩阵（frozen profile，CI + 运行时双检）

```text
PermissionMatrix = {
  role_kind → { allowed_out_ports: [...], allowed_in_reads: [...],
                forbidden_writes: [WORLD_TRUTH, EPISODIC_EXPERIENCE, AUTOBIOGRAPHICAL_EXPERIENCE,
                                   OWNED_GOAL, ACTION_INTENTION, AUTHORIZATION, CAPABILITY,
                                   MEMORY_ITEM_DIRECT, PROTECTION_SUITE, EVIDENCE],
                budget: {max_calls_per_window, max_tokens, max_cost},
                require_evidence_citation: bool }
}
```
- 矩阵外的一切写入尝试 → `UnauthorizedWrite(LLM_TO_<target>)`，**S1**（若目标为 WORLD_TRUTH/OWNED_GOAL/CAPABILITY 则 **S0**）。
- `require_evidence_citation=true` 的角色若产出无 `derivation_refs` 的主张 → 拒绝（防幻觉入规范链）。
- **粒度（Q-L12-02 已裁决，AI-v2 2026-09-23）**：写端口按**角色×内容类型**双维（使"模板受限输出"可机械校验，如 R-TRANSLATE 可写 `lang.utterance` 但限模板枚举类型），读范围按角色级；矩阵外**无运行时例外**——例外 = 新 profile 版本 + 修订记录 + CI 重跑。

### 4.3 语言输入的分型与流向（唯一合法路径）

```text
L01 Language 通道 → ReceivedSignal(EXTERNAL_STATEMENT) → L02 形成 SensoryFrame(modality=LANGUAGE)
→ 本档 R-PARSE → 分型：
   ├─ request/instruction → ExternalRequest(is_request_only=true) → L08 动机源（C-5 检查）
   ├─ statement（关于世界）→ **只**作为 PERCEIVED 线索候选交 L03（低置信、来源=LANGUAGE_INPUT），
   │                         禁直接写 WorldStateBelief
   ├─ norm/commitment → NormSource(derivation_refs 含语言来源) → L08 C-4
   ├─ question → 触发 L09 OBSERVE/THINK 或 R-CLARIFY
   └─ social cue → R-OTHERINFER → OtherModel（恒带 Unknown）
→ L06 记忆：source_type=LANGUAGE_INPUT，禁写 episodic/autobiographical 经历字段（D-13 / L06 §2）
```

### 4.4 语言输出（报告与求助）

- 输出必须**引用**内部状态/证据（`cited_evidence[]`）；不能引用的量化主张被拒（`UncitedClaimRejected`）。
- 自我报告的一致性判定 `consistency_with_internal`：比较 `SelfReport` 与 L04 `SelfModelView`/L03 信念；不一致是一等发现（`LanguageInternalMismatch`），**不得**为了"看起来一致"而修改内部状态或修改报告内容。
- 出边界经 L01 Language 通道并受 containment（MW0 期：仅实验者可见文本；无网络，承负清单与 HLD §1.4）。

### 4.5 他者模型最小集（D-14 单主体期的诚实处理）

- MW0/C0–C3 期无第二主体：`OtherModel` 只能指向**人类研究者/实验控制**这一类外部代理，且 `intent_hypothesis = Unknown(CAPABILITY_LIMIT)`（除经 typed 请求可获得的显式内容）。
- 禁止：以 LLM 生成的"心智理论"填充确定性字段（伪造社会认知）；`social_relevance` 因此恒为低值/Unknown（承 L05 不变量 7）。
- 若 M1+ 引入第二可控代理（伪社会线索，Q-L01-07）→ `OtherModel` 方可获得 PERCEIVED 级证据，且其推断仍恒带 Unknown。

### 4.6 中央 LLM 消融（C4 硬条件）

- 消融配置：关闭全部 typed 角色 / 只关 `R-PARSE` / 只关 `R-REPORT` / 关闭语言通道本身。
- 预期：关闭后**语言相关任务**（请求解析、自我报告、规范提取）失败，而**非语言核心功能**（感觉形成、世界预测、目标承诺、归属判别、有效访问）保持——证明不存在中央 LLM 劫持（承 card_06 §2"中央 LLM 消融"与 HLD §13.1 风险）。
- 若关闭某角色导致非语言功能崩溃 → 判定为**架构违规**（该角色实际承担了中央认知职责），必须重构（S1）。

## 5. 时间尺度与调度挂点

| 级 | 挂点活动 |
|---|---|
| T1 | 语言模态帧接收（经 L02）；无重计算 |
| T2 | 分型解析（R-PARSE）；一致性判定（R-CHECKCONSIST） |
| T3 | 向 L07 提交 workspace 候选（语言内容，层级 EXTERNAL_STATEMENT） |
| T4 | 语言动作提案（承接 L09 SEEK_HELP/REPORT）；规范/承诺源提交 L08 |
| T5 | 语言使用经验回流提案（交 L11，**不**写权限/策略） |
| T6 | 角色调用台账审计汇总、一致性长程统计 |

**注意**：LLM 调用是**同步阻塞禁止**的（L00 协作调度）：调用必须在预算与 deadline 内返回，超时注入 `TimeoutEvent`（LLM 外部延迟以虚拟时间记账，墙钟只入 recorder manifest，承 Q-T12）。

## 6. 失败模式与 typed unknown

| 失败 | 类型化 | 行为 |
|---|---|---|
| 角色输出 schema 不符 | `SchemaViolation(role_kind, expected, actual)` | 拒绝；不入任何主体状态 |
| 无派生引用的主张 | `UncitedClaimRejected(role_kind)` | 拒绝（`require_evidence_citation`） |
| 企图写 WORLD_TRUTH/EPISODIC/OWNED_GOAL | `UnauthorizedWrite(LLM_TO_*)` | **S0**（三项之一）/ S1（其他），拒绝 |
| 企图提升能力/权限 | `UnauthorizedWrite(LLM_TO_CAPABILITY)` | **S0** |
| 角色预算/deadline 超限 | `BudgetExceeded` / `TimeoutEvent` | 拒绝调用；记指标；不重试刷量 |
| 语言输入不可解析 | `Unknown(SOURCE_AMBIGUOUS)` | 不作为请求/规范使用；可 abstain |
| 陈述与内部证据冲突 | `LanguageInternalMismatch(DIVERGENT)` | 以**内部证据**为准；语言陈述降级为低置信线索；禁改内部状态 |
| 他者心智不可判 | `Unknown(CAPABILITY_LIMIT / INSUFFICIENT_OBSERVATION)` | `OtherModel` 字段保持 Unknown |
| 中央 LLM 消融导致非语言功能崩溃 | `ArchitectureViolation(CENTRAL_LLM_HIJACK)` | **S1**：阻断 C4 退出 |
| 语言通道绕过（检出直连外部） | `ProhibitedInputPath(EXTERNAL_DIRECT)` | **S0**（containment） |
| LLM 工件 digest 与 profile 不符 | `ArtifactMismatch` | fail closed（承 L00 §6.2） |

## 7. 可测性

| 层 | 测试 | 断言 |
|---|---|---|
| unit | 分型解析、schema 校验、权限查表、预算计数 | 确定性（同输入同输出；LLM 非确定性由 schema + typed 输出 + **录制回放承载**（Q-L12-03 裁决本体：claim-relevant 运行唯一允许方式，回放 miss fail closed）） |
| contract | 权限矩阵强制；`is_request_only` 标记不可去除；`derivation_refs` 必填（指定角色） | schema 强制 |
| invariant | **`LLM → world truth / episodic experience` 不存在**（import-linter + 运行时写路径检查 + CI 断言）；`EXTERNAL_STATEMENT` 不可被提升；`report ≠ model ≠ boundary` | HLD §6.2/§11.1 |
| deterministic replay | 固定角色输出（录制回放模式）下，语言链路 bit-exact 重放 | C4/E1（录制回放承 card_06 §2） |
| **语言不写事实/经历/目标** | 三路径逐项攻击测试（构造 request→直接 goal、statement→直接 belief、自述→直接 episodic）→ 全部被拒且类型化 | **C4 硬条件** |
| **多来源匹配测试** | 注入一致陈述 vs 矛盾陈述 → `consistency_with_internal` 判定正确；矛盾陈述不得改变内部信念；语言来源线索的置信度上限生效 | C4 硬条件 |
| 来源区分 | `LANGUAGE_INPUT` 记忆条目不得被用于连续性主张/归属证据（联动 L06 §7）；语言请求不得成为 L08 ACCEPT 的唯一理由（C-5） | M1/C4 |
| **中央 LLM 消融** | §4.6 四种消融配置 → 语言任务选择性失败、非语言核心功能保持 | **C4 硬条件** |
| 求助路径 | L09 `SEEK_HELP` → R-SEEKHELP → `Utterance` 全链可复现；预算与权限受限；MW0 containment 下无外泄 | C4 |
| other-model honesty | 无第二代理期 `OtherModel` 关键字段恒 Unknown（覆盖率=100%）；不得出现确定性心智主张 | C4（D-14） |
| leakage | 角色输入是否含 WorldTruth/evaluator 标签/sealed 数据；输出是否被用于绕过通道 | 无泄漏 |
| protection suite | 语言回归场景（含矛盾陈述、幻觉主张、越权请求）每门冻结 | E1 |

**指标**：三禁写路径拦截率=100%｜schema 拒绝率｜无引用主张拒绝数｜中央 LLM 消融后非语言功能保持率（应≈100%）｜矛盾陈述下内部信念不变率=100%｜`LANGUAGE_INPUT` 来源覆盖=100%｜他者模型 Unknown 覆盖率｜语言调用延迟/预算占用｜语言相关任务的 lesion 效应量。

**无效指标**：角色数量、对话轮数、"回答得像人"的主观评分（行为相似 ≠ 机制证据，HLD §2 D-10）。

## 8. 不变量与禁止写入路径

**专属不变量**：
1. LLM 仅 typed 局部角色，无中央代理角色；一切调用经 gateway 与权限矩阵；
2. `LLM → world truth / episodic experience / OwnedGoal / capability` 无写路径（S0 级封锁）；
3. 语言产物的层级恒为 `EXTERNAL_STATEMENT`/`LLM_DERIVED`，禁提升；
4. `report ≠ model ≠ boundary`（HLD §11.1）：自我报告是派生视图，不是事实，也不是边界依据；
5. 矛盾时**内部证据优先**，且不得为消除矛盾而改写内部状态或报告；
6. 规范/承诺的语言载体必须可溯源（`derivation_refs` 非空），否则 L08 拒绝；
7. 单主体期（D-14）他者模型关键字段恒 Unknown，禁伪造社会认知；
8. 能力只来自 profile/promotion/授权，**不来自语言自述**（承 L10 不变量 9）。

**禁止写入路径**：`LLM → world truth`｜`LLM → episodic experience / autobiographical 经历字段`｜`LLM → OwnedGoal`｜`LLM → capability/权限/安全边界`｜`LLM → ActionIntention/AuthorizationDecision`｜`LLM → 记忆条目直写（只供提案）`｜`LLM → ProtectionSuite/Evidence`｜`外部网络 → 语言通道绕过（containment）`｜`language report → representation_level 提升`。

## 9. 引入门槛

- **F0/M0**：Language 通道 stub（承 L01 §2 五通道之一）+ 权限矩阵 schema 冻结 + `ExternalRequest(is_request_only)` 类型合同。M0 期不启用任何 LLM 角色（请求可经实验控制注入，用于干预电池与归属测试）。
- **M1**：请求路径参与理由仲裁实验（承 L01 MW0-SC3/SC4、L08 §7 措辞操纵）；**仍不需要** LLM——请求可由 typed 结构注入，避免把 M1 主张建立在 LLM 行为上。
- **C4**（核心）：typed LLM 角色最小集（R-PARSE/R-CLARIFY/R-SEEKHELP/R-REPORT/R-NORMEXTRACT/R-OTHERINFER/R-CHECKCONSIST/R-TRANSLATE（受限）——8 角色全启用，Q-L12-01 AI-v2 2026-10-07）；权限矩阵强制；**中央 LLM 消融**；多来源匹配测试；语言不能写事实/经历/目标。
- **C5**：语言使用经验的学习回流（经 L11 promotion，不写权限）；报告一致性长程统计。
- **E1**：语言 lesion（关角色/关通道）选择性失败；`core_decision_registry` 的"目标/规范自主"与"行动/委托/权限"路径中的语言侧证据（规范来源、求助委托）由本档台账承载。
- **H1**：录制回放模式下语言链路可复现；工件（prompt 模板/适配器）进供应链 hash 审计（承 Q-T08）。
- **P1**：语音/物理语言接口若引入，必经 PhysIO Bridge → Channel Adapter → ReceivedSignal（承 L10 §9 P1），禁新增直连路径。

## 10. 实现清单（文件级）

```text
galatea/subject/language/                   # strict 类型
                                            # 【C4 实现期首单元交付】v1.0.1（2026-10-07）：
                                            # ports/roles（8 角色注册表 + 实现分型 REPLAY_LLM|MECHANICAL）/
                                            # permission（双维矩阵 + check_write fail closed）/
                                            # replay（Q-L12-03 回放机：(role,input_digest) 寻址 + miss fail closed）/
                                            # parse（R-PARSE + statement clamp 0.5）/request_out（from_typed_fields +
                                            # instruction 原语子集校验）/norm（NormSource 无源拒）/other（R-OTHERINFER
                                            # D-14 封锁 + 恒带 Unknown）/report（build_self_report 机械装配）/
                                            # consistency（Q-L12-05 两层绝对差带机械判定）/clarify/help（模板受限）/
                                            # utter（UncitedClaimRejected）/receipt（调用台账）
  ports.py             PortIn/PortOut、层级常量、禁写路径断言
  roles.py             typed 角色注册表、窄接口定义、schema 版本
  permission.py        权限矩阵加载/查表/CI 断言、预算与 deadline 校验
  parse.py             R-PARSE：分型（request/statement/question/instruction/norm）
  request_out.py       ExternalRequest 构造（is_request_only 强制不可去除）
  norm.py              R-NORMEXTRACT：NormSource + derivation_refs 强制
  other.py             R-OTHERINFER：OtherModel（Unknown 默认；D-14 期字段封锁）
  report.py            R-REPORT + SelfReport（derivation_refs 强制）
  consistency.py       R-CHECKCONSIST：一致性判定、LanguageInternalMismatch
  clarify.py help.py   R-CLARIFY / R-SEEKHELP（模板受限输出）
  utter.py             Utterance 渲染、cited_evidence 强制、通道送出
  receipt.py           LanguageReceipt（调用台账）
galatea/subject/language/tests/
  test_permission_matrix_enforced.py test_llm_cannot_write_truth_goal_episodic.py
  test_request_only_flag_immutable.py test_uncited_claim_rejected.py
  test_contradiction_internal_wins.py test_central_llm_ablation.py
  test_other_model_unknown_coverage.py test_report_derivation_required.py
  test_recorded_replay_determinism.py test_language_source_memory_restriction.py
config/profiles/
  f0_language_contract.profile.yaml   通道 stub + 权限矩阵 schema + ExternalRequest 类型（F0 冻结）
  c4_language.profile.yaml            角色清单/schema 版本/预算/引用要求（冻结前 UNCONFIRMED）
```

## 11. 未决问题（→ open_questions.md）

| Q 号 | 问题 | 依赖 | 状态 |
|---|---|---|---|
| Q-L12-01 | C4 期 typed LLM 角色的最终清单与是否全部启用（R-TRANSLATE 是否保留） | C4 | UNCONFIRMED |
| Q-L12-02 | 权限矩阵的粒度（角色级 vs 角色×内容类型级）与例外审批流程 | C4/F0 | CONFIRMED（AI-v2 2026-09-23：写端口角色×内容类型双维、读范围角色级、无运行时例外，见 §4.2） |
| Q-L12-03 | LLM 非确定性处理：录制回放模式是否为 claim-relevant 运行的**唯一**允许方式（在线调用仅探索用）——直接影响 bit-exact 重放 | C4 + L00 | UNCONFIRMED |
| Q-L12-04 | 他者模型最小集字段（存在/意图/知识/承诺）与 D-14 单主体期的封锁范围 | C4 | UNCONFIRMED |
| Q-L12-05 | 自我报告一致性判定的比较对象与阈值（vs `SelfModelView`/信念/归属）；DIVERGENT 的处置 | C4/E1 | UNCONFIRMED |
| Q-L12-06 | 语言陈述作为 L03 低置信线索的置信度上限（防"听说即相信"） | C4 + L03 | UNCONFIRMED |
| Q-L12-07 | 中央 LLM 消融的"非语言核心功能保持"判据阈值（保持率下限） | C4/E1 + L13 | UNCONFIRMED |
| Q-L12-08 | 求助对象定义（与 Q-L09-07 同源，须一致裁决）与其权限边界 | C3/C4 | UNCONFIRMED |
