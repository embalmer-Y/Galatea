# L02 Sensorium：感觉形成、校准、对齐与增益

> LLD: L02/14 · v1.0.3 · 2026-10-03（v1.0.3：§11 Q-L02-01/04/06 转 CONFIRMED——C1 件裁决；校准 c1-static-v1）· v1.0.2 2026-10-03（v1.0.2：§10 实现期首批交付标注——十二件 + pipeline 装配面补录 + tests/conftest 装置 + 测试八件全绿；C0 实现期首单元）· v1.0.1 2026-10-02（§11 Q-L02-03/-05 转 CONFIRMED——AI-v2 C0 准备单元裁决；`config/profiles/c0_sensorium.profile.yaml` v1.0 随 C0 门冻结单元成稿，Q-G00-12 伞式）· v1.0 2026-09-13 · 状态：**C0 实现期**（冻结物 c0_sensorium v1.0；门退出待 REV-0012）
> 上游：`HLD.md` §4.2/§4.3/§5/§6/§9 · `L01_environment_channels.md`（唯一合法输入源）· `L00_kernel.md`（envelope/RNG/时钟）
> 下游消费者：L03（知觉，唯一合法消费 SensoryFrame 的模块）、L04（身体模型消费内感受帧）
> 引入门槛：**C0**（形成回执与旁路保护）→ **C2**（有界增益 + 增益回执）→ **C5**（设备/模态适配）

## 1. 目标与范围

**目标**：把主体边界收到的 `ReceivedSignal`（RECEIVED）**形成**为带来源、时间、质量、增益与类型化不确定性的版本化 `SensoryFrame`（SENSORY_FORMED），并完成跨模态时间对齐、校准版本管理与感觉预测误差的低层比较。**形成不是推断**：本档不得输出任何 PerceptualBelief、事实、目标、意图或归属。

**范围内**：
- 外感受形成（MW0 期 ≥2 种模态：局部网格观测、事件/威胁观测）；
- 内感受形成（energy 变化率、integrity 损伤、load/过载、恢复事件 → `InteroceptiveSensation`）；
- 本体感受形成（pos/orientation/能力观测/控制状态）；
- 时间对齐窗、校准版本（`calibration_version`）、质量估计、增益（gain）与增益回执；
- SensoryPrediction 与形成后感觉的低层比较 → 层级化预测误差的**感觉层**分量；
- 形成回执（`FormationReceipt`）与 raw-to-perception 旁路保护。

**范围外**：对象/事件/来源推断（L03）；信念与置信度（L03）；身体信念 `InteroceptiveBodyBelief`（L04）；世界模型 rollout（L04）；注意资源分配的策略（L09 提案，本档只执行有界增益）；任何 telemetry 直填路径。

**成功判据（C0 退出）**：至少两种外感受 + 一种内感受形成带完整五元属性（来源/时间/质量/增益/不确定性）的感觉帧；形成回执可审计；raw-to-perception 旁路经权限测试被拒；接收→形成延迟、对齐误差、校准漂移、旁路率、跨模态一致性全部进入指标；同一 (profile, seed, ReceivedSignal 序列) 下形成结果 bit-exact 重放。

## 2. Ports（输入输出契约）

### 2.1 PortIn（消费）

| 端口 | 来源 | 数据 | 表示层级 | 纪律 |
|---|---|---|---|---|
| `sensory.ingest(received_packet)` | L01 `channel.received` / `outcome.received` | `ReceivedSignalPacket` | RECEIVED | **唯一合法入口**；只读，禁改写（含 attention/affect/prediction 改写）。**C0 期排除 `outcome.received` 载体**（Q-G00-12①：效果回传归 L10 归属域，不入感觉形成；未来如需感觉化 outcome 走新 Q + 模态枚举扩展） |
| `sensory.prediction_in(pred_packet)` | L03/L04/L09 | `SensoryPrediction(target_modality, expected_features, valid_window, precision)` | PREDICTED | 必须带 `valid_window`；过期预测丢弃并记 `deferred/expired` |
| `sensory.modulation_in(field)` | L05 `ModulationField` | 有界增益/精度调制指令 + `modulation_bound_ref` | — | 增益上界由 frozen profile 给定；**必须回写增益回执**（§4.4） |
| `sensory.calibration_load(ref)` | Experiment Control（经 registry） | `CalibrationVersion(id, params_digest, valid_scope)` | — | 版本切换 = 新 profile；运行期禁改参数 |

### 2.2 PortOut（发布）

