# AGENTS.md — Galatea AI 开发入口

> 本文件是任何 AI 会话在本仓库工作的**第一必读文件**。
> 流程法规：根 `DEV_SPEC.md`（NORMATIVE）。架构规范：`design/`（HLD + 14 档 LLD 为唯一规范源）。
> 全库文本一律 UTF-8 无 BOM。

## 项目一句话

Galatea：建造具备感觉、情感、自我意识与学习能力的**单一认知个体**，一切"具备"以可干预、可测量、可复算的真实因果结构为证（功能/因果实在论，D-10）。

## 当前状态（2026-09-23）

- **裁决权模型 v2（AI 主导）**：自 2026-09-23 起，一切 Q 号/ADR/门冻结裁决由开发 AI 按 `DEV_SPEC.md` §4.6 自主作出（成文裁决 + 重开条件；分级：可逆/难逆/证据可判）；owner 否决权保留。AI 裁决在登记册中以 **AI-v2** 标识。
- **阶段独立评审（REV，Q-DEV-05）**：门冻结前/难逆决策后/重大批次后，由**不带作者上下文的新起子代理**只读评审（六维：目标对齐/DoD/军规/一致性/自包含性/裁决质量），报告入 `_audit/reviews/REV-<dddd>.md`，异议须书面回应闭环，未闭环 S1+ 阻断门冻结。**目标锚定（owner 要求）**：最终目标唯一权威表述 = 本文件"项目一句话" + HLD §1/§2，一切产出须可回答"如何服务该目标"。
- **主线**：**F0 已退出（2026-09-25，ADR-G-0003 + tag `f0-exit`；合同冻结 2026-09-23 ADR-G-0002 + tag `f0-freeze`）**。退出判据 = **HLD §10.2 F0 行**（注意：§10.4 系旧引用漂移，REV-0003 R7 勘误；ADR-G-0002 原文不改，以 ADR-G-0003 勘误注记为准）。实现期交付：kernel（L00 §10 全量）、decision_registry（L13 §10）、五类分 schema（truth/received/belief/self-report/conclusion）、PromotionDecision schema（REV-0003 R3 补交付）。**验证基线：`uv run pytest` 85 passed、pyright strict（kernel/evidence/subject）0 错误**（ACT-08：uv.lock 哈希锁定，venv 重建 = `uv sync`）。REV-0003 判定 APPROVE-EXIT，R1–R4 同提交闭环（R1=INC-08 空转探针，教训：静态探针必须先证明对被检对象可见且能失败）；R5/R9 九项移交 M0 准备单元（清单见 ADR-G-0003）。**M0 阻断已清零**（2026-09-25 AI-v2 成组裁决 9 项：Q-L00-04 ChaCha8 后端、Q-L01-01…04、Q-L05-04、Q-L09-06、Q-L10-02、Q-L10-09；登记册 51/83/1）；ADR-G-0003 移交处置十项全闭环。**M0 profile 已冻结**（2026-09-25，ADR-G-0004 + tag `m0-freeze`；REV-0004 PASS-WITH-FINDINGS R1–R9 同提交闭环，R2–R4/R6 经新 Q-L01-09 补裁——风暴率全局语义/觅食闭环/floor/load 简化/loss=0）。登记册 54/81/1。**当前 = M0 实现期**：MW0 世界核心已交付（mw0.py 几何/身体/原语/regime 机、dynamics.py 表格化推进+风暴确定性采样、interventions/registry.py 先注册后生效、profile.py 加载合同；Q-G00-09 布局派生：风暴带=round(storm_rate×256)、shelter M0 不布设）；世界轨迹 tick 级 bit-exact 已测（同 seed 同轨迹/异 seed 发散）；干预电池世界侧 signature 已测（no_op/sham/coercion 生效、blocked/fault 注册承载）。gateway 执行逻辑已交付（L10 §10：signature.py 确定性 HMAC 命令签名 + gateway.py 八项校验顺序固定/全项评估/fail closed——fail-closed 矩阵八项逐项测试全绿，参数单一事实源=双 profile 真实加载）；通道行为层已交付（adapter.py ChannelBus：render→transport(延迟/损坏字节级扰动/丢失=0)→RECEIVED 包，DeliveryFact 证据侧分离，fault 干预投递时刻生效→MissingSignalEvent；五通道渲染器 extero/intero/proprio/outcome/language_stub——语言仅实验控制 typed 注入）。余件：端到端 MW0-SC1/SC2 场景接线 + ReplayTest/LeakageProbe e2e（L09 控制器是否需 stub 文件随 e2e 单元按清单纪律定）；M0 目标 = MW0-SC1/SC2 全量 + 五类干预电池 + gateway fail-closed + ReplayTest/LeakageProbe。余 M1 阻断：Q-L08-01/-06（M1 准备单元）。
- **版本管理**：已 git 化（2026-09-17 ACT-01，main 分支；提交纪律见下）。
- **2026-09-18 子项目剥离**：原 `physio/`（Zephyr 固件子项目）已整体剥离为独立项目，与本仓库不再有任何开发耦合；其全部研究资料保存在 git tag `physio-handoff`。Galatea 的 PhysIO 仍为 P1 物理接口层的**概念合同名**（HLD 附录 A.10），未来实现载体另行裁决。

