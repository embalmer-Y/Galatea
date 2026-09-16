# Galatea 未决问题登记册（open_questions）

> v1.1 · 2026-09-13 · 状态：ACTIVE
> 用途：汇总 HLD/LLD 中所有标注 UNCONFIRMED 的参数、默认值与待裁决项。**任何 Q 号未经 owner 裁决，不得进入 frozen profile、不得作为门退出依据、不得写入代码常量。**
> 裁决流程：owner 回复 Q 号 + 决定 → 本档改为 CONFIRMED（附日期）→ 同步修订对应 HLD/LLD 章节 → 门冻结时写入 frozen profile。
>
> **分区索引**：A 已裁决存档 · B 全局（G）· C L00 · D L01 · E L02 · F L03 · G L04 · H L05 · I L06 · J L07 · K L08 · L L09 · M L10 · N L11 · O L12 · P L13 · Q 跨档联动与 F0 阻断清单
> 另：开发流程域 Q-DEV 系列与标识符治理域 Q-ID 系列登记于仓库根 `DEV_SPEC.md`（附录 D / §13）。
> **规模**：CONFIRMED 19 项；UNCONFIRMED 114 项（G 5 + L00 6 + L01 8 + L02–L13 95）；CLOSED 1 项（Q-L00-03，编号不复用）。

## A. 已裁决项（存档，CONFIRMED）

| Q 号 | 议题 | 裁决 | 日期 |
|---|---|---|---|
| Q-T01 | 语言 Python 3.12 | 接受；pin 补丁版；固定 PYTHONHASHSEED；主体平面禁线程 | 2026-09-12 |
| Q-T02 | PyTorch + 三层纪律 | 接受；CPU-pinned；NeuralModule 统一接口；禁自持 RNG/时钟；C1 前禁非确定性 op | 2026-09-12 |
| Q-T03 | dataclass envelope + Pydantic payload | 接受；envelope=frozen slots dataclass；payload=Pydantic v2；禁 TypedDict | 2026-09-12 |
| Q-T04 | 自研确定性协作调度器 | 接受；只读 envelope 不读 payload；tie-break (due, t_level, module_id, seq)；拒 asyncio/SimPy/Ray | 2026-09-12 |
| Q-T05 | SQLite 三库分离 | 接受；subject_state/subject_memory/registry；WAL；branch=谱系非复制 | 2026-09-12 |
| Q-T06 | Parquet + DuckDB/Polars | 接受；Polars 仅写侧；Parquet 唯一证据载体；DuckDB 只读复算 | 2026-09-12 |
| Q-T07 | pytest + Hypothesis + ReplayTest/LeakageProbe | 接受；property-based 覆盖不变量 | 2026-09-12 |
| Q-T08 | pyright 分级 strict + uv lock --require-hashes | 接受 | 2026-09-12 |
| Q-T09 | 自研 content-addressed registry | 接受；~500 行；拒 MLflow/W&B/DVC；外部仓库仅作依赖源 | 2026-09-12 |
| Q-T10 | 数值纪律 | 接受；模型 float32、证据/统计 float64；版本入 manifest | 2026-09-12 |
| Q-T11 | counter-based RNG 流派生 | 接受；禁全局 RNG | 2026-09-12 |
| Q-T12 | virtual_time 唯一时间源 | 接受；墙钟仅 recorder manifest 独立字段 | 2026-09-12 |
| Q-C01 | LLD 粒度 | 14 档 L00–L13，一模块一档，11 节模板 | 2026-09-12 |
| Q-C02 | 顶层词汇 | 只用卡片模块词汇；废弃 S1–S6 | 2026-09-12 |
| Q-C03 | 阶段 0 蓝图地位 | 保留为 MW0，写入 L01，D1–D7 重映射门体系 | 2026-09-12 |
| Q-C04 | 参数初值策略 | 建议默认值 + UNCONFIRMED + Q 号 | 2026-09-12 |
| Q-C05 | 卡片处置 | 归档 design/archive/；HLD/LLD 升 normative | 2026-09-12 |
| Q-C06 | 交付节奏 | 先交 HLD+L00+L01 确认风格，再批量 L02–L13 | 2026-09-12 |
| Q-N01 | 术语 HIO → PhysIO | HIO 系 Helios I/O 缩写，项目更名后废弃；全库（含 archive）统一为 PhysIO（Physical I/O）；派生标识符 PhysIO Bridge / PhysIOControlGraph | 2026-09-12 |