| 端口 | 读者 | 数据 | 表示层级 | access_scope |
|---|---|---|---|---|
| `sensory.frame` | L03、L04（本体/内感受）、Recorder | `SensoryFrame` | **SENSORY_FORMED** | MODULE_LOCAL→声明读者 |
| `sensory.sample` | L03（可选原始特征）、Recorder | `SensorySample`（形成中间量，版本化） | SENSORY_FORMED | MODULE_LOCAL |
| `sensory.error` | L03/L04/L05/L09/L11 | `SensoryPredictionError(modality, predicted_ref, formed_ref, residual, precision_weight)` | SENSORY_FORMED（派生量） | PUBLIC_BROADCAST（有界） |
| `sensory.formation_receipt` | Recorder、L13 evaluator | `FormationReceipt(frame_id, source_received_ids, calibration_version, alignment_offset, quality, gain_applied, unknowns[])` | EVIDENCE_ONLY | 证据侧 |
| `sensory.gain_receipt` | L05、Recorder | `GainReceipt(modulation_ref, requested_gain, applied_gain, bound_check)` | — | 声明读者 + Recorder |

**纪律**：任何 PortOut 的 `representation_level` 恒为 SENSORY_FORMED（或其派生），**永不**为 PERCEIVED；广播/缓存/存储不得提升层级（HLD §4.2）。

## 3. 状态所有权与单写者

| 状态 | 唯一写入者 | 存储 | 读者 |
|---|---|---|---|
| `SensorySample` / `SensoryFrame` | Sensorium | subject_state.sensory（环形分区 + registry blob 引用） | L03/L04（只读）、Recorder |
| `FormationReceipt` / `GainReceipt` | Sensorium | subject_state.receipts | Recorder/Evaluator（只读） |
| 对齐窗缓冲（跨模态待对齐帧） | Sensorium | 内存 + checkpoint | 内核（序列化） |
| 校准版本绑定表 | Sensorium（启动期加载，运行期只读） | subject_state | 审计 |
| `InteroceptiveSensation` | Sensorium（内感受形成路径） | subject_state.sensory.intero | L04（身体信念唯一来源）、L05（appraisal 输入） |

**禁止**：Sensorium 写 `PerceptualBelief`／`WorldStateBelief`／`BodyBelief`／任何 fact/goal/intention/agency；写 `ReceivedSignal`（含原地修改字段、补零、重排）；写主体记忆（L06）；写 telemetry→InteroceptiveSensation 直填通道（运维 telemetry 只能作为 `Unknown(CALIBRATION_UNCERTAIN)` 的 evidence_refs 出现，不得成为感觉内容）。

## 4. 算法与数据结构

### 4.1 数据结构

```text
SensoryFrame(
  frame_id, modality: enum{EXT_LOCAL_OBS, EXT_EVENT, INTERO, PROPRIO, ...},
  source_received_ids: list[event_id],      # 完整溯源；缺失即 Unknown(MISSING_SIGNAL)
  effective_time: int, formed_time: int,    # 世界时 vs 形成时严格分离（承 L01 §4.5）
  alignment_offset: int, alignment_confidence: float|Unknown,
  calibration_version: str,
  features: ArtifactRef,                    # 大 tensor 只读引用 + digest（L00 §4.4）
  quality: QualityMetrics(snr_est, completeness, corruption_flags[]),
  gain: GainState(applied_factor, bound_ref, source: PROFILE|MODULATION, receipt_id),
  uncertainty: list[Unknown],               # typed，禁裸 None（L00 §6.1）
  representation_level: SENSORY_FORMED,     # 常量，不可被下游修改
  content_digest: str
)
```

### 4.2 形成流水线（T1 挂点，每 cycle）

```text
ingest RECEIVED 包 → 校验 schema/provenance/层级（不符即 SchemaViolation，禁投递）
→ 解 payload_ref 取原始信号 → 缺失/损坏分类（不补零、不静默）
→ 时基归一（effective_time → 对齐窗槽位）
→ 模态内形成（去噪/归一化/特征化，纯确定性，RNG 仅来自 L00 流 ("sensorium", modality)）
→ 校准应用（calibration_version 参数，digest 入帧）
→ 质量与不确定性估计 → 增益应用（§4.4）→ content_digest
→ 发布 SensoryFrame + FormationReceipt
```

**确定性要求**：全部算子 C1 前为表格/枚举或确定性张量算子（禁非确定性 op，HLD §12）；浮点 reduction 顺序固定；无全局 RNG、无墙钟、无容器迭代序依赖。

### 4.3 跨模态时间对齐

