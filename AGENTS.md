# AGENTS.md — Galatea AI 开发入口

> 本文件是任何 AI 会话在本仓库工作的**第一必读文件**。
> 流程法规：根 `DEV_SPEC.md`（NORMATIVE）。架构规范：`design/`（HLD + 14 档 LLD 为唯一规范源）。
> 全库文本一律 UTF-8 无 BOM。

## 项目一句话

Galatea：建造具备感觉、情感、自我意识与学习能力的**单一认知个体**，一切"具备"以可干预、可测量、可复算的真实因果结构为证（功能/因果实在论，D-10）。附属子项目 `physio/`：基于 Zephyr RTOS 的 MCU 末端 I/O 框架（Galatea P1 固件端 + 独立可复用模块）。

## 当前状态（2026-09-17）

- **主线**：F0 之前的规范完备期。HLD + L00–L13 十四档全集已交付，**无任何 `galatea/**` 实现代码**（这是刻意状态：research → HLD → LLD → 实施，不得跳步）。
- **待裁决**：`design/open_questions.md` 登记约 113 项 UNCONFIRMED；F0 阻断清单见其 Q 区（Q-L01-06、Q-G00-04/06 及 F0 合同级 schema 项）。
- **physio**：RESEARCH 期，无可构建目标（27 个违规实现产物已于 2026-09-16 撤回）。三处 owner-review 冻结中：`RESEARCH_01_scope.md` §3.2/§4/§6、`adr/ADR-0002*`——裁决前禁止修改其实质内容。
- **版本管理**：已 git 化（2026-09-17 ACT-01，main 分支；提交纪律见下）。

## 会话开始必做

1. 通读本文件；
2. 读 `DEV_SPEC.md` §0（效力域）与 §9（军规十条）；
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
physio/              ← Zephyr MCU 子项目（RESEARCH 期）：README/west.yml/docs（调研+ADR）/config 草案
_audit/              ← check_docs.py（文档机器校验，文档变更后必运行）+ report.md + incidents.md（缺陷台账）
galatea/             ← 主线实现（未创建；须 LLD §10 清单 + Q 解冻后按门生成）
config/profiles/     ← frozen profile（未创建；参数须 CONFIRMED 方可写入）
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