## B. 全局未决（G 系列）

| Q 号 | 议题 | 建议默认 | 依赖 | 状态 |
|---|---|---|---|---|
| Q-G00-01 | **（指针，非独立登记项）** T0–T6 频率——所有权在 **Q-L00-01**（L00 §5 比例 N2/N3/N4/N5=2/4/16/64）；本行仅当基准 cycle→墙钟绝对时基需裁决时启用 | — | F0 profile 冻结 | 见 Q-L00-01 |
| Q-G00-02 | **（指针，非独立登记项）** MW0 观测窗与边界——所有权在 **Q-L01-01**（egocentric 5×5 + 衰减）与 **Q-L01-02**（torus vs 墙） | — | M0 | 见 Q-L01-01 / Q-L01-02 |
| Q-G00-03 | 团队规模与总工期假设（10-14 人 / 25-38 月） | 卡片原值 | 仅规划参考 | UNCONFIRMED |
| Q-G00-04 | 六类核心决策路径的完整枚举文本 | 卡片摘要（连续性/构成边界/目标规范自主/行动委托权限/学习适应/viability 资源风险）+ 十种路径类型 | F0 | UNCONFIRMED |
| Q-G00-05 | 持续极端 aversive-like 状态的伦理评审阈值与处置（暂停/调整/终止） | 触发即暂停 claim-relevant 运行 + 人工评审 | E1 前 | UNCONFIRMED |
| Q-G00-06 | 完整实验对象符号系 `W/O/S/C/G/R/D/A*/A/Ä/Y/Ŷ/Z` 与 M1 时序记号 `S_t/Q_t/G_t/R_t/D_t/A_t*/Z_t+1` 的完整映射（原文不可得；HLD §4.4 仅重建了 W/O、A/Ä、Y/Ŷ 最小集） | HLD §4.4 重建释义 | F0（术语/对象图合同） | UNCONFIRMED（阻塞 F0 符号合同冻结） |
| Q-G00-07 | 门链中 **"E0"**（L13 §1"→ E0→E1→H1"与 Q-L13-02 依赖列"F0/E0"两处引用）在全库无定义：owner 须裁决其定义（推测为 C5 与 E1 之间的 sealed 评价准备期）或从文档中剔除并修正引用 | — | F0（门体系合同） | UNCONFIRMED（2026-09-17 DEV_SPEC 设立时登记，见根 DEV_SPEC §13） |

## C. L00 横切基础

| Q 号 | 议题 | 建议默认 | 状态 |
|---|---|---|---|
| Q-L00-01 | T3/T4/T5/T6 频率比 N2/N3/N4/N5 | 2/4/16/64 | UNCONFIRMED |
| Q-L00-02 | UnknownReason 冻结清单增删 | 现 9 项（MISSING_SIGNAL/CALIBRATION_UNCERTAIN/SOURCE_AMBIGUOUS/OOD/CONFLICTING_EVIDENCE/INSUFFICIENT_OBSERVATION/CAPABILITY_LIMIT/ATTRIBUTION_UNRESOLVED/DECISION_PATH_UNRESOLVED） | UNCONFIRMED |
| ~~Q-L00-03~~ | ~~float64 统一是否接受存储/性能代价~~ **CLOSED**：与 Q-T10 裁决（模型 float32、证据/统计 float64，2026-09-12 CONFIRMED）重复且措辞冲突，已废弃归并入 Q-T10；编号不复用 | — | CLOSED |
| Q-L00-04 | RNG 算法 ChaCha8 vs Philox | ChaCha8 | UNCONFIRMED |
| Q-L00-05 | checkpoint 频率策略 | 每 T6 + 关键事件触发 | UNCONFIRMED |
| Q-L00-06 | registry 大 artifact 分片阈值 | 8 MiB 分片 | UNCONFIRMED |
| Q-L00-07 | Hypothesis packet 序列生成分布 | 谱系感知 + 对抗混合 | UNCONFIRMED |

## D. L01 环境与通道