- 单一对齐窗 `W_align`（**4 cycles，CONFIRMED Q-L02-03**：T3 对齐，覆盖通道延迟上界 3 倍余量）；窗内各模态帧按 `effective_time` 归槽，窗关闭时原子发布对齐组（`alignment_group_id`）。
- 窗超时未到的模态：**不等待、不补零**，发布部分对齐帧 + `Unknown(INSUFFICIENT_OBSERVATION)`；迟到信号以 revision 事件表达（新帧引用旧帧，envelope 不可变纪律）；**回溯深度 = 1 个对齐窗（Q-L02-03）**——超窗龄迟到记 `Unknown(INSUFFICIENT_OBSERVATION)` 留痕，不产历史帧改写。
- 对齐误差 = 各模态 `effective_time` 极差；超阈值降级 `alignment_confidence` 并记指标。

### 4.4 增益（gain）与增益回执（C2 核心）

- 增益来源两类：profile 静态增益、L05 `ModulationField` 动态调制。**统一上界** `gain_max[modality]`（frozen profile，**C2 冻结，Q-L02-02**——C0 期增益恒等 1.0、无调制入口，Q-G00-12③）。
- `applied_factor = clip(requested, 0, gain_max)`；越界即裁剪并记录 `bound_check=CLIPPED`（不报错、不静默）。
- **增益不改历史**：增益只作用于当期形成的特征缩放与精度权重，**禁止**回写已发布帧或改写 ReceivedSignal（HLD §6.2 禁止路径 `attention/affect/prediction → rewrite ReceivedSignal`）。
- 每帧必回 `GainReceipt`，使 evaluator 能复算"调制是否真的发生因果作用"（C2 退出条件：至少三类下游因果调制通过消融——增益是其中一类的载体）。
- affect ≠ reward ≠ command：增益指令是**有界调制**，不是行动命令；Sensorium 不因调制而改变是否形成（形成是无条件义务）。

### 4.5 感觉预测误差（层级化）

- `SensoryPrediction` 到达时以其 `valid_window` 绑定候选；形成完成后按模态+时间槽匹配，产出残差 `residual = formed_features − expected_features`（在声明的特征空间中）。
- `precision_weight` 来自预测方声明 × 当期质量估计；低质量帧的误差必须降权并携带 `Unknown(CALIBRATION_UNCERTAIN)`。
- 无匹配预测 → 只形成，不产误差（禁伪造"零误差"）；预测无匹配帧 → 由 L09/L04 处置，本档记 `Unknown(MISSING_SIGNAL)`。
- 误差**层级化**：本档只产感觉层分量；知觉层/模型层误差分别由 L03/L04 产生，三者不得互相顶替。

## 5. 时间尺度与调度挂点

| 级 | 挂点活动 |
|---|---|
| T1（每 cycle） | ingest → 形成 → 对齐窗推进 → 发布帧/回执；感觉运动预测的低层比较 |
| T2 | 向 L03/L05/L09 提供上一窗对齐组（读者自取，本档不在 T2 计算） |
| T6 | 校准漂移统计与形成质量长程汇总（仅产出证据，不改历史帧） |

- T0 期不含"感觉驱动反射"——MW0 期 containment 由 gateway/实验控制承担（L01 §5）；C0 后若引入 T0 反射，其触发必须来自已发布帧且经 L09 仲裁，禁止 Sensorium 直连执行（HLD §6.2）。
- 对齐窗跨 cycle 状态随 checkpoint 序列化；分支恢复后窗内容必须与谱系一致（L00 §3）。

## 6. 失败模式与 typed unknown

| 失败 | 类型化 | 行为 |
|---|---|---|
| 输入包 schema/provenance 不合法 | `SchemaViolation` | 拒绝形成；不产出"空帧"占位 |
| 模态信号缺失/窗超时 | `Unknown(MISSING_SIGNAL / INSUFFICIENT_OBSERVATION)` | 部分对齐发布 + 误差降权；禁补零 |
| 通道损坏标记 | `Unknown(CALIBRATION_UNCERTAIN)` + `corruption_flags` | 质量下调；证据侧留痕 |
| 校准版本与 profile 不符 | `CalibrationMismatch(expected, actual)` | fail closed，停止 claim-relevant 运行 |
| 增益越界 | `GainReceipt(bound_check=CLIPPED)` | 裁剪并记录；**不是**错误 |
| 形成超时 | `TimeoutEvent`（L00 §6.2 注入） | 当帧记 `Unknown(CAPABILITY_LIMIT)`；调度继续 |
| OOD 原始信号（特征越域） | `Unknown(OOD)` | 照常形成并标记；不推断、不丢弃 |
| 层级被下游篡改（检出） | `RepresentationEscalation(frame_id, claimed_level)` | S0：立即停止 + 废止证据 |

