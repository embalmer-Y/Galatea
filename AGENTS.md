# AGENTS.md — Galatea AI 开发入口

> 本文件是任何 AI 会话在本仓库工作的**第一必读文件**。
> 流程法规：根 `DEV_SPEC.md`（NORMATIVE）。架构规范：`design/`（HLD + 14 档 LLD 为唯一规范源）。
> 全库文本一律 UTF-8 无 BOM。

## 项目一句话

Galatea：建造具备感觉、情感、自我意识与学习能力的**单一认知个体**，一切"具备"以可干预、可测量、可复算的真实因果结构为证（功能/因果实在论，D-10）。

## 当前状态（2026-09-23）

- **裁决权模型 v2（AI 主导）**：自 2026-09-23 起，一切 Q 号/ADR/门冻结裁决由开发 AI 按 `DEV_SPEC.md` §4.6 自主作出（成文裁决 + 重开条件；分级：可逆/难逆/证据可判）；owner 否决权保留。AI 裁决在登记册中以 **AI-v2** 标识。
- **阶段独立评审（REV，Q-DEV-05）**：门冻结前/难逆决策后/重大批次后，由**不带作者上下文的新起子代理**只读评审（六维：目标对齐/DoD/军规/一致性/自包含性/裁决质量），报告入 `_audit/reviews/REV-<dddd>.md`，异议须书面回应闭环，未闭环 S1+ 阻断门冻结。**目标锚定（owner 要求）**：最终目标唯一权威表述 = 本文件"项目一句话" + HLD §1/§2，一切产出须可回答"如何服务该目标"。
- **主线**：**F0 已冻结（2026-09-23，ADR-G-0002 + tag `f0-freeze`）**——7 份工程合同入库（`config/profiles/` 3 份 + `config/evidence/` 4 份）。当前 = **F0 实现期**：按 L00/L01/L10/L12 §10 清单生成 `galatea/`（kernel 骨架 + schema stubs + core_decision_registry 骨架）+ 同批测试；退出判据 = HLD §10.4 F0 行（唯一写者成立；真值/接收/信念/自述/结论分 schema；core_decision_registry 建立）。
- **F0 直接阻断已清零**（2026-09-23 AI-v2 成文裁决 21 项，含执行中补裁的 Q-L00-01/02，见 A 区当日批次）；剩余 M0/M1 阻断项（Q-L01-01…04、Q-L09-06、Q-L10-02、Q-L08-01/-06）在 M0 准备单元处理。登记册规模：CONFIRMED 41 / UNCONFIRMED 92 / CLOSED 1。
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
