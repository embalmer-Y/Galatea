# Galatea 设计文档索引

> v1.1.1 · 2026-09-17 · 规范状态：**NORMATIVE**（HLD + LLD 全集 14 档为唯一规范源；开发流程与标识符域归仓库根 `DEV_SPEC.md`）
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
- **标识符**：跨文档标签/缩写（D-/Q-/Lxx/S0–S4/门号/ADR…）统一由根 `DEV_SPEC.md` 第二部分登记册管辖；新增命名空间须走其 §14 注册流程；physio 域改标提案 Q-ID-01…06 待 owner 裁决。
- **九条认识不变量**与**机械禁止写入路径**见 HLD §11.1 / §6.2——CI + 运行时双重强制。
- **门体系不可颠倒**：F0→M0→M1→M2→R0→ALLOW_NEXT_STAGE→C0–C5→E1→H1→物理授权→P1；投入成本不得降低门。
- **术语**：物理 I/O 层统一称 **PhysIO**（曾用名 HIO = Helios I/O，已废弃，见 open_questions Q-N01）。

## 修订记录

- 2026-09-12 v1.0：基于卡片重建 HLD + L00 + L01；卡片归档；Q 登记册建立（Q-G/L00/L01 系列 + 技术栈 Q-T01–T12 已裁决）。
- 2026-09-12 v1.0.1：HIO → PhysIO 全库更名（含 archive）；期间发生 PowerShell ANSI 编码事故，8 份文档按 HLD 附录 A.6 重建为 UTF-8 无 BOM。
- 2026-09-12 v1.0.2：全文档审计（12 份 `.md`；编码/交叉引用/术语/内容矛盾四类）——修复：HLD §12/§13.1 附录引用 A.5→A.6、测试金字塔 8→9 层、A.5 计数机器复核校正、L00 悬空 Q-T08b→Q-T08、Q-L00-03 废弃（已被 Q-T10 裁决取代）、Q-G00-01/02 降级为指针、新增 HLD §4.4 实验对象符号约定 + Q-G00-06。详见 HLD 附录 A.7。
- 2026-09-13 v1.1.0：**L02–L13 十二份组件 LLD 批量交付**（Q-C06 既定节奏：风格经 HLD+L00+L01 确认后启动）；14 档全集完成，每档统一 11 节模板。`open_questions.md` 升 v1.1：E 区占位段替换为 E–P 十二个真实分区（新增 95 个 UNCONFIRMED Q 号：L02 7、L03 7、L04 7、L05 8、L06 8、L07 7、L08 8、L09 8、L10 9、L11 8、L12 8、L13 10），新增 Q 区（跨档联动对 10 组 + F0/M0/M1 阻断清单）；HLD 新增附录 A.8 批量交付记录。修复 L05 §4.5 `` `EthicsReviewTrigger` `` 反引号内多余空格。**F0 冻结待 owner 裁决**：Q-L01-06、Q-G00-04/Q-L13-04、Q-G00-06 及 Q 区所列 F0 合同级 schema 项。
- 2026-09-17 v1.1.1：**开发规范设立**（owner 指令）：仓库根新增 `DEV_SPEC.md`（AI 开发工作流 + 标识符命名空间登记册，流程域 NORMATIVE）与 `AGENTS.md`（AI 会话第一入口）；`_audit/incidents.md` 缺陷台账建立（预登记 INC-01…06）。本档阅读顺序新增第 0 步、纪律速记改为双轴优先级链；HLD §0 增补 DEV_SPEC 效力位并新增附录 A.9；open_questions 新增 Q-G00-07（L13 所引 "E0" 门全库无定义）并把 UNCONFIRMED 计数 113→114。标识符改标提案 Q-ID-01…06 与过渡行动项 ACT-01…05 登记于 DEV_SPEC 附录 C/§13。