| Q 号 | 议题 | 建议默认 | 状态 |
|---|---|---|---|
| Q-L01-01 | egocentric 观测窗大小与衰减函数 | 5×5，线性距离衰减 | UNCONFIRMED |
| Q-L01-02 | MW0 边界 torus vs 墙 | torus | UNCONFIRMED |
| Q-L01-03 | 三 regime 参数化及与 L05 情感模式对应 | abundance/scarcity/volatile；对应待 L05 | UNCONFIRMED |
| Q-L01-04 | regime 最小驻留 N6 | 256 cycles | UNCONFIRMED |
| Q-L01-05 | no-op/sham 归属判别冻结最小效应量与样本量 | 待 M0 统计计划（L13） | UNCONFIRMED |
| Q-L01-06 | **旧 D1–D7 验收原文不可得**；L01 §4.6 重映射为重建稿 | owner 逐条确认或提供原文 | UNCONFIRMED（阻塞 frozen profile） |
| Q-L01-07 | M1 是否引入第二可控代理（伪社会线索） | 推迟到 C4 | UNCONFIRMED |
| Q-L01-08 | energy/integrity viability 阈值与损伤事件定义 | 联动 L05 驱力 | UNCONFIRMED |

## E. L02 感觉形成（Sensorium）

| Q 号 | 议题 | 建议默认 | 依赖 | 状态 |
|---|---|---|---|---|
| Q-L02-01 | 校准版本策略：单版本冻结 vs 允许受控漂移（漂移是否需 revision 谱系） | — | C1 | UNCONFIRMED |
| Q-L02-02 | `gain_max[modality]` 默认上界与裁剪是否计入"调制有效性"判据 | — | C2 | UNCONFIRMED |
| Q-L02-03 | 对齐窗 `W_align` 默认值与迟到 revision 的最大回溯深度 | 4 cycles | C0/C1 | UNCONFIRMED |
| Q-L02-04 | 质量估计量纲与跨模态可比性（是否需归一到统一 [0,1] 精度标度） | — | C1 | UNCONFIRMED |
| Q-L02-05 | 内感受模态最小集与"损伤事件"离散化阈值 | — | C0；联动 Q-L01-08 | UNCONFIRMED |
| Q-L02-06 | 感觉层预测误差的特征空间定义（MW0 期是否直接用网格观测向量） | — | C1 | UNCONFIRMED |
| Q-L02-07 | C5 新模态适配是否需独立 protection 场景（防适配破坏既有模态） | — | C5 | UNCONFIRMED |

## F. L03 知觉（Perception）

| Q 号 | 议题 | 建议默认 | 依赖 | 状态 |
|---|---|---|---|---|
| Q-L03-01 | 置信度标度形式（直接概率 vs logit vs 离散档）与跨模态可比性 | [0,1] 概率 | C1 | UNCONFIRMED |
| Q-L03-02 | `believe_threshold` 与 OOD 阈值默认值；abstain 是否分级（部分承诺） | — | C1 | UNCONFIRMED |
| Q-L03-03 | MW0 表格融合的先验 π 与似然表构造方式（手算可复核 vs 由 L01 dynamics 表导出） | — | C1 | UNCONFIRMED |
| Q-L03-04 | 校准达标判据（ECE 阈值、分箱策略、最小样本量） | — | C1；联动 Q-L13-01 | UNCONFIRMED |
| Q-L03-05 | 多假设保留数量上限与塌缩条件（何时必须收敛为单信念） | — | C1/C2 | UNCONFIRMED |
| Q-L03-06 | affordance 的 `action_class` 枚举与 L09/L10 能力契约的对齐方式 | — | C3/C4 | UNCONFIRMED |
| Q-L03-07 | C1+ 神经 encoder 替换表格融合时的等价性验证方法（防"换实现即换主张"） | — | C1 | UNCONFIRMED |

## G. L04 世界/身体/自我模型

