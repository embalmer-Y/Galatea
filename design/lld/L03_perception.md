# L03 知觉：对象/事件/来源/affordance 与带置信度的 PerceptualBelief

> LLD: L03/14 · v1.0 · 2026-09-13 · 状态：WORKING（C1 冻结前）
> 上游：`HLD.md` §4.1/§4.2/§5/§6 · `L02_sensorium.md`（唯一合法输入）· `L00_kernel.md`
> 下游消费者：L04（信念融合）、L05（appraisal）、L07（workspace 候选）、L08（动机源）、L09（控制器）
> 引入门槛：**C1**（多模态知觉、来源可区分、不确定性校准）→ **C2**（与感受/workspace 联动）→ **E1**（知觉 lesion 选择性失败）

## 1. 目标与范围

**目标**：从 `SensoryFrame`（及明确的内部预测/记忆线索）推断**对象、事件、来源、affordance**，维护**部分可观察信念**与 **unknown**，输出带置信度的 `PerceptualBelief`（PERCEIVED）。知觉是**推断**，不是事实登记：输出恒为信念，禁止任何形式的层级提升。

**范围内**：
- 多模态融合（外感受 × 本体感受 × 内感受线索）与融合权重先验；
- 对象/事件识别、来源判断（self-produced / external / ambiguous）、affordance 提取；
- 置信度标度与校准（含 OOD 检测与 abstain 路径）；
- 知觉层预测误差（与 L04 模型预测比较）；
- 感觉/知觉解离的可测性设计（C1 退出条件）。

**范围外**：世界状态信念与多未来 rollout（L04）；身体信念（L04）；情感与价值（L05）；长期记忆内容（L06，本档只读检索线索）；目标与决策（L08/L09）；任何直接读取通道或隐藏真值的路径。

**成功判据（C1 退出）**：held-out 优于基线；能力与不确定性**校准**（置信度与实际正确率匹配，统计计划见 L13）；感觉/知觉**解离**可证（破坏知觉不影响感觉形成完整性，破坏感觉输入使知觉选择性失败）；感觉、知觉、自我/外部来源**可区分**；无 raw-to-perception 旁路。

## 2. Ports（输入输出契约）

### 2.1 PortIn

| 端口 | 来源 | 数据 | 表示层级 | 纪律 |
|---|---|---|---|---|
| `perc.sensory_in(frames)` | L02 `sensory.frame` | `SensoryFrame` + `alignment_group_id` | SENSORY_FORMED | **唯一外部感觉入口**；禁直读 L01 通道 |
| `perc.pred_in(pred)` | L04（模型预测）、L02（感觉层误差） | `ModelPrediction` / `SensoryPredictionError` | PREDICTED | 必须声明来源模块；预测不得当作感知 |
| `perc.memory_cue(clue)` | L06（声明端口） | `RetrievalCue(kind, refs, confidence)` | RECALLED | 线索只影响先验权重，**不得**直接成为信念内容 |
| `perc.modulation_in(field)` | L05 | 有界精度/阈值调制 | — | 必须回执（§4.5）；不改历史信念 |
| `perc.attention_in(hint)` | L09 | 注意倾向（有界、可拒） | — | 拒绝须记 reason code |

### 2.2 PortOut

| 端口 | 读者 | 数据 | 表示层级 |
|---|---|---|---|
| `perc.belief` | L04/L05/L07/L08/L09、Recorder | `PerceptualBelief` | **PERCEIVED** |
| `perc.objects` / `perc.events` | L04/L08/L09 | `PerceivedObject` / `PerceivedEvent`（belief 的结构化分量） | PERCEIVED |
| `perc.affordance` | L09（控制器）、L04 | `Affordance(action_class, preconditions_est, confidence)` | PERCEIVED |
| `perc.source_judgement` | L04（自我模型）、L10（归属输入之一） | `SourceJudgement(kind∈{SELF,EXTERNAL,AMBIGUOUS,UNKNOWN}, evidence_refs[])` | PERCEIVED |
| `perc.error` | L04/L09/L11 | `PerceptualPredictionError(belief_ref, predicted_ref, residual, precision)` | PERCEIVED（派生） |
| `perc.abstain` | L07/L09/L13 | `AbstainEvent(reason: Unknown, candidates_considered[], threshold_ref)` | EVIDENCE_ONLY 可读 |
| `perc.receipt` | Recorder | `PerceptionReceipt(belief_id, source_frames[], cues[], modulation_recs[], ood_flags[], calibration_version)` | EVIDENCE_ONLY |

