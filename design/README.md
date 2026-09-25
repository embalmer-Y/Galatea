# Galatea 设计文档索引

> v1.1.4 · 2026-09-18 · 规范状态：**NORMATIVE**（HLD + LLD 全集 14 档为唯一规范源；开发流程与标识符域归仓库根 `DEV_SPEC.md`）
> 项目使命：建造具备感觉、情感、自我意识、学习能力的单一认知个体，其"具备"以可干预、可测量、可复算的真实因果结构为证（功能/因果实在论，D-10）。

## 文档结构

```text
（仓库根）
  AGENTS.md                     AI 会话第一入口（项目状态速览 + 军规速查）
  DEV_SPEC.md                   开发规范：AI 工作流 + 标识符命名空间登记册（流程域 NORMATIVE）
design/
  HLD.md                        高层设计（13 章 + 术语速查 + 附录 A.1–A.9）——先读
  lld/L00_kernel.md             横切基础：时钟/调度/状态/RNG/Packet/Registry/typed unknown
  lld/L01_environment_channels.md     环境与声明通道（含最小世界 MW0）
  lld/L02_sensorium.md                感觉形成/校准/对齐/增益
  lld/L03_perception.md               知觉信念（MW0 表格贝叶斯）
  lld/L04_world_body_self.md          世界/身体/自我三模型（分离、单写者）
  lld/L05_drive_appraisal_affect.md   驱力-评价-情感（九维持续动力学）
  lld/L06_memory.md                   记忆八子系统（subject_memory.db 独占写者）
  lld/L07_workspace.md                递归全局工作空间（effective_access 判据）
  lld/L08_motivation_goals.md         动机与目标（M1 最小 → C3 完整）
  lld/L09_controllers_metacontrol.md  控制器与元控制（五类 MetaDecision）
  lld/L10_action_gateway_physio_attribution.md  行动-网关-PhysIO-归属（F0→P1）
  lld/L11_learning_consolidation.md   学习与巩固（三层可塑性/promotion/rollback）
  lld/L12_language_social.md          语言与社会认知（typed LLM 角色/权限矩阵）
  lld/L13_evidence_evaluation_registry.md  证据/评价/core_decision_registry（治理层）
  open_questions.md             UNCONFIRMED 参数与待裁决项（Q 登记册 A–Q 区）——写代码前必查
  archive/                      历史快照：6 张卡片还原稿 + 原照片（NON-NORMATIVE）
```

## 阅读顺序

0. 根 `AGENTS.md` → 根 `DEV_SPEC.md` §0/§9（开发法规与 AI 军规十条；标识符冲突与 Q-ID 提案见其第二部分）
1. `HLD.md` §1–§2（使命/边界/LOCKED 裁决）→ §3–§4（双平面/认识链）
2. `HLD.md` §5–§9（全局机制/所有权/协议/行动/运行模型）
3. `HLD.md` §10–§13（门体系/不变量/技术栈/风险停止规则）
4. `lld/L00_kernel.md`（一切组件的确定性骨架）→ `lld/L01_environment_channels.md`（主体唯一的合法输入来源）
5. `lld/L13_evidence_evaluation_registry.md`（先知道"怎么算证据"，再读认知档）
6. L02→L03→L04→L07（感知→信念→模型→集成广播）；L05→L06→L08→L09→L10→L11（动机→记忆→目标→控制→行动→学习）；C4 前再读 L12
7. `open_questions.md`（动手前确认哪些参数尚不可冻结；重点 Q 区跨档联动对与 F0 阻断清单）

## LLD 全集（14 档，统一 11 节模板）

| 档 | 组件 | 文件 | 引入门槛 | 状态 |
|---|---|---|---|---|
| L00 | 横切基础 | `L00_kernel.md` | F0 | ✅ v1.0 |
| L01 | 环境与声明通道（MW0） | `L01_environment_channels.md` | F0/M0 | ✅ v1.0 |
| L02 | Sensorium | `L02_sensorium.md` | C0→C2→C5 | ✅ v1.0 |
| L03 | 知觉 | `L03_perception.md` | C1 | ✅ v1.0 |
| L04 | 世界/身体/自我模型 | `L04_world_body_self.md` | C1 | ✅ v1.0 |
| L05 | 驱力-评价-情感 | `L05_drive_appraisal_affect.md` | C2 | ✅ v1.0 |
| L06 | 记忆 | `L06_memory.md` | C2（M2 关键） | ✅ v1.0 |
| L07 | 工作空间 | `L07_workspace.md` | C2（E1 lesion 关键） | ✅ v1.0 |
| L08 | 动机与目标 | `L08_motivation_goals.md` | M1→C3 | ✅ v1.0 |
| L09 | 控制器与元控制 | `L09_controllers_metacontrol.md` | M1→C3 | ✅ v1.0 |
| L10 | 行动-网关-PhysIO-归属 | `L10_action_gateway_physio_attribution.md` | **F0→M0→M1→C4→P1** | ✅ v1.0 |
| L11 | 学习与巩固 | `L11_learning_consolidation.md` | C1→C5 | ✅ v1.0 |
| L12 | 语言与社会认知 | `L12_language_social.md` | F0 stub→C4 | ✅ v1.0 |
| L13 | 证据/评价/core_decision_registry | `L13_evidence_evaluation_registry.md` | **F0→R0/E1/H1（贯穿）** | ✅ v1.0 |