**纪律**：任何失败不得被改写为"主体没有感觉到"或"信号正常"。形成失败必须留 `Unknown` 并入 `state.unknowns`（L00 §6.1）；Sensorium 无权决定"忽略"。

## 7. 可测性（指标 / 对照 / 消融 / 保护集）

| 层 | 测试 | 断言 |
|---|---|---|
| unit | 时基归一、质量估计、增益裁剪、确定性算子 | 同输入同 digest |
| contract | 只接受 RECEIVED 入口；输出层级恒为 SENSORY_FORMED；FormationReceipt 必备字段完整 | schema 强制 |
| invariant | **接收质量 ≠ 真值概率**；帧不可改写（envelope 冻结构造）；`RawChannel → Perception` 直连在 import 图与运行时双检中均不存在 | 认识链 |
| deterministic replay | 同 (profile, seed, ReceivedSignal 序列) → 帧序列 bit-exact | M0/C0 |
| integration | 对齐窗部分到达、迟到 revision、跨模态一致性 | 无补零、无静默丢弃 |
| ablation | ① 移除增益回执 → C2 因果调制证据应缺失可检出；② 移除校准版本 → 校准漂移指标应失效；③ 旁路 Sensorium 直送知觉 → 权限测试应拒绝 | 选择性失败 |
| leakage | 形成特征与 WorldTruth 的未声明相关性（承 L01 §7）；telemetry 字段是否出现在 features 中 | 无 oracle 泄漏 |
| protection suite | 每门冻结的 MW0 形成回归场景在 C1+ 不退化 | E1 回归 |

**指标（进 HLD §13.2 有效指标）**：接收→形成延迟分布｜对齐误差与对齐成功率｜校准漂移｜**旁路率（必须恒为 0）**｜跨模态一致性｜ formation 失败率与 `Unknown` 分布｜增益越界裁剪率｜bit-exact 重放率=100%。

**无效指标（禁止作为进度证据）**：模态数量、帧吞吐、参数量。

## 8. 不变量与禁止写入路径

**本档专属不变量**：
1. `ReceivedSignal` 对全体主体模块只读且不可改写（含增益/注意/预测）；
2. Sensorium 输出的 `representation_level` 恒为 SENSORY_FORMED，且形成不产生信念/事实/目标/意图/归属；
3. 每帧必有完整溯源（`source_received_ids`）或显式 `Unknown`，禁匿名形成；
4. telemetry ≠ InteroceptiveSensation（内部事实必经声明通道 → 形成，禁直填）；
5. 增益有界、必回执、不改历史；
6. 形成义务无条件：调制不得使 Sensorium 跳过形成。

**禁止写入路径（本档强制，承 HLD §6.2）**：`Sensorium → fact/goal/intention/agency`｜`Sensorium → PerceptualBelief`｜`attention/affect/prediction → rewrite ReceivedSignal`｜`telemetry → InteroceptiveSensation`｜`Sensorium → subject memory`｜`Sensorium → 执行/gateway`｜`perception → raw channel`（本档拒绝为 L03 提供原始通道句柄）。

## 9. 引入门槛

- **C0**：≥2 外感受 + ≥1 内感受形成；五元属性齐全；FormationReceipt；raw-to-perception 旁路保护；确定性重放。
- **C1**：与 L03/L04 联动的多模态对齐与精度加权预测误差；OOD 标记；校准版本治理。
- **C2**：有界增益 + GainReceipt + 至少一类下游因果调制可经消融证明（增益路径）。
- **C4**：与 EfferenceCopy/SensoryPrediction 的感觉运动闭环（预测来自 L04/L09，比较在本档）。
- **C5**：设备/模态适配（新模态 = 新 `modality` 枚举 + 新校准版本 + 新 profile，不改本档合同）；保护集回退判据。
- **E1**：Sensorium/身体接口干预列入全模块 lesion 电池；六类核心决策路径中"构成/边界"与"连续性/恢复"的形成侧证据由本档回执承载。
- **P1**：物理传感必经 `PhysIO Bridge → Channel Adapter（L01）→ ReceivedSignal → 本档`，**不得**因物理来源而绕过形成（HLD §8）。

## 10. 实现清单（文件级）