**纪律**：输出层级恒为 PERCEIVED；`confidence` 是**校准过的概率标度**，不是"接收质量"，也不是真值概率；abstain 是一等输出，不是异常。

## 3. 状态所有权与单写者

| 状态 | 唯一写入者 | 存储 | 读者 |
|---|---|---|---|
| `PerceptualBelief` 及其分量（object/event/affordance/source） | Perception | subject_state.perception | 声明读者（只读）、Recorder |
| 知觉内部工作缓存（多假设竞争状态） | Perception | 内存 + checkpoint | 内核 |
| 置信度标度校准表（`calibration_version`） | Perception（T6 更新提案）/ Promotion Gate（L11）生效 | subject_state + registry | L13 evaluator |
| `AbstainEvent` / `PerceptionReceipt` | Perception | subject_state.receipts | Recorder/Evaluator |

**禁止**：Perception 写 `SensoryFrame`／`ReceivedSignal`（向上改写）；写 `WorldStateBelief`／`BodyBelief`／`SelfModelView`（L04 所有）；写 `DriveState`／`FunctionalExperientialState`（L05 所有）；写 `WorkspaceFrame`（L07 所有，本档只提交**候选**）；写 `OwnedGoal`／`ActionIntention`；写主体记忆（L06 独占）。

## 4. 算法与数据结构

### 4.1 PerceptualBelief

```text
PerceptualBelief(
  belief_id, kind: enum{OBJECT, EVENT, STATE, SOURCE, AFFORDANCE, FIELD},
  content: ArtifactRef,                      # 结构化内容（MW0 期可为枚举表项）
  confidence: float | Unknown,               # 校准标度（§4.3）；禁裸 None
  alternatives: list[AltHypothesis(content_ref, posterior)],   # 多假设保留，禁过早塌缩
  modality_support: dict[modality, frame_ids],
  source_judgement: SourceJudgement?,
  ood_flag: bool, ood_score: float|Unknown,
  provenance: Provenance(source_frames, cues, calibration_version, modulation_receipts),
  causal_parent_ids: list[event_id],
  valid_window: (t_start, t_end)?,           # 可过期；过期不得被当作当前感知
  representation_level: PERCEIVED,           # 常量
  content_digest: str
)
```

### 4.2 多模态融合（贝叶斯式，MW0 期为表格化）

- MW0 期融合以**枚举/表格后验**实现（承 L01 §4.4"表格化动力学"精神，保证可手算复核）：$\text{posterior}(h) \propto \pi(h)\prod_m \mathcal{L}_m(o_m \mid h)^{w_m}$，其中权重 $w_m$ 由模态质量（L02 `QualityMetrics`）与调制精度共同决定，全部有界。
- 融合权重先验 `π` 与似然表冻结于 profile（UNCONFIRMED → Q-L03-03）；C1+ 可替换为神经 encoder，但**合同不变**（同样的输入/输出/层级/回执）。
- 冲突处理：模态间冲突产生 `Unknown(CONFLICTING_EVIDENCE)` + 保留 `alternatives`，**禁止**用置信度强行调和。
- 来源判断：以本体感受 + efference 相关线索 + 时间一致性联合估计；证据不足必须返回 `AMBIGUOUS` 或 `UNKNOWN`（不可默认 `SELF` 或 `EXTERNAL`）。

### 4.3 置信度标度与校准

- 标度为 [0,1] 概率，须经**校准曲线**（reliability diagram）验证；`calibration_version` 入每个信念的 provenance。
- 校准更新只经 T6 提案 → L11 Promotion Gate（禁在线自改，防"自我宣称可靠"）。
- **能力/不确定性校准**是 C1 硬退出条件：冻结 held-out 上 ECE（或等价量）须达冻结阈值（Q-L03-04 已裁决：ECE≤0.05、等质量 15 箱、每箱 ≥30 样本，AI-v2 2026-09-23，随 Q-L13-09）。

### 4.4 OOD 检测与 abstain

- OOD 评分：MW0 期为观测特征超出冻结枚举域的检测（距离/计数式），C1+ 可换神经评分器。
- 触发 OOD 或后验最高假设低于 `believe_threshold`（UNCONFIRMED → Q-L03-02）→ 发 `AbstainEvent`，并仍可发布 `kind=FIELD` 的低承诺信念（"我看到了什么但无法归类"），**不得**伪造高置信度归类。
- abstain 必须可复算：`candidates_considered[]` + `threshold_ref` 完整留存。