| Q 号 | 议题 | 建议默认 | 依赖 | 状态 |
|---|---|---|---|---|
| Q-L04-01 | rollout 深度/宽度上界默认值与超预算裁剪策略 | ≤8 / ≤4 | C1 | UNCONFIRMED |
| Q-L04-02 | 世界信念更新率与多假设保留上限 | — | C1；联动 Q-L03-05 | UNCONFIRMED |
| Q-L04-03 | 身体纳入三判据的冻结阈值与最小效应量 | — | C1；联动 Q-L13-09 | UNCONFIRMED |
| Q-L04-04 | 自我预测误差的维度定义与时间常数 | — | C1/C2；联动 Q-L05-* | UNCONFIRMED |
| Q-L04-05 | `CapabilityEstimate` 的 action_class 粒度 | — | C3/C4；联动 Q-L03-06 | UNCONFIRMED |
| Q-L04-06 | 连续性 gap 的最大可接受数量与"伪更新"判定边界 | — | M2 | UNCONFIRMED |
| Q-L04-07 | C1+ 神经世界模型替换表格模型的等价性/泄漏验证方法 | — | C1；同源 Q-L03-07 | UNCONFIRMED |

## H. L05 驱力/评价/情感（九维动力学）

| Q 号 | 议题 | 建议默认 | 依赖 | 状态 |
|---|---|---|---|---|
| Q-L05-01 | 九维的取值域与量纲（[0,1] vs [-1,1]，valence 是否对称）与跨维可比性 | — | C2 | UNCONFIRMED |
| Q-L05-02 | 内稳态误差权重 `w_d` 默认值与是否允许 appraisal 有界动态调整（幅度上界） | — | C2 | UNCONFIRMED |
| Q-L05-03 | 各维时间常数 τ、迟滞带宽、衰减率的默认谱 | — | C2；联动 Q-L00-01 | UNCONFIRMED |
| Q-L05-04 | MW0 三 regime 与"3 情感模式"的对应参数化 | — | C2；**须与 Q-L01-03 一致裁决** | UNCONFIRMED |
| Q-L05-05 | 持续极端 aversive-like 状态的触发阈值与持续时长 | — | E1 前（伦理）；**须与 Q-G00-05 一致** | UNCONFIRMED |
| Q-L05-06 | `tendencies.action_class` 枚举 | — | C3/C4；联动 Q-L03-06、Q-L04-05 | UNCONFIRMED |
| Q-L05-07 | anti-reward-collapse 检验的统计量与阈值（"九维不可被单维线性重构"的拟合优度门限） | — | C2/E1；联动 Q-L13-09 | UNCONFIRMED |
| Q-L05-08 | `social_relevance` 在 C4 后由 L12 供给线索的最小定义（避免伪造社会情感） | 恒 Unknown（D-14 单主体期） | C4 | UNCONFIRMED |

## I. L06 记忆（八子系统）

| Q 号 | 议题 | 建议默认 | 依赖 | 状态 |
|---|---|---|---|---|
| Q-L06-01 | 八子系统的容量上界与溢出策略（拒写 / 强制巩固 / 降级 ARCHIVED） | — | C2 | UNCONFIRMED |
| Q-L06-02 | 检索打分权重 α/β/γ/δ/ε 默认值与是否受 L05 有界调制 | — | C2 | UNCONFIRMED |
| Q-L06-03 | 各子系统衰减 τ 谱与访问增强上限 | — | C2/C5 | UNCONFIRMED |
| Q-L06-04 | 巩固窗口触发条件（每 T6 / 强度阈 / 重放选中）与抽象的聚类粒度 | — | C5 | UNCONFIRMED |
| Q-L06-05 | 保护集构成规则（谁标 PROTECTED、最小集内容、可否被 promotion 扩容） | — | C5/E1；联动 Q-L11-04 | UNCONFIRMED |
| Q-L06-06 | RECALLED/PERCEIVED 混淆率的测量协议与可接受上限 | — | C2/E1 | UNCONFIRMED |
| Q-L06-07 | tombstone 保留期与库体积治理 | — | C5/H1；联动 Q-L00-06 | UNCONFIRMED |
| Q-L06-08 | procedural 记忆向 L09 提案的接口形式（防"经验变权限"） | — | C3/C5 | UNCONFIRMED |

## J. L07 工作空间（递归全局工作空间）

