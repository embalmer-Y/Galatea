# 文档机器校验报告（只读）

根目录：`D:\Software\project\Galatea\design`

扫描 `.md` 文件数：**24**

## 1. 严格 UTF-8 解码

- OK：24/24 全部严格 UTF-8 解码通过，无 BOM、无 U+FFFD

## 2. Q 编号闭合（声明 vs 引用）

- 登记册声明 Q 号：**141**
  - CONFIRMED: 135
  - UNCONFIRMED: 5
  - CLOSED: 1
  - 分区分佈：{'A': 135, 'B': 3, 'C': 1, 'M': 1, 'P': 1}

- OK：无重复声明

- **WARNING 被引用但登记册未声明（10）**：
  - `Q-G00-05` → HLD.md, README.md, lld/L05_drive_appraisal_affect.md, open_questions.md
  - `Q-L03-06` → lld/L03_perception.md, lld/L05_drive_appraisal_affect.md, open_questions.md
  - `Q-L04-05` → lld/L04_world_body_self.md, lld/L05_drive_appraisal_affect.md, open_questions.md
  - `Q-L05-05` → README.md, lld/L05_drive_appraisal_affect.md, open_questions.md
  - `Q-L06-05` → lld/L06_memory.md, lld/L11_learning_consolidation.md, lld/L13_evidence_evaluation_registry.md, open_questions.md
  - `Q-L11-03` → lld/L11_learning_consolidation.md, lld/L13_evidence_evaluation_registry.md, open_questions.md
  - `Q-L11-04` → lld/L11_learning_consolidation.md, lld/L13_evidence_evaluation_registry.md, open_questions.md
  - `Q-L13-06` → lld/L13_evidence_evaluation_registry.md, open_questions.md
  - `Q-L13-07` → lld/L13_evidence_evaluation_registry.md, open_questions.md
  - `Q-T08b` → HLD.md, README.md

- 仅在登记册出现（未被任何 LLD/HLD 引用）的 Q 号数：0

### 各 LLD 自声明 Q 号数（§11 表）

- `lld/L00_kernel.md`: 7 → Q-L00-01, Q-L00-02, Q-L00-03, Q-L00-04, Q-L00-05, Q-L00-06, Q-L00-07
- `lld/L01_environment_channels.md`: 9 → Q-L01-01, Q-L01-02, Q-L01-03, Q-L01-04, Q-L01-05, Q-L01-06, Q-L01-07, Q-L01-08, Q-L01-09
- `lld/L02_sensorium.md`: 7 → Q-L02-01, Q-L02-02, Q-L02-03, Q-L02-04, Q-L02-05, Q-L02-06, Q-L02-07
- `lld/L03_perception.md`: 7 → Q-L03-01, Q-L03-02, Q-L03-03, Q-L03-04, Q-L03-05, Q-L03-06, Q-L03-07
- `lld/L04_world_body_self.md`: 7 → Q-L04-01, Q-L04-02, Q-L04-03, Q-L04-04, Q-L04-05, Q-L04-06, Q-L04-07
- `lld/L05_drive_appraisal_affect.md`: 8 → Q-L05-01, Q-L05-02, Q-L05-03, Q-L05-04, Q-L05-05, Q-L05-06, Q-L05-07, Q-L05-08
- `lld/L06_memory.md`: 8 → Q-L06-01, Q-L06-02, Q-L06-03, Q-L06-04, Q-L06-05, Q-L06-06, Q-L06-07, Q-L06-08
- `lld/L07_workspace.md`: 7 → Q-L07-01, Q-L07-02, Q-L07-03, Q-L07-04, Q-L07-05, Q-L07-06, Q-L07-07
- `lld/L08_motivation_goals.md`: 9 → Q-L08-01, Q-L08-02, Q-L08-03, Q-L08-04, Q-L08-05, Q-L08-06, Q-L08-07, Q-L08-08, Q-L08-09
- `lld/L09_controllers_metacontrol.md`: 8 → Q-L09-01, Q-L09-02, Q-L09-03, Q-L09-04, Q-L09-05, Q-L09-06, Q-L09-07, Q-L09-08
- `lld/L10_action_gateway_physio_attribution.md`: 9 → Q-L10-01, Q-L10-02, Q-L10-03, Q-L10-04, Q-L10-05, Q-L10-06, Q-L10-07, Q-L10-08, Q-L10-09
- `lld/L11_learning_consolidation.md`: 8 → Q-L11-01, Q-L11-02, Q-L11-03, Q-L11-04, Q-L11-05, Q-L11-06, Q-L11-07, Q-L11-08
- `lld/L12_language_social.md`: 8 → Q-L12-01, Q-L12-02, Q-L12-03, Q-L12-04, Q-L12-05, Q-L12-06, Q-L12-07, Q-L12-08
- `lld/L13_evidence_evaluation_registry.md`: 11 → Q-L13-01, Q-L13-02, Q-L13-03, Q-L13-04, Q-L13-05, Q-L13-06, Q-L13-07, Q-L13-08, Q-L13-09, Q-L13-10, Q-L13-11

