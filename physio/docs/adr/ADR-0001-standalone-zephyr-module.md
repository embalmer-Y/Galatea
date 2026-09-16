# ADR-0001：PhysIO 拆分为独立西 Zephyr 模块子项目

- 状态：PROPOSED（待 owner 批准）
- 日期：2026-09-15
- 关联：Q-PIO-08（仓库形态与许可证）

> ⚠️ **状态说明（2026-09-16）**：本 ADR 的**结论未变且仍成立**（PhysIO 作为 Zephyr module，`module/` 零 Galatea 依赖），
> 但它的**实现产物已随全部 C/构建文件一同撤回**（`module/zephyr/module.yml`、`module/CMakeLists.txt`、`module/Kconfig` 已删）。
> 原因：流程为 research → HLD → LLD → 实施，研究阶段不得落盘构建系统。
> HLD 冻结后按 LLD 的文件级实现清单重新生成；`module/zephyr/module.yml` 属 M0 产物。
> ⇒ 目前 `module/` 下只有 `.gitkeep` 占位目录，**仓库无任何可构建目标，这是预期状态**。

## 背景

Galatea 整体技术栈庞大且含大量未验证前沿技术（详见 design/HLD.md）。owner 决定先从 PhysIO 切入实现，并要求 PhysIO 未来能作为独立模块复用于其他项目。

## 决策

PhysIO 以 **Zephyr module**（`zephyr/module.yml`）形态组织，物理上先 in-tree 存放于 `physio/`，逻辑上满足两个硬约束：

1. `module/`（框架核心）**零 Galatea 依赖**——不 include、不链接任何 Galatea 概念；
2. Galatea 对接逻辑全部收敛在 `app/galatea_node/` 薄层 + 宿主侧 Bridge，整体删除不影响框架构建。

机械验证：CI 必须能单独构建 `module/`（不带 app），该测试通过是"可独立复用"的唯一证据。

## 备选方案

- A. 直接作为 Galatea Python 代码库的子目录：违反 MCU 固件的语言/工具链现实，否决。
- B. 一开始就独立仓库：在首次外部复用发生前维护成本高（双仓 CI/版本同步），延迟到 Q-PIO-08 裁决点再拆。

## 后果

- 正面：复用边界机械可验；Galatea 侧 P1 前可独立推进固件开发。
- 代价：多一层 west 工作区初始化步骤；协议 schema 需在两仓之间做单一事实源管理（→ 未来由 schema 文件生成 C 头与 Pydantic 模型）。