| Q 号 | 议题 | 建议默认 | 依赖 | 状态 |
|---|---|---|---|---|
| Q-L07-01 | 容量 K 默认值与是否按模态/子系统分配子配额 | K=4 | C2 | UNCONFIRMED |
| Q-L07-02 | 竞争权重 `w_c` 五项默认值及 L05 调制因子上界 | — | C2 | UNCONFIRMED |
| Q-L07-03 | `ReadReceipt` 超时（cycles）与缺失回执的处置（重试/降级/指标） | — | C2 | UNCONFIRMED |
| Q-L07-04 | 递归深度上界 `depth_max` 与去重 TTL | depth=3 | C2 | UNCONFIRMED |
| Q-L07-05 | "分离模块"的形式定义（哪些模块对算 separated；同模块内分区是否算） | — | C2/E1 | UNCONFIRMED |
| Q-L07-06 | 预注册 watch point 的最小集合与新增流程（profile 变更 vs 冻结合同） | — | C2/E1 | UNCONFIRMED |
| Q-L07-07 | `effective_access` 的统计判据（是否需最小效应量） | — | E1；联动 Q-L13-09 | UNCONFIRMED |

## K. L08 动机/目标（M1 最小 → C3 完整）

| Q 号 | 议题 | 建议默认 | 依赖 | 状态 |
|---|---|---|---|---|
| Q-L08-01 | M1 期承诺检查清单最小集（C-1/C-2/C-5/C-7 是否足够；C-4 规范溯源是否延至 C4） | — | M1 | UNCONFIRMED |
| Q-L08-02 | 候选 TTL 默认值与每 cycle 候选数上界（防候选爆炸） | — | M1/C3 | UNCONFIRMED |
| Q-L08-03 | Pareto 仲裁的多目标向量分量定义与默认权重 | — | C3 | UNCONFIRMED |
| Q-L08-04 | front 内优先序（viability > 规范 > 承诺 > 其余？）是否成立及例外条件 | — | C3；联动 Q-L09-02 | UNCONFIRMED |
| Q-L08-05 | 真实理由/伪理由检验的最小效应量与样本量 | — | M1；同源 Q-L01-05，汇总于 Q-L13-09 | UNCONFIRMED |
| Q-L08-06 | 措辞操纵实验的操纵集设计（多少种措辞/请求者身份组合才具说服力） | — | M1 | UNCONFIRMED |
| Q-L08-07 | 规范（NORM）来源的可接受 derivation 形式（哪些算"可溯"） | — | C3/C4 | UNCONFIRMED |
| Q-L08-08 | 长期目标（跨 episode）的最大寿命与"不可复活"的例外（如同名新目标） | — | C5 | UNCONFIRMED |

## L. L09 控制器/元控制

| Q 号 | 议题 | 建议默认 | 依赖 | 状态 |
|---|---|---|---|---|
| Q-L09-01 | 仲裁权重 ω_g/ω_c/ω_cost/ω_u/ω_a 默认值与 affect_factor 上界 | — | C3 | UNCONFIRMED |
| Q-L09-02 | 五类控制器优先级偏序是否成立及例外条件 | — | C3；联动 Q-L08-04 | UNCONFIRMED |
| Q-L09-03 | 五类元决策的触发阈值（尤其 `loss_of_control` 的窗长 L_c 与误差阈值） | — | C3/C4 | UNCONFIRMED |
| Q-L09-04 | metacontrol 最小驻留（cycles）与抖动锁定策略 | — | C3 | UNCONFIRMED |
| Q-L09-05 | 在线适应 `adaptive_gain` 的允许范围与"何时必须走 promotion"的边界 | — | C5；联动 Q-L11-* | UNCONFIRMED |
| Q-L09-06 | Reflex 控制器在 MW0/C0 期是否启用（L01 §5 称 containment 由 gateway/实验控制承担；若启用需白名单刺激定义） | MW0 期禁用 | C0/C3；联动 Q-L10-09 | UNCONFIRMED |
| Q-L09-07 | `SEEK_HELP` 在单主体（D-14）期的对象定义（人类研究者？实验控制？）与其权限边界 | — | C3/C4；联动 Q-L12-08 | UNCONFIRMED |
| Q-L09-08 | 三层预测误差的相对权重与是否允许跨层归一 | — | C1/C3；联动 Q-L02-06、Q-L03-01 | UNCONFIRMED |

## M. L10 行动/网关/PhysIO/归属