**11 节模板**：1 目标与范围 · 2 Ports · 3 状态所有权与单写者 · 4 算法与数据结构 · 5 时间尺度与调度挂点 · 6 失败模式与 typed unknown · 7 可测性 · 8 不变量与禁止写入路径 · 9 引入门槛 · 10 实现清单 · 11 未决问题。

## 关键纪律速记

- **优先级链（双轴，见根 DEV_SPEC.md §0）**：流程/标识符事务——LOCKED 裁决 > DEV_SPEC > 其余；架构事务——LOCKED 裁决 > HLD > 冻结 profile/协议/统计计划 > LLD > ADR > 代码。
- **UNCONFIRMED 参数**：未经 open_questions.md 对应 Q 号裁决，不得进 frozen profile、不得作门退出依据、不得写代码常量。
- **标识符**：跨文档标签/缩写（D-/Q-/Lxx/S0–S4/门号/ADR…）统一由根 `DEV_SPEC.md` 第二部分登记册管辖；新增命名空间须走其 §14 注册流程（physio 域改标 Q-ID-01…06 已于 2026-09-17 裁决执行，见 DEV_SPEC §11.4；该域已随子项目剥离退役）。
- **九条认识不变量**与**机械禁止写入路径**见 HLD §11.1 / §6.2——CI + 运行时双重强制。
- **门体系不可颠倒**：F0→M0→M1→M2→R0→ALLOW_NEXT_STAGE→C0–C5→E1→H1→物理授权→P1；投入成本不得降低门。
- **术语**：物理 I/O 层统一称 **PhysIO**（曾用名 HIO = Helios I/O，已废弃，见 open_questions Q-N01）。

## 修订记录