## 3. 交叉引用：被引用的 LLD 文件名是否存在

- OK：所有 `Lxx_*.md` 引用均指向存在文件

- 残留通配符引用（`L02_* … L13_*`）：1 → [('HLD.md', 'L02_* … L13_*')]

## 4. 术语漂移

- 含 `Helios` 的文件（应仅作曾用名注记）：[('archive/README.md', 2), ('HLD.md', 4), ('open_questions.md', 1), ('README.md', 1)]
- 独立 `HIO` 令牌计数：14（{'archive/card_02.md': 1, 'archive/card_03.md': 1, 'archive/card_04.md': 1, 'archive/card_06.md': 1, 'archive/README.md': 1, 'HLD.md': 5, 'open_questions.md': 2, 'README.md': 2}）
- OK：全部位于曾用名/更名注记语境
- 旧六层叙事残留（`S5`/`S6`/`S1–S6`；已排除缺陷等级 S0–S4 与切片 MW0-SCx）：[('HLD.md', 2), ('lld/L01_environment_channels.md', 2), ('open_questions.md', 1)]
- “8 层金字塔”残留：无

## 5. LLD 11 节模板符合度

- `lld/L00_kernel.md`: 228 行 · 标题「# L00 横切基础：时钟、调度、状态、RNG、Packet、Registry 核心、typed unknown」 · OK
- `lld/L01_environment_channels.md`: 207 行 · 标题「# L01 环境与声明通道：WorldTruth、Channel Adapter、干预注册、最小世界 MW0」 · OK
- `lld/L02_sensorium.md`: 234 行 · 标题「# L02 Sensorium：感觉形成、校准、对齐与增益」 · OK
- `lld/L03_perception.md`: 210 行 · 标题「# L03 知觉：对象/事件/来源/affordance 与带置信度的 PerceptualBelief」 · OK
- `lld/L04_world_body_self.md`: 235 行 · 标题「# L04 世界/身体/自我模型：信念、rollout、主动感知与自我预测误差」 · OK
- `lld/L05_drive_appraisal_affect.md`: 244 行 · 标题「# L05 驱力-评价-情感：持续动力学、有界 ModulationField 与内稳态价值」 · OK
- `lld/L06_memory.md`: 234 行 · 标题「# L06 记忆：八子系统、来源类型、检索、巩固与遗忘控制」 · OK
- `lld/L07_workspace.md`: 225 行 · 标题「# L07 递归全局工作空间：竞争、广播、读取回执与因果访问」 · OK
- `lld/L08_motivation_goals.md`: 222 行 · 标题「# L08 动机与目标：Motive → GoalCandidate → 承诺检查 → OwnedGoal 与结算」 · OK
- `lld/L09_controllers_metacontrol.md`: 237 行 · 标题「# L09 控制器与元控制：五类控制器并行提案、仲裁与 metacontrol」 · OK
- `lld/L10_action_gateway_physio_attribution.md`: 286 行 · 标题「# L10 行动-网关-PhysIO-归属：授权链、fail-closed gateway、四类现实授权与归属系统」 · OK
- `lld/L11_learning_consolidation.md`: 242 行 · 标题「# L11 学习与巩固：三层可塑性、replay、promotion/rollback 与保护集」 · OK
- `lld/L12_language_social.md`: 251 行 · 标题「# L12 语言与社会认知：typed LLM 角色、权限矩阵与他者模型」 · OK
- `lld/L13_evidence_evaluation_registry.md`: 345 行 · 标题「# L13 证据链与治理：实验控制、独立记录器、评价器、promotion gate、统计计划与 core_decisi」 · OK

## 6. LLD 头部规范（版本/日期/状态/上游/下游/门槛）

- `lld/L00_kernel.md`: OK
- `lld/L01_environment_channels.md`: OK
- `lld/L02_sensorium.md`: OK
- `lld/L03_perception.md`: OK
- `lld/L04_world_body_self.md`: OK
- `lld/L05_drive_appraisal_affect.md`: OK
- `lld/L06_memory.md`: OK
- `lld/L07_workspace.md`: OK
- `lld/L08_motivation_goals.md`: OK
- `lld/L09_controllers_metacontrol.md`: OK
- `lld/L10_action_gateway_physio_attribution.md`: OK
- `lld/L11_learning_consolidation.md`: OK
- `lld/L12_language_social.md`: OK
- `lld/L13_evidence_evaluation_registry.md`: OK

## 7. 冻结配置 YAML 可解析性（config/**）

- 扫描 YAML 文件数：31
- OK：全部 config/**/*.y*ml 经 yaml.safe_load 解析通过

## 8. 证据工件归档核验（config/evidence/artifact_manifest.yaml）

- 清单条目：28（只增不减）
- OK：本地存在的全部工件与归档锚一致