### 4.5 调制回执与知觉层预测误差

- L05 调制只允许改：精度权重 $w_m$、`believe_threshold`、竞争窗口长度；**禁止**改：输入特征、置信度标度、层级、历史信念。每次接受调制写 `ModulationReceipt`（C2 因果调制证据之一）。
- 知觉层误差 = 当前 `PerceptualBelief` 与 L04 `ModelPrediction` 在声明比较空间中的残差；与 L02 感觉层误差**分别记录、不得合并**（层级化预测误差纪律）。

## 5. 时间尺度与调度挂点

| 级 | 挂点活动 |
|---|---|
| T1 | 接收 L02 当窗对齐组，登记候选假设（不做重计算） |
| T2（每 cycle，承 L00 §5） | 主知觉计算：融合、来源判断、affordance、OOD、发布信念与回执 |
| T3 | 向 L07 提交 workspace 候选（`WorkspaceProposal`，含显著性分量） |
| T4 | 响应 L09 的注意/主动感知请求（可拒，须 reason code） |
| T5/T6 | 误差汇总供 L11 学习提案；校准表更新提案（T6 经 Promotion Gate） |

## 6. 失败模式与 typed unknown

| 失败 | 类型化 | 行为 |
|---|---|---|
| 输入帧层级不合法（收到非 SENSORY_FORMED） | `SchemaViolation` | 拒绝；记 S1（可能是旁路企图） |
| 模态证据不足 | `Unknown(INSUFFICIENT_OBSERVATION)` | 降低承诺或 abstain |
| 模态冲突 | `Unknown(CONFLICTING_EVIDENCE)` | 保留 alternatives；禁强调和 |
| 来源不可判 | `Unknown(SOURCE_AMBIGUOUS)` | `SourceJudgement=AMBIGUOUS/UNKNOWN` |
| OOD | `Unknown(OOD)` + `ood_flag` | abstain 或低承诺 FIELD 信念 |
| 超出能力域（模态未支持） | `Unknown(CAPABILITY_LIMIT)` | 不形成信念；回执留痕 |
| 校准版本缺失/不符 | `CalibrationMismatch` | fail closed |
| 检出 `SensoryFrame → PerceptualBelief` 之外的输入路径 | `UnauthorizedInput(path)` | S0：停止 + 废止证据 |

**纪律**：不确定即 `Unknown` + abstain，禁以"最可能假设"冒充感知，禁把置信度低写成置信度高。

## 7. 可测性

| 层 | 测试 | 断言 |
|---|---|---|
| unit | 表格后验计算、OOD 评分、冲突分支 | 确定性、可手算复核 |
| contract | 只接受 SENSORY_FORMED 入口；输出层级恒 PERCEIVED；`Unknown` 强制类型 | schema 强制 |
| invariant | 广播/缓存/存储不提升层级；`confidence` 标度不可被下游改写；abstain 不产生高置信信念 | 认识链 |
| deterministic replay | 同 (profile, seed, 帧序列) → 信念序列 bit-exact | C1 |
| calibration | 冻结 held-out 上可靠性曲线 / ECE 达阈值；与"接收质量"的相关性不得被冒用为真值概率 | C1 硬条件 |
| dissociation | **感觉/知觉解离**：注入知觉故障 → 感觉帧形成完整性不变；降质感觉输入 → 知觉正确率与置信度同步下降 | C1 硬条件 |
| ablation | 移除来源判断 → 自我/外部区分应失败；移除 OOD → abstain 率应坍缩为 0（可检出退化）；移除 L06 线索 → 先验效应应消失 | 选择性失败 |
| leakage | 信念内容与 WorldTruth 的未声明相关性；`content` 是否含真值坐标衍生量 | 无 oracle 泄漏 |
| protection suite | MW0 知觉回归场景（含 abstain 场景）在 C2+ 不退化 | E1 回归 |

**指标**：held-out 正确率 vs 基线｜ECE/校准误差｜abstain 率与 abstain 正确性（应在低证据条件下升高）｜多假设保留率｜来源判断混淆矩阵｜模态贡献度（经消融）｜知觉延迟｜旁路检出数=0。

**无效指标**：类别数、信念吞吐、参数量。

## 8. 不变量与禁止写入路径