- 2026-09-12 v1.0：基于卡片重建 HLD + L00 + L01；卡片归档；Q 登记册建立（Q-G/L00/L01 系列 + 技术栈 Q-T01–T12 已裁决）。
- 2026-09-12 v1.0.1：HIO → PhysIO 全库更名（含 archive）；期间发生 PowerShell ANSI 编码事故，8 份文档按 HLD 附录 A.6 重建为 UTF-8 无 BOM。
- 2026-09-12 v1.0.2：全文档审计（12 份 `.md`；编码/交叉引用/术语/内容矛盾四类）——修复：HLD §12/§13.1 附录引用 A.5→A.6、测试金字塔 8→9 层、A.5 计数机器复核校正、L00 悬空 Q-T08b→Q-T08、Q-L00-03 废弃（已被 Q-T10 裁决取代）、Q-G00-01/02 降级为指针、新增 HLD §4.4 实验对象符号约定 + Q-G00-06。详见 HLD 附录 A.7。
- 2026-09-13 v1.1.0：**L02–L13 十二份组件 LLD 批量交付**（Q-C06 既定节奏：风格经 HLD+L00+L01 确认后启动）；14 档全集完成，每档统一 11 节模板。`open_questions.md` 升 v1.1：E 区占位段替换为 E–P 十二个真实分区（新增 95 个 UNCONFIRMED Q 号：L02 7、L03 7、L04 7、L05 8、L06 8、L07 7、L08 8、L09 8、L10 9、L11 8、L12 8、L13 10），新增 Q 区（跨档联动对 10 组 + F0/M0/M1 阻断清单）；HLD 新增附录 A.8 批量交付记录。修复 L05 §4.5 `` `EthicsReviewTrigger` `` 反引号内多余空格。**F0 冻结待 owner 裁决**：Q-L01-06、Q-G00-04/Q-L13-04、Q-G00-06 及 Q 区所列 F0 合同级 schema 项。
- 2026-09-17 v1.1.1：**开发规范设立**（owner 指令）：仓库根新增 `DEV_SPEC.md`（AI 开发工作流 + 标识符命名空间登记册，流程域 NORMATIVE）与 `AGENTS.md`（AI 会话第一入口）；`_audit/incidents.md` 缺陷台账建立（预登记 INC-01…06）。本档阅读顺序新增第 0 步、纪律速记改为双轴优先级链；HLD §0 增补 DEV_SPEC 效力位并新增附录 A.9；open_questions 新增 Q-G00-07（L13 所引 "E0" 门全库无定义）并把 UNCONFIRMED 计数 113→114。标识符改标提案 Q-ID-01…06 与过渡行动项 ACT-01…05 登记于 DEV_SPEC 附录 C/§13。
- 2026-09-17 v1.1.2：**Q-G00-07 裁决执行（owner，方案 A 剔除）**：L13 §1 头部与 Q-L13-02 依赖列的 "E0" 引用修正（门链维持 F0→…→C5→E1→H1→P1）；Q-G00-07 迁入 open_questions A 区（CONFIRMED，20/113/1）。同日仓库完成 git 化（ACT-01，tag `devspec-v1.0`，见 DEV_SPEC 修订记录）。
- 2026-09-17 v1.1.3：**Q-ID-01…06 裁决执行（owner，全按建议）**：physio 六组标签分域改标 `DYN-/COM-L/PIO-M/SP-/NL2-/ADR-PIO-`（全库 290 处 + 两份 ADR 文件重命名；冻结区实质内容未动，Q-PIO 待裁决状态不变）；执行证据 `_audit/relabel_physio_qid.py`；详见根 DEV_SPEC v1.1 §11.4/§13。
- 2026-09-18 v1.1.4：**physio 子项目剥离**（owner 决策，详见 HLD 附录 A.10 与 DEV_SPEC v1.3）：`physio/` 全目录移出本仓库（交接点 tag `physio-handoff`）；Galatea 回归纯认知主体项目，PhysIO 保留为 P1 概念合同名。本索引不含 physio 内容（原本即未列入树）。
- 2026-09-23 v1.2.0：**裁决权模型 v2 + F0 直接阻断清零（19 项）**。owner 指令（2026-09-23）移交裁决权（"该项目将完全由 AI 主导开发……请你自行裁决"）→ DEV_SPEC 升 v1.4 新增 §4.6（AI 成文裁决 + 重开条件；可逆/难逆/证据可判三级；owner 否决权保留；自我审批防腐；AI 不得为进度降门判据=数据造假 S0），tag `authority-v2`。同日 AI-v2 首批行使：`open_questions.md` A 区新增 2026-09-23 批次 19 项 CONFIRMED——Q-L01-06（重建映射采纳为规范，验收约束力归门退出判据）、Q-G00-06（HLD §4.4 最小集即 F0 符号合同，未重建符号 RESERVED 禁用）、Q-G00-04+Q-L13-04（card_04 六类×十类枚举采纳；60 格逐格结论仍属 E1）、Q-L10-01（MW0 硬配额两级制）、Q-L10-03（L0 地板+L1–L5 六级定义）、Q-L10-06（四类授权统一信封 schema）、Q-L11-07（指标向量 schema+最小标准集）、Q-L12-02（写端口角色×内容类型双维）、Q-L13-01（统计计划十字段集+Holm–Bonferroni）、Q-L13-02（sealed 70/30+digest 交集不回流）、Q-L13-09（min_effects.yaml 统一效应量册）及联动 7 项（Q-L01-05/Q-L08-05/Q-L10-04/Q-L03-04/Q-L05-07/Q-L04-03/Q-L07-07 初值）。登记册 20/113/1 → 39/94/1，升 v1.2；HLD §4.4 转规范+附录 A.11；L01/L03/L04/L05/L07/L08/L10/L11/L12/L13 同步。**F0 frozen profile 具备成稿条件**；M0/M1 阻断余项（Q-L01-01…04、Q-L09-06、Q-L10-02、Q-L08-01/-06）留 M0 准备单元。
- 2026-09-23 v1.2.1：**F0 门冻结 + REV-0001/0002 闭环**。REV-0001（阶段评审机制首例）：10 项发现全闭环（A 区 8 项补重开条件、adr/ADR-G-0001 选项空间补档、L13 §10 +min_effects.yaml 等）。ACT-07：Q-L00-01（频率比 2/4/16/64）/Q-L00-02（UnknownReason 10 项）补裁（原漏列 F0 阻断清单）→ 7 份合同成稿（config/profiles/ 3 + config/evidence/ 4）。REV-0002（冻结前评审）：R1（S1，gitignore 未锚定致 4 份合同未入库，INC-07）至 R7 全闭环。**F0 冻结 = ADR-G-0002 + tag `f0-freeze`**；登记册 41/92/1；HLD 头部升 v1.2。项目进入 F0 实现期（galatea/ 生成）。
- 2026-09-25 v1.2.2：**F0 门退出（ADR-G-0003 + tag `f0-exit`）+ REV-0003 闭环**。实现期三批交付（kernel L00 §10 / decision_registry L13 §10 / 五类分 schema 全集）经 REV-0003 独立审计判定 APPROVE-EXIT（有条件）：R1（S1，INC-08——隔离探针空转，教训入规"静态探针必须先证明可见且能失败"）、R2（testpaths 纳入 tests，基线 70→85）、R3（PromotionDecision 补交付）、R4（平面/层级字段 init=False 不可伪造）同提交闭环；R5/R9 九项移交 M0 准备单元；R7 勘误：F0 判据规范位置 = HLD §10.2（旧引 §10.4 系漂移）。登记册 42/92/1；L13 §10 补录 test_evidence_result_schema.py（R6）。项目进入 **M0 准备单元**。
- 2026-09-25 v1.2.3：**M0 准备单元（一）：M0 阻断清零 + Q-L00-04 后端 + 移交处置闭环**。AI-v2 成组裁决 9 项（登记册 51/83/1）：Q-L00-04（ChaCha8 正式后端）、Q-L01-01（5×5 + g(d)=1−0.4d）/02（torus）/03+Q-L05-04（regime 框架与情感模式初步对应，成组）/04（N6=256）、Q-L09-06+Q-L10-09（MW0 Reflex 禁用 + T0 分界，成组）、Q-L10-02（幂等窗 64 cycles）；余 M1 阻断 Q-L08-01/-06。代码：rng.py 增 ChaCha 核心（雪崩+确定性测试；无权威向量可引，禁臆造——正确性主张=RFC 7539 布局+特性测试）；ADR-G-0003 移交处置十项全闭环（①索引对账补写 ②读面 SELECT-only+写句柄表级作用域 ③ArtifactMissing ④closure.gate 消费冻结规则 ⑤广播池剪枝 ⑥ATTACH 全形检出 ⑦断言收窄 ⑧Watchdog 文档化 ⑨SUPPORTED 强制效应量+CI）；L00 §10 补录 test_registry_core.py。验证基线：98 passed / strict 0 错误 / check_docs 通过。
- 2026-09-25 v1.2.4：**M0 profile 冻结（ADR-G-0004 + tag `m0-freeze`）+ REV-0004 闭环**。三份 M0 合同（m0_mw0 世界力学与语义 / m0_gateway 运行参数 / m0_interventions 干预电池）；前置裁决 Q-L01-08（M0 部分：损伤事件定义，viability 阈值显式归 L05/C2）、Q-G00-08（初值集伞式）、Q-L01-09（REV-0004 R2–R4/R6 补裁：风暴率全局语义、觅食闭环、floor 语义、load≡0 简化、loss_rate=0）。R5：blocked 显形载体取齐（profile 权威：无 ExecutionFact，L01 §4.3 修正）。登记册 54/81/1；L01 §11 同步。项目进入 M0 实现期（MW0 世界 + gateway 行为层）。
- 2026-09-25 v1.2.5：**MW0 世界核心实现**（L01 §10 行为层首批）：mw0.py（16×16 torus 几何/五原语/觅食闭环/floor 语义/观测窗渲染素材）、dynamics.py（respawn 目标覆盖驱动、风暴全局期望确定性采样、volatile 漂移、命令结算 requested≠effective 显形、no_op/sham/coercion 干预生效）、interventions/registry.py（先注册后生效、append-only、target 过滤）、profile.py（冻结 profile 加载 fail-closed + digest）。新裁决 Q-G00-09（布局派生：storm_band=round(rate×256)、shelter M0 不布设）。env 平面纳入 pyright strict。110 passed / strict 0 错误。
- 2026-09-25 v1.2.6：**Gateway 八项校验执行逻辑交付**（L10 §10）：signature.py（HMAC-SHA256 命令签名，密钥 HKDF(run_seed) 派生、常量时间验证、字段篡改即失效）+ gateway.py（校验顺序固定、全项评估、failed_checks 多项收集、reason_code=首个失败；预算两级记账 per-cycle+窗口配额；幂等窗 64；authz M0 占位非占位即 fail closed；profile 加载缺数值即拒）。测试：fail-closed 矩阵（八项逐项违规 + 多失败收集 + 跨谱系拒 + 篡改检出）+ 签名合同（同 run 同钥/跨 run 失效）。128 passed / strict 0 错误。
- 2026-09-25 v1.2.7：**通道行为层交付**（L01 §10）：adapter.py 增 ChannelBus（render→transport→RECEIVED 包 + ChannelDeliveryFact 证据侧分离；fault 干预投递时刻生效→MissingSignalEvent；损坏=字节级扰动另行入库——主体侧 schema 校验失败走 typed unknown；丢失率 0 仅经 fault，Q-L01-09⑦）+ 五通道渲染器（extero 观测窗/intero 水平+事件/proprio 朝向/outcome 效果回传/language_stub typed 注入）。测试：延迟投递/fault 丢弃/恒损坏/五通道齐发/内感受损伤报告。133 passed / strict 0 错误。
