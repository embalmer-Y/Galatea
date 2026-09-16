# Galatea 开发计划：门前证据链 F0-M2 与扩展决定

> DOC:02 | Development Plan | Evidence-Gated Foundation — CARD:05/06
> NON-NORMATIVE CONDENSED SUMMARY | 源：`02_DEVELOPMENT_PLAN.md` · WORKING v1.1 · 2026-09-08 | 本卡是 1/2。计划由证据门驱动；时间只用于资源预测，阶段退出只由冻结证据和工程条件决定。

## 1. 两个不可颠倒的时期

```text
时期 A: F0 → M0 → M1 → M2 → R0(root EvidenceResult) → independent ExpansionDecision
                                  ALLOW_NEXT_STAGE only ↓
时期 B: C0 → C1 → C2 → C3 → C4 → C5 → E1 → H1 → independent physical authorization → P1
```

- **里程碑成功**：FIRST_VERSION_MILESTONE_CRITERIA_SATISFIED(...).status == SUPPORTED。不等于活动主体、完整 Galatea、意识、身份继续或部署许可。
- **扩展授权**：根证据与 ExpansionDecision 必须分别记录。只有 recommendation = ALLOW_NEXT_STAGE 才允许启动 C0。
- **资源假设**：团队 10-14 人；时期 A 7-11 月，时期 B 15-21 月，硬化 3-6 月，总计 25-38 月。失败门会延长、返工或终止计划。

## 2. 八条长期工作流

**GOV** 术语/ADR/权限/版本 | **RUN** 时钟/调度/状态/checkpoint | **ENV** 真值/通道/干预 | **COG** Sensorium/知觉/记忆/情感/自我/目标/决策 | **ACT** intention/gateway/containment/来源 | **LRN** 状态承接/更新/纠偏/巩固/防遗忘 | **EVD** recorder/profile/统计/sealed evaluation/EvidenceResult | **QLT** CI/测试/工件/依赖/安全/发布。主评价链必须组织上独立于被评价机制。

## 3. 门前阶段与退出纪律

| 阶段 | 目标与最小范围 | 关键交付 / 实验 | 退出纪律 |
|---|---|---|---|
| F0（3-4 周） | 将锁定概念变成工程合同，不实现复杂认知 | 术语/对象图、W/O/S/C/G/R/D/A*/A/Ä/Y/Ŷ/Z 映射、typed unknown、权限矩阵、threat model、checkpoint、manifest、基线合同、core_decision_registry | 唯一写者；真值/接收/信念/自述/结论分 schema；门后合同不改 M0 |
| M0（6-8 周） | 可审计因果通道；证明 W/O、A/Ä、Y/Ŷ 隔离和非平凡动作效应；不主张自主选择 | deterministic environment、observation/action/receipt/outcome channels、gateway、recorder、checkpoint/branch、offline evaluator；no-op/sham/blocked/fault/coercion | 确定性重放；干预外记；evaluator 不读主体日志；无 oracle 泄漏；失败不启动 M1 主评价 |
| M1（8-12 周） | 最小目标拥有、理由仲裁、非平凡选择、授权、来源判断和结算 | S_t/Q_t/G_t/R_t/D_t/A_t*/Z_t+1；目标接受/拒绝/修改/延期/解除；真实理由与伪理由、来源线索交叉操纵；匹配近邻 | 请求不直写目标；真实理由而非伪理由改变选择；意图/授权/执行/回执可分；归属经交叉操纵校准 |
| M2（12-16 周） | 连续状态和局部纠偏；经历经非初始化路径进入下一轮 | 经历编码、更新、checkpoint 谱系、冻结/重置/伪更新对照、sealed held-out、protection suite、二阶段纠偏、独立复算 | held-out 达冻结最小效应；随机分支 intent-to-treat；保护指标不退；有害更新可再次纠正 |
| R0（4-8 周） | 冻结根证据并单独形成扩展决定 | 冻结 artifact/profile/protocol/statistics/branches；sealed 执行；保存失败/删失/异常；机械检查 scope；I2 独立复算或 I3 独立复现 | SUPPORTED 无约束→可 ALLOW；有约束/INCONCLUSIVE→HOLD；REFUTED→REWORK；投入成本不得降低门 |

## 4. 时期 B 的全部启动条件

- 根证据绑定明确的 profile、system version 和 artifact digest；根状态为 SUPPORTED。
- ExpansionDecision = ALLOW_NEXT_STAGE；认知扩展的资源、安全和伦理约束已批准。
- 当前架构文档与 C0 profile 已评审；门前候选工件被归档，不被门后变更覆盖。

## 5. 前 90 天重点

建立术语/schema 工作组和 W/O/…/Z 映射 | 权限矩阵、ADR 模板、C1 基线 | 环境合同、标识/时间/envelope、recorder manifest、M0 协议草案 | 确定性环境、动作效果、三类通道、typed unknown、gateway 测试 | recorder/checkpoint/分支/no-op/sham/blocked/泄漏测试 | 冻结 M0 工件/profile，独立评价，再决定进入 M1 或返工。不得预先开始 M1 claim-relevant 实验。