**专属不变量**：
1. 知觉输出恒为 PERCEIVED 信念，且 `PerceptualBelief` 不得被任何下游改写为事实；
2. 知觉只消费 `SensoryFrame` 与**明确声明**的内部预测/记忆线索，禁读通道与隐藏真值；
3. 来源判断不得默认归因（证据不足 → AMBIGUOUS/UNKNOWN）；
4. 置信度是校准标度，接收质量 ≠ 真值概率；
5. abstain 与 `Unknown` 是一等输出，禁止用高置信度假设填补；
6. 记忆线索只调先验，不得直接注入信念内容（`LLM/memory → world truth` 的知觉侧对应物）。

**禁止写入路径**：`Perception → raw channel`｜`Perception → SensoryFrame/ReceivedSignal`｜`Perception → WorldStateBelief/BodyBelief/SelfModelView`｜`Perception → OwnedGoal/ActionIntention/gateway`｜`Perception → subject memory（写）`｜`Perception → WorkspaceFrame（只能提交候选）`｜`memory/LLM cue → PerceptualBelief 内容直填`。

## 9. 引入门槛

- **C1**：多模态融合、对象/事件、来源判断、affordance、OOD/abstain、校准达标、感觉/知觉解离证明。
- **C2**：与 L05 有界调制（含 ModulationReceipt，作为"至少三类下游因果调制"之一）、与 L07 workspace 竞争供给。
- **C3**：向 L08 提供 opportunity/mismatch 类动机源（`PerceptualBelief` 的失配信号），但禁写目标。
- **C4**：与语言（L12）交互时，知觉信念可被**引用**为陈述依据，但语言输入不得写信念（HLD §2 D-13）。
- **C5**：知觉层误差参与 L11 学习提案；校准表更新经 Promotion Gate；保护集回退判据。
- **E1**：知觉模块 lesion → 选择性失败（识别/来源/affordance 分别可辨）；知觉层是"构成/边界"决策路径的证据源之一。
- **P1**：物理来源观测仍走 L01→L02→本档，禁因物理性而绕过。

## 10. 实现清单（文件级）

```text
galatea/subject/perception/                # strict 类型
  ports.py             PortIn/PortOut、层级常量断言、拒绝路径
  believe.py           PerceptualBelief 构造/冻结构造/digest
  fusion.py            多模态表格后验（MW0）、权重 w_m、冲突处理
  objects.py events.py affordance.py
  source.py            SourceJudgement（SELF/EXTERNAL/AMBIGUOUS/UNKNOWN）
  ood.py               OOD 评分与 abstain 判定（believe_threshold）
  confidence.py        置信度标度、校准表加载、ECE 计算接口（评估在 L13）
  pred_error.py        知觉层预测误差（与 L04 预测比较）
  modulation.py        ModulationReceipt、允许/禁止调制项白名单
  receipt.py           PerceptionReceipt
  workspace_prop.py    向 L07 的 WorkspaceProposal 构造（显著性分量）
galatea/subject/perception/tests/
  test_fusion_table.py test_abstain.py test_calibration_scale.py
  test_dissociation.py test_source_ambiguity.py test_no_raw_channel.py
  test_level_invariance.py test_modulation_whitelist.py test_ablation_ood.py
config/profiles/
  c1_perception.profile.yaml   融合先验/似然表/阈值/OOD 参数/校准版本（冻结前 UNCONFIRMED）
```

## 11. 未决问题（→ open_questions.md）

| Q 号 | 问题 | 依赖 | 状态 |
|---|---|---|---|
| Q-L03-01 | 置信度标度形式（直接概率 vs logit vs 离散档）与跨模态可比性 | C1 | UNCONFIRMED |
| Q-L03-02 | `believe_threshold` 与 OOD 阈值默认值；abstain 是否分级（部分承诺） | C1 | UNCONFIRMED |
| Q-L03-03 | MW0 表格融合的先验 π 与似然表构造方式（手算可复核 vs 由 L01 dynamics 表导出） | C1 | UNCONFIRMED |
| Q-L03-04 | 校准达标判据（ECE 阈值、分箱策略、最小样本量）——与 L13 统计计划联动 | C1 | CONFIRMED（AI-v2 2026-09-23，随 Q-L13-09：ECE≤0.05、等质量 15 箱、每箱 ≥30） |
| Q-L03-05 | 多假设保留数量上限与塌缩条件（何时必须收敛为单信念） | C1/C2 | UNCONFIRMED |
| Q-L03-06 | affordance 的 `action_class` 枚举与 L09/L10 能力契约的对齐方式 | C3/C4 | UNCONFIRMED |
| Q-L03-07 | C1+ 神经 encoder 替换表格融合时的等价性验证方法（防"换实现即换主张"） | C1 | UNCONFIRMED |