| Q 号 | 议题 | 建议默认 | 依赖 | 状态 |
|---|---|---|---|---|
| Q-L10-01 | budget 默认值体系（每类动作的次数/资源配额）与 MW0 期是否设硬配额 | — | F0/M0 | UNCONFIRMED |
| Q-L10-02 | idempotency 窗口长度（cycles）与跨分支的键作用域 | — | M0 | UNCONFIRMED |
| Q-L10-03 | L0–L5 各级的精确定义、每级所需授权组合与升降级条件 | passive→calibration→shadow→limited→active | P1（schema 在 F0 冻结） | UNCONFIRMED |
| Q-L10-04 | 归属六类判定的证据规则阈值（残差阈、时间约束、后验校准门限） | — | M1/C4 + L13 统计计划 | UNCONFIRMED |
| Q-L10-05 | 概率 agency 后验的计算形式与校准判据 | — | C4；同源 Q-L03-04 | UNCONFIRMED |
| Q-L10-06 | 四类授权模板（字段、批准者标识、撤销路径、重授权流程） | — | P1（前置 F0 schema） | UNCONFIRMED |
| Q-L10-07 | gateway policy 更新流程（promotion + 重授权 + 审计）与"重大变化"的判定 | — | C5/H1 | UNCONFIRMED |
| Q-L10-08 | 急停响应时间上界与在途命令的终止语义（部分执行如何处理） | — | P1/H1 | UNCONFIRMED |
| Q-L10-09 | MW0 期 Reflex 与 T0 硬保护的职责分界，避免 containment 双写 | — | C0；联动 Q-L09-06 | UNCONFIRMED |

## N. L11 学习/巩固

| Q 号 | 议题 | 建议默认 | 依赖 | 状态 |
|---|---|---|---|---|
| Q-L11-01 | 三层可塑性的学习率谱（在线适应步长上界、adapter 秩/步长、巩固批大小） | — | C1/C5 | UNCONFIRMED |
| Q-L11-02 | replay 选择策略默认权重（情感标注/新颖性/误差/时间多样性）与 budget 默认 | — | C5 | UNCONFIRMED |
| Q-L11-03 | promotion 判据的多目标组合形式（Pareto + 保护硬约束）与最小改善阈值 | — | C5；联动 Q-L13-07 | UNCONFIRMED |
| Q-L11-04 | 保护集回退判定阈值（delta 显著性/效应量） | — | C5/E1；联动 Q-L06-05 | UNCONFIRMED |
| Q-L11-05 | 二阶纠偏"可区分性"的形式判据（data_scope 差异度量） | — | C5/M2 | UNCONFIRMED |
| Q-L11-06 | 在线适应是否需持久化（checkpoint 内参数）或仅运行期有效（重启复位） | — | C1/C5 | UNCONFIRMED |
| Q-L11-07 | `metrics_snapshot` 的标准指标集（跨档统一，供 L13 评价复用） | — | F0/C5 + L13 | UNCONFIRMED |
| Q-L11-08 | 灾难性遗忘保持率的冻结阈值与回归场景最小集 | — | C5/E1 | UNCONFIRMED |

## O. L12 语言/社会认知

| Q 号 | 议题 | 建议默认 | 依赖 | 状态 |
|---|---|---|---|---|
| Q-L12-01 | C4 期 typed LLM 角色的最终清单与是否全部启用（R-TRANSLATE 是否保留） | 8 角色（§4.1 表） | C4 | UNCONFIRMED |
| Q-L12-02 | 权限矩阵的粒度（角色级 vs 角色×内容类型级）与例外审批流程 | — | C4/F0 | UNCONFIRMED |
| Q-L12-03 | LLM 非确定性处理：录制回放模式是否为 claim-relevant 运行的**唯一**允许方式（在线调用仅探索用） | — | C4 + L00 | UNCONFIRMED |
| Q-L12-04 | 他者模型最小集字段（存在/意图/知识/承诺）与 D-14 单主体期的封锁范围 | — | C4 | UNCONFIRMED |
| Q-L12-05 | 自我报告一致性判定的比较对象与阈值；DIVERGENT 的处置 | — | C4/E1 | UNCONFIRMED |
| Q-L12-06 | 语言陈述作为 L03 低置信线索的置信度上限（防"听说即相信"） | — | C4 + L03 | UNCONFIRMED |
| Q-L12-07 | 中央 LLM 消融的"非语言核心功能保持"判据阈值（保持率下限） | — | C4/E1 + L13 | UNCONFIRMED |
| Q-L12-08 | 求助对象定义与其权限边界 | — | C3/C4；联动 Q-L09-07 | UNCONFIRMED |

