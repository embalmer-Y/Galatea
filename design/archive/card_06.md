# Galatea 开发计划：C0-C5、集成证据与受控物理具身

> DOC:02 | Development Plan | Cognitive Expansion & Physical Embodiment — CARD:06/06
> NON-NORMATIVE CONDENSED SUMMARY | 源：`02_DEVELOPMENT_PLAN.md` · WORKING v1.1 · 2026-09-08 | 本卡是 2/2，不得替代或覆盖源文档。
> 注：本卡原文术语 HIO 已统一更名为 PhysIO（见 `../open_questions.md` Q-N01）。

## 1. 门后 C0-C5

| 阶段 | 核心工作 | 关键退出条件 | 参考 |
|---|---|---|---|
| C0 认知底座 | 多速率时钟、typed packets/ports、tensor refs、完整 checkpoint、数字身体、gateway；ReceivedSignal→SensorySample/Frame、形成回执和旁路保护 | 确定性重放；无匿名共享写；M0-M2 不退；至少两种外感受和一种内感受形成带来源/时间/质量/增益/不确定性的感觉帧 | 6-8 周 |
| C1 模型形成 | 外感受 encoder、内感受/身体模型、对象/事件、世界/自我模型、rollout、主动感知、OOD；MotorCommandCopy→SensoryPrediction | held-out 优于基线；能力/不确定性校准；感觉/知觉解离；身体纳入由感觉运动预测和跨模态一致性支持 | 10-14 周 |
| C2 感受整合 | drive、appraisal、持续 FunctionalExperientialState、有界 modulation、分层记忆、workspace/read receipt、Sensorium gain receipt | affect 不是 reward/标签；至少三类下游因果调制；workspace lesion 选择性失败；增益有界且不改历史接收 | 10-14 周 |
| C3 自主动机 | Motive、GoalCandidate、OwnedGoal、承诺/冲突/资源、Pareto 仲裁、habit/model-based/active perception、metacontrol | 请求不直写目标；affect/drive 不直达执行；目标持续且可修订；控制可在规划/观察/求助/放弃间切换 | 10-14 周 |
| C4 行动社会 | forward/inverse、主体 EfferenceCopy、感觉预测、概率 agency、typed LLM、他者/规范/承诺、中央 LLM 消融 | 多来源匹配测试；语言不能写事实/经历/目标；agency 只读主体可见回执；形成后结果和感觉误差参与归属 | 8-12 周 |
| C5 持续发展 | learnable registry、online adapter、replay、巩固、self 约束、保护集、promotion/rollback、二阶纠偏；Sensorium/设备适配 | sealed held-out 改善且无保护回退；每次长期更新有父版本/数据/promotion；核心权限/安全/证据不可在线修改 | 12-16 周 |

## 2. E1、H1 与 P1

- **E1 集成证据（8-12 周）**：模块 lesion、edge ablation、角色交换、录制回放、中央 LLM/无 affect/无 workspace/无 self/无 episodic 基线、M0-M2 回归、分布偏移/恢复、压力测试、Sensorium/身体接口干预、六类核心决策全路径。
  **退出**：选择性损失、原始记录可复算、无各类旁路、unresolved_paths[] 为空且分母闭合。
- **H1 平台硬化（3-6 月）**：长时运行、故障注入、checkpoint 稳定/迁移、profiling 后并行化、实验/复算自动化、可视化不泄漏、安全/供应链审计、恢复演练、runbook、可复现发布。
  **退出**：冻结 manifest 可重建；独立人员可运行/恢复/复算；性能优化不破坏确定性和证据兼容。
- **P1 物理具身（12-20 周）**：仅在 E1+H1、PhysIO 安全评审、最高物理权限授权、外部独立急停/失效安全后启用。建设 PhysIO Bridge、设备认证、非学习有界 PhysIOControlGraph、版本化 BodyGraph、passive→calibration→shadow→limited→active、L0-L5 控制、设备新增/更换/隔离/重新纳入。不得旁路 Sensorium/gateway/receipt/evidence。

**P1 四类独立记录**：functional_ability、enabled_interface、containment_allowance、deployment_authorization。分别管理版本、设备、范围、期限、监控、停止、恢复、撤销和重新授权；任一失效或重大变化均 fail closed。

## 3. 测试、模型与数据治理

- **测试金字塔**：Unit→Schema/Contract→Invariant→Deterministic replay→Integration→Ablation→Protection suite→Security→Sealed evaluation。代码覆盖率不能替代关键行为和路径覆盖。
- **模型流程**：role → dataset manifest → baseline → training → calibration → robustness → contract → shadow → ablation → candidate registration → promotion review。训练完成不得直接替换运行主体。
- **机械数据隔离**：InternalValidationSet 仅供主体学习/promotion；SealedScientificEvaluationSet 仅供 EVAL 独立评价。不同类型、token、manifest、namespace；sealed 结果不得回流同一候选。

**缺陷等级**：S0 真值泄漏/证据损坏/未授权现实效果→立即停止；S1 目标/行动旁路或错误工件→阻断发布并废止证据；S2 checkpoint/关键场景错误→阻断阶段退出；S3 性能/工具；S4 文档/易用性。

## 4. 风险、指标与停止规则

- **关键风险**：证据前架构膨胀 | 中央 LLM 劫持 | orchestrator 冒充主体 | reward 塌缩 | 伪情感/伪感觉 | 隐藏真值泄漏 | telemetry 冒充内感受 | 身体纳入伪装 | PhysIO 越权/硬件旁路 | 伪 workspace | 记忆污染 | 灾难性遗忘 | 证据泄漏 | 不确定性伪装 | 非确定性 | 过早优化 | 持续极端 aversive-like 伦理风险。
- **有效指标**：未声明旁路经权限测试 | 重放 digest/独立重建 | S0-S2/回归 | 冻结 claim/对照/替代解释 | 校准/held-out/保护回退 | 有效 read receipts/lesion | 接收到形成延迟/对齐/校准/旁路率/跨模态 | 周期延迟/资源/checkpoint | 参数量、代码行、模块数和演示数不是核心进度。
- **必须停止**：前置门未过 | 真值/hidden label/evaluator 泄漏 | digest/谱系/原始记录损坏 | 未授权现实效果 | 保护集回退否决 | evaluator 无法复算 | 非主体近邻同证据通过 | 结果依赖事后选择/改指标 | 返工生成新版本，失败与旧工件保留；资源不足只能减场景→减模型→延时间→缩非关键功能，不得降低证据、权限、保护、复算或退出标准。