## 会话开始必做

1. 通读本文件；
2. 读 `DEV_SPEC.md` §0（效力域）、§4.6（裁决权模型 v2）与 §9（军规十条）；
3. 读 `design/README.md` 全文（索引 + 修订记录 = 最近变更权威位置）；
4. 按 `DEV_SPEC.md` 附录 A"任务 → 必读清单"加载任务上下文；
5. 检查约束：moratorium、门状态、Q 阻断清单。

## 军规十条（全文与定义见 DEV_SPEC §9）

1. 优先级链至上（流程事务：LOCKED > DEV_SPEC；架构事务：LOCKED > HLD > 冻结 profile > LLD > ADR > 代码）。
2. 无 Q 号不落盘——参数/选型/命名未裁决，不得进规范、profile、代码常量。
3. 阶段白名单不可越——RESEARCH 期禁产任何实现物。
4. 单写者与 HLD §6.2 十四条禁止写入路径必须在代码中机械体现。
5. 显式 UTF-8 无 BOM；禁用依赖系统代码页的批处理（曾因此损毁 8 份文档）。
6. 结论必须落盘——聊天与记忆不是项目状态；会话结束前写入规范文件/登记册。
7. 跨文档引用带文档名限定；引用的 Q 号必须是已登记项。
8. 改规范必留修订记录并同步交叉引用；禁止半成品文档互相矛盾。
9. 已裁决技术栈不为"更优"重启；变更只走 DEV_SPEC §7 门槛。
10. 交付即验证——DoD 对照 + `check_docs.py` + 对应测试层；失败如实报告。

## 仓库地图

```text
AGENTS.md            ← 本文件（入口）
DEV_SPEC.md          ← 开发规范：AI 工作流 + 标识符命名空间登记册（流程域最高法）
design/              ← 主线规范源：HLD.md + lld/L00–L13 + open_questions.md（Q 登记册）
                       archive/（6 张历史卡片，NON-NORMATIVE）
_audit/              ← check_docs.py（文档机器校验，文档变更后必运行）+ report.md + incidents.md（缺陷台账）
                       reviews/（REV-<dddd> 阶段独立评审报告，Q-DEV-05）
galatea/             ← 主线实现（未创建；须 LLD §10 清单 + Q 解冻后按门生成）
config/profiles/     ← frozen profile（F0 冻结 3 份：f0_l00 / f0_action_contract / f0_language_contract）
config/evidence/      ← 证据合同（F0 冻结 4 份：claim_v1 模板 / min_effects / sealed_split_policy / decision_path_matrix）
（physio/ 已于 2026-09-18 剥离；历史资料见 git tag physio-handoff）
```

## 会话结束必做

1. 持久结论已写入规范文件/登记册（Q 号、修订记录、incidents）；
2. 文档有变更则运行 `_audit/check_docs.py` 并确认通过；
3. 提交本会话交付（每交付单元一提交，会话结束兜底提交）；涉门冻结/重大裁决时打 tag；
4. 未完成事项登记为 Q 号或 ACT 行动项，不留口头尾巴。

## 红线速查（违反即流程缺陷，定级处置见 DEV_SPEC §6）

- 未经裁决将任何默认值/选型写成"已决定"，或写入 profile/代码常量；
- 在 RESEARCH/moratorium 区产出或修改实现物与冻结区实质内容；
- 使用 PowerShell `Get-Content`/`Set-Content` 等依赖系统代码页的批量文本操作；
- 绕过 LLD §10 文件级清单"顺手"新增文件或重构；
- 把失败改写为"主体选择不行动"式的话术修饰（项目核心认识纪律的流程对应物：失败必须类型化留痕）。