## P. L13 证据/评价/registry 治理

| Q 号 | 议题 | 建议默认 | 依赖 | 状态 |
|---|---|---|---|---|
| Q-L13-01 | 冻结统计计划模板的最小必备字段集与多重比较校正默认策略 | — | F0 | UNCONFIRMED |
| Q-L13-02 | sealed 分割策略（比例、隔离层级、token 机制）与"不回流同一候选"的机械判据 | — | F0/E0 | UNCONFIRMED |
| Q-L13-03 | `EvidenceResult` 与 `ExpansionDecision` 的签发者分离形式（人/角色/工具）与记录格式 | — | R0 | UNCONFIRMED |
| Q-L13-04 | `core_decision_registry` 六类路径的**全枚举**与十类路径的定稿（含 `unresolved_paths[]`/分母闭合判据） | L13 §4.7 初版 6×10 矩阵 | **Q-G00-04**（owner 裁定）→ E1 | UNCONFIRMED（**阻断 E1**） |
| Q-L13-05 | leakage 探针的 14 条路径逐条实现形式（静态契约 vs 运行时钩子 vs 数据查询的分工） | — | C0+ | UNCONFIRMED |
| Q-L13-06 | 保护集"只增不减"的退役裁定流程与回退阈值 | — | C5/E1；联动 Q-L11-04、Q-L06-05 | UNCONFIRMED |
| Q-L13-07 | promotion 多目标判据的组合形式与最小改善阈 | — | C5；联动 Q-L11-03 | UNCONFIRMED |
| Q-L13-08 | I2/I3 的"独立"标准（实现者/环境/seed 隔离程度）与一致性判据 | — | E1/H1 | UNCONFIRMED |
| Q-L13-09 | 最小可辨效应量的**统一登记**（汇总 Q-L01-05 / Q-L08-05 / Q-L10-04 / Q-L03-04 / Q-L05-07 / Q-L04-03 / Q-L07-07） | — | F0/R0 | UNCONFIRMED |
| Q-L13-10 | 静态报告的最小集与导出频率（只读、无服务化） | — | H1 | UNCONFIRMED |

## Q. 跨档联动与 F0 阻断清单（裁决时须成组处理）

**必须成组裁决的联动对**：

| 组 | Q 号 | 联动原因 |
|---|---|---|
| 时基谱 | Q-L00-01 ↔ Q-L05-03 | 情感时间常数依赖 T 级频率比 |
| regime ↔ 情感模式 | Q-L01-03 ↔ Q-L05-04 | 同一参数化在两处出现 |
| 伦理阈 | Q-G00-05 ↔ Q-L05-05 | owner 裁决必须同时覆盖 |
| 能力粒度 | Q-L03-06 ↔ Q-L04-05 ↔ Q-L05-06 | `action_class` 枚举三处共用 |
| 误差标度 | Q-L02-06 ↔ Q-L03-01 ↔ Q-L09-08 | 三层误差比较需共同标度 |
| Reflex 边界 | Q-L09-06 ↔ Q-L10-09 | containment 不得双写 |
| 求助对象 | Q-L09-07 ↔ Q-L12-08 | 单主体期的权限边界 |
| 保护集 | Q-L06-05 ↔ Q-L11-04 ↔ Q-L13-06 | 保护集构成、阈值、治理一体 |
| promotion 判据 | Q-L11-03 ↔ Q-L13-07 | 多目标判据与统计阈值 |
| 分片与治理 | Q-L00-06 ↔ Q-L06-07 | tombstone 保留依赖 registry 分片 |

**F0 冻结的直接阻断项**（未裁决则 frozen profile 无法完成）：
- **Q-L01-06**（D1–D7 → MW0-SC1…SC6 重映射为重建稿，需 owner 逐条确认或提供原文）
- **Q-G00-06**（实验对象符号系原文不可得；HLD §4.4 仅重建最小集）
- **Q-G00-04 → Q-L13-04**（六类决策路径全枚举；同时阻断 E1）
- F0 合同级 schema 依赖：Q-L10-01/-03/-06、Q-L11-07、Q-L12-02、Q-L13-01/-02/-09

**M0/M1 阻断项**：Q-L01-01…05、Q-L09-06、Q-L10-01/-02/-04、Q-L08-01/-05/-06