```text
galatea/subject/sensorium/              # strict 类型
  ports.py            PortIn/PortOut 定义、层级常量断言
                      【C0 实现期首单元交付】SensoryModality 四类枚举 + C0SensoriumProfile
                      typed loader（load_c0_sensorium_profile，INC-11 纪律）+ SensoryFrame
                      （构造期 digest 强制重算核验——replace 篡改构造即拒，S0 面）+
                      GainState/QualityMetrics/四特征 dataclass
  ingest.py           【交付】RECEIVED 校验、schema/provenance/层级/kind↔载体匹配、
                      excluded_carriers 拒绝路径（Q-G00-12①）
  alignment.py        【交付】对齐窗、槽位归一、迟到 revision、alignment_group（Q-L02-03）
  form_extero.py      【交付】外感受形成算子（EXT_LOCAL_OBS 观测窗 + EXT_EVENT 事件观测面）
  form_intero.py      【交付】内感受形成（Q-L02-05 四 sensation + energy_rate 派生差分，零新阈值）
  form_proprio.py     【交付】本体感受形成（orientation；位置不下发 Q-L01-09⑥）
  calibration.py      【交付】CalibrationVersion 绑定/digest/漂移统计（c0-static-v1，Q-G00-12②）
  quality.py          【交付】QualityMetrics、completeness/损坏标记/OOD 标记（Q-G00-12④）
  gain.py             【交付】C0 恒等增益 + GainReceipt + 调制入口即拒（Q-G00-12③）
  pred_error.py       【交付】C0 合同面：无预测源 → 不产误差（禁伪造零误差；C1/C4 接线）
  receipt.py          【交付】FormationReceipt 构造与发布（digest 双绑定、完整性 fail-closed）
  unknowns.py         【交付】本档 Unknown 产生点（MISSING_SIGNAL/INSUFFICIENT/
                      CALIBRATION_UNCERTAIN/OOD，统一走 L00 类型）
  pipeline.py         【C0 补录件（REV-0011 R2 后首单元）】SensoriumPipeline 装配面：
                      process_cycle（T1：ingest→对齐→三面形成→校准→增益→发布）+ audit
                      （无帧无回执/增益回执逐帧绑定/digest 失配——消融检出面）
galatea/subject/sensorium/tests/
  conftest.py         【C0 补录件】测试装置：真实通道 schema 同构的 RECEIVED 包构造 +
                      run_full_stream（extero 延迟 1 + W=4 窗关闭语义）
  test_determinism.py test_alignment_partial.py test_gain_bound.py
  test_no_bypass.py(权限) test_level_escalation.py test_receipt_completeness.py
  test_intero_no_telemetry.py test_ablation_gain_receipt.py        # 八件全绿（C0 实现期首单元）
config/profiles/
  c0_sensorium.profile.yaml   【已冻结 v1.0，ADR-G-0011 + tag c0-freeze】模态集/W_align/
                              内感受四 sensation/校准版本/增益形态/质量度量纲（Q-L02-03/-05/Q-G00-12）
```

## 11. 未决问题（→ open_questions.md）

| Q 号 | 问题 | 依赖 | 状态 |
|---|---|---|---|
| Q-L02-01 | 校准版本策略：单版本冻结 vs 允许受控漂移（漂移是否需 revision 谱系） | C1 | CONFIRMED（AI-v2 2026-10-03，见 A 区） |
| Q-L02-02 | `gain_max[modality]` 默认上界与裁剪是否计入"调制有效性"判据 | C2 | UNCONFIRMED |
| Q-L02-03 | 对齐窗 `W_align` 默认值（建议 4 cycles）与迟到 revision 的最大回溯深度 | C0/C1 | CONFIRMED（AI-v2 2026-10-02：W_align = 4 cycles（T3 对齐，覆盖通道延迟上界 3 倍余量）+ 迟到回溯 = 1 窗（超窗龄 = Unknown(INSUFFICIENT_OBSERVATION) 留痕，禁历史帧改写），见 open_questions A 区） |
| Q-L02-04 | 质量估计量纲与跨模态可比性（是否需归一到统一 [0,1] 精度标度） | C1 | CONFIRMED（AI-v2 2026-10-03，见 A 区） |
| Q-L02-05 | 内感受模态的最小集与"损伤事件"离散化阈值（联动 Q-L01-08、L05 驱力） | C0 | CONFIRMED（AI-v2 2026-10-02：C0 内感受最小集四 sensation——energy_level/integrity_level（连续 [0,1]）+ damage_event/energy_depleted（离散，零新阈值：Q-L01-08 世界侧离散化 + Q-L01-09⑤ 锁存）；energy_rate = 派生差分非独立 sensation，见 A 区） |
| Q-L02-06 | 感觉层预测误差的特征空间定义（MW0 期是否直接用网格观测向量） | C1 | CONFIRMED（AI-v2 2026-10-03，见 A 区） |
| Q-L02-07 | C5 新模态适配是否需独立 protection 场景（防适配破坏既有模态） | C5 | UNCONFIRMED |
