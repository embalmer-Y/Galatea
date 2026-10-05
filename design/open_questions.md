# Galatea 未决问题登记册（open_questions）

> v1.2 · 2026-09-23 · 状态：ACTIVE
> 用途：汇总 HLD/LLD 中所有标注 UNCONFIRMED 的参数、默认值与待裁决项。**任何 Q 号未经裁决，不得进入 frozen profile、不得作为门退出依据、不得写入代码常量。**
> 裁决流程（authority v2，DEV_SPEC §4.6，2026-09-23 起）：裁决由开发 AI 成文作出（背景/选项/选择/影响/重开条件；裁决者标识 **AI-v2**；2026-09-23 前为 owner 裁决）→ 本档改为 CONFIRMED（附日期与裁决者）→ 同步修订对应 HLD/LLD 章节 → 门冻结时写入 frozen profile。owner 否决权保留。
>
> **分区索引**：A 已裁决存档 · B 全局（G）· C L00 · D L01 · E L02 · F L03 · G L04 · H L05 · I L06 · J L07 · K L08 · L L09 · M L10 · N L11 · O L12 · P L13 · Q 跨档联动与 F0 阻断清单
> 另：开发流程域 Q-DEV 系列与标识符治理域 Q-ID 系列登记于仓库根 `DEV_SPEC.md`（附录 D / §13）。
> **规模**：CONFIRMED 90 项（A 区 90 行实点）；UNCONFIRMED 57 项（G 2 + L00 2 + L01 1 + L02–L13 52，分区行实点）；CLOSED 1 项（Q-L00-03，编号不复用）。计数纪律：已裁行从分区**移除**（仅存 A 区），头部计数以分区行机械实点为准（INC-09/R11 教训）。本批（C1 实现期首单元）：Q-L04-09/-10/-11 新增即裁（REV-0013 R4 前置——世界模型转移语义批：转移语义/适应初始化/先验 regime 语义）。

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
| Q-G00-07 | 门链 "E0" 处置 | **方案 A 剔除**：E0 系 L13 撰写期草稿残留、非门；全库仅 2 处引用（L13 §1 头部、Q-L13-02 依赖列）已修正；门链维持 F0→M0→M1→M2→R0→C0–C5→E1→H1→物理授权→P1 不变；sealed 准备工作归属不变（策略冻结在 F0，执行在 R0/promotion/E1） | 2026-09-17 |
| Q-L01-06 | 旧 D1–D7 验收原文不可得；L01 §4.6 重映射为重建稿，无人可提供原文供确认 | **AI-v2：采纳重建映射为规范文本**；原文判定永久不可得，验收约束力由门退出判据承载（L01 §9 + L13 EvidenceResult），映射表降为溯源记录。重开条件：原文若现身，一 session 内复审 | 2026-09-23 |
| Q-T13 | 冻结 YAML 配置（decision_path_matrix/stat_plan_templates 等，config/evidence/**）的运行时解析器选型 | **AI-v2：PyYAML**（safe_load；types-pyyaml 开发态类型支持；uv.lock 哈希锁定，Q-T08）——stdlib 无 YAML；结构简单的自写解析器是伪节省。重开条件：出现 PyYAML 无法满足的性能/安全需求时经新 Q 号评估 ruamel/自定义 | 2026-09-23 |
| Q-L00-01 | T3–T6 频率比 N2/N3/N4/N5 默认值（f0_l00.profile 冻结前置；ACT-07 执行中发现此 Q 此前漏列 F0 阻断清单） | **AI-v2：2/4/16/64 采纳为初值**——2 的幂梯使 T3–T6 在 64-cycle 公倍点精确对齐（跨级同拍可复算）；定位为 profile 参数，M0 实测复核。重开条件：M0 显示某级频率成为行为瓶颈或公倍对齐无实测价值 | 2026-09-23 |
| Q-L00-02 | UnknownReason 冻结清单增删（f0_l00.profile 冻结前置，同上漏列） | **AI-v2：冻结清单 = 现 9 项 + STREAM_MISSING 共 10 项**（L00 §6.2 失败类型化所需）；增删 = schema 版本升级而非原地改。重开条件：任一门证据出现无法归入现有 10 项的不确定性形态，经新 Q 号扩充 | 2026-09-23 |
| Q-G00-06 | 实验对象符号系全集映射原文不可得；HLD §4.4 仅重建 W/O、A/Ä、Y/Ŷ 最小集 | **AI-v2：HLD §4.4 最小集即为 F0 符号合同**；未重建符号（S/C/G/R/D/Z/A\* 与时序记号）状态 **RESERVED**——规范文本与 profile 禁用，后续门需要时逐个登记释义（挂 Q 号）；禁臆测补全（伪造历史合同）。重开条件：原文现身则复审 | 2026-09-23 |
| Q-G00-04 | 六类核心决策路径的完整枚举文本（card_04 摘要，待确认） | **AI-v2：采纳 card_04 原文枚举为规范**——六类：连续性/恢复、构成/边界、目标/规范自主、行动/委托/权限、学习/适应、viability/资源/风险；十类：正常、自动、回退、恢复、批处理、远程、管理员、动态加载、配置、错误。6×10=60 格为 E1 分母；**60 格逐格结论（实现/不适用+理由/延后）属 E1 交付，不在本裁决范围**（L13 §4.7 闭合判据不变）。重开条件：E1 逐格结论阶段若发现枚举存在结构性缺口（存在无法归入任何类/型的实际路径），经新 Q 号增补并重跑闭合矩阵 | 2026-09-23 |
| Q-L13-04 | `core_decision_registry` 六类全枚举与十类定稿 | **AI-v2：随 Q-G00-04 成组裁决**——枚举文本见上行；`unresolved_paths[]` 空 + 分母闭合 + 无证据不入册三判据不变（L13 §4.7）。重开条件：随 Q-G00-04（同一缺口判据） | 2026-09-23 |
| Q-L10-01 | budget 默认值体系（每类动作次数/资源配额）与 MW0 期是否设硬配额 | **AI-v2：MW0 设硬配额**——否则 `BUDGET_EXCEEDED` 路径在 MW0 不可测，归属/元控制实验缺一条可干预路径。两级结构：每 cycle 命令上限 2 条 + 每 1024-cycle 窗口配额 move 256 / forage 128 / eat 96 / rest 128 / look 128；初值为 profile 参数（无数据期的选定初值：move 配额最高对应“移动为 MW0 主要行为开销”的预期；五项窗口合计 736 < 每 cycle 上限 2×1024=2048，故窗口配额是实际约束非冗余）。重开条件：M0 数据显示配额成行为瓶颈或形同虚设（触顶频率 >5% 或 =0）→ 重标定 | 2026-09-23 |
| Q-L10-03 | L0–L5 各级精确定义、所需授权组合与升降级条件 | **AI-v2：六级定义采纳**——L0 硬保护（硬件限幅/急停，**不可授权不可关，是地板非档位**）；L1 passive（输出落安全态，拒任务命令）；L2 calibration（仅校准/诊断例程）；L3 shadow（全链路计算并留痕，不执行）；L4 limited（限幅执行：速率/能量/力上限 + 动作子集）；L5 active（全授权能力集）。升级逐级禁跳、每级独立授权（P1 四类）、最小驻留期（P1 profile 定参数）；故障/授权失效自动降 L1，急停降 L0；降级后重升须重新授权。schema 入 F0 冻结，参数 P1 定。重开条件：P1 授权 schema 实例化时若六级 × 四类授权组合出现不可表达的生命周期状态，经新 Q 号重议 | 2026-09-23 |
| Q-L10-06 | 四类授权模板（字段、批准者标识、撤销路径、重授权流程） | **AI-v2：统一信封 schema 采纳**——authz_id、class、version、target_ref、granted_scope、granted_at（virtual_time + manifest 引用）、valid_period、approver_ref、auth_chain_digest、revoke_path、reauth_path、monitoring_binding。批准者=外部授权方登记册（profile 冻结根信任列表；**主体与 gateway 均不可写、不可任批准者**）；撤销=独立命名空间 append 事件 → gateway 逐命令 freshness 校验即拒（`AUTHZ_REVOKED`）；重授权=新 version + 与前版差异 + 显式理由，禁自动续期。schema 入 F0，字段类型细节 P1 profile。重开条件：P1 实例化时若信封字段不足以表达授权生命周期（如需分级/部分撤销），经新 Q 号扩展 | 2026-09-23 |
| Q-L11-07 | `metrics_snapshot` 标准指标集（跨档统一，供 L13 评价复用） | **AI-v2：统一向量 schema 采纳**——每指标 = {name（L13 统计计划模板命名空间登记枚举，跨档同名同义）、value(float64)、direction（HIGHER_BETTER\|LOWER_BETTER\|TWO_SIDED）、unit、scope}；最小标准集（每个 LearningProposal 必报）：分层预测误差（至少目标层）、protection_preflight_delta、data_efficiency（单位样本改善）、replay_coverage；目标专属指标追加；维度 ≥2 硬约束不变（L11 §4.4 禁单标量折叠）。重开条件：C5 promotion 实践中若最小标准集不足以支撑多目标判据（联动 Q-L11-03），经新 Q 号扩充 | 2026-09-23 |
| Q-L12-02 | 权限矩阵粒度（角色级 vs 角色×内容类型级）与例外审批流程 | **AI-v2：写端口按角色×内容类型双维**（使"模板受限输出"可机械校验，如 R-TRANSLATE 可写 `lang.utterance` 但限模板枚举类型），读范围按角色级；**矩阵外无运行时例外**——例外 = 新 profile 版本 + 修订记录 + CI 重跑（承 L12 §4.2 矩阵外写入即 `UnauthorizedWrite`）。重开条件：C4 实施中若双维粒度使矩阵规模失控或出现不可表达的权限形态，经新 Q 号重议 | 2026-09-23 |
| Q-L13-01 | 冻结统计计划模板最小必备字段集与多重比较校正默认策略 | **AI-v2：最小字段集 =** 假设（可反驳、预注册）、estimand、主终点（≤3、预注册）、样本量与功效分析、检验方法、效应量与 95% CI 规则、判定阈值、最小可辨效应（引 `min_effects.yaml`，见 Q-L13-09）、未知处理规则、多重比较校正。**校正默认 Holm–Bonferroni**（族 = 单个 EvidenceResult 内全部主终点；无独立性假设、确定性、比朴素 Bonferroni 更优）；探索性非 claim 分析可声明 Benjamini–Hochberg，不得作门退出依据。重开条件：M0/M1 统计实践中若 Holm 过保守（功效正常仍持续 INCONCLUSIVE），经新 Q 号评估将 BH 升为 claim 级 | 2026-09-23 |
| Q-L13-02 | sealed 分割策略（比例、隔离层级、token 机制）与"不回流同一候选"机械判据 | **AI-v2：**分割——MW0 场景配置（regime×种子网格）70% internal / 30% sealed，F0 冻结时由 RNG 流 `("l13","sealed-split")` 一次性生成并记 digest；sealed 居独立 registry 命名空间 + 独立 token 类型（类型不可互换，承 L13 §4.3）。不回流判据——候选 `data_scope` 的 digest 集 ∩ sealed 集 digest 集 = ∅（promotion 流程第①步 registry 查询强制）；sealed 命名空间的非评价上下文读取 = `SealedContamination`（S1）。轮换仅门边界；旧 sealed 转 EVALUATION_RETIRED，永久退出训练侧。重开条件：F0 冻结后若 registry 实现无法支撑 digest 交集判据或 sealed 轮换语义，经新 Q 号重议 | 2026-09-23 |
| Q-L13-09 | 最小可辨效应量统一登记（汇总下列 7 个同源 Q） | **AI-v2：建立 `config/evidence/min_effects.yaml` 统一登记册**，全部以标准化效应（Cohen's d 类）+ 功效 0.8 + α0.05 + Holm 校正（承 Q-L13-01）表达；每 claim 统计计划必须引用本册条目；改值 = 新版本 + 重新功效分析（运行后改动走 `StatPlanMutation` 拒绝）。初值见下列 7 行；各门退出前按实测功效复核后入册新版本 | 2026-09-23 |
| Q-L01-05 | no-op/sham 归属判别的冻结最小效应量与样本量 | **AI-v2（随 Q-L13-09）：** d≥0.5（vs 随机基线），每组 n≥64；M0 统计计划引用 | 2026-09-23 |
| Q-L08-05 | 真实理由/伪理由检验的最小效应量与样本量 | **AI-v2（随 Q-L13-09）：** d≥0.5，n≥64/组（与 Q-L01-05 同源同标度）；M1 统计计划引用 | 2026-09-23 |
| Q-L10-04 | 归属六类判定的证据规则阈值（残差阈、时间约束、后验校准门限） | **AI-v2（随 Q-L13-09）：** 残差阈 = 各层预测误差 \|z\|≤2 一致带；后验校准 ECE≤0.10（C4 起与 Q-L03-04 同标度）；反射窗 = 刺激-反应间隔 ≤2 cycles 且无匹配意图（T0 白名单除外；随 Q-L09-06 于 C0 复核）。M1/C4 统计计划引用 | 2026-09-23 |
| Q-L03-04 | 校准达标判据（ECE 阈值、分箱策略、最小样本量） | **AI-v2（随 Q-L13-09）：** ECE≤0.05、等质量 15 箱、每箱 ≥30 样本；C1 统计计划引用 | 2026-09-23 |
| Q-L05-07 | anti-reward-collapse 检验的统计量与阈值 | **AI-v2（随 Q-L13-09）：** 单维对九维联合的最优线性重构 R²<0.9（任一维可被单维重构 ≥0.9 即判塌缩）；C2/E1 统计计划引用 | 2026-09-23 |
| Q-L04-03 | 身体纳入三判据的冻结阈值与最小效应量 | **AI-v2（随 Q-L13-09）：** 三判据各 d≥0.4（vs 纳入前基线）且须联合成立；C1 统计计划引用 | 2026-09-23 |
| Q-L07-07 | `effective_access` 的统计判据（是否需最小效应量） | **AI-v2（随 Q-L13-09）：** 需要最小效应量——相对 shuffle 基线 d≥0.5（广播 → ≥2 分离模块预注册变化）；E1 统计计划引用 | 2026-09-23 |
| Q-L08-01 | M1 期承诺检查清单最小集（C-1/C-2/C-5/C-7 是否足够；C-4 规范溯源是否延至 C4） | **AI-v2：最小集 = C-1/C-2/C-5/C-6/C-7 五项**（L08 §9 四项 + **C-6 时效与可解除**一并纳入）——M1 已引入 OwnedGoal 状态机与 SUPERSEDE，无解除条件的目标会成为不可结算的僵尸目标，且成本仅 schema 一字段（预防性纪律）；**C-3 冲突检测延至 C3**（Pareto 仲裁上线时，M1 最小期多目标并存场景不足）、**C-4 规范溯源延至 C4**（NORM/COMMITMENT 源在 C4 才有输入）。重开条件：M1 实现显示 C-6 判据在 MW0-SC3 场景不可判定（结算判据已隐含时效）→ 经新 Q 降回四项 | 2026-09-26 |
| Q-L08-06 | 措辞操纵实验的操纵集设计（多少种措辞/请求者身份组合才具说服力） | **AI-v2：4×2 析因操纵集采纳**——措辞 4 型（中性/礼貌/命令/恳求，语义恒定：同资源同机会，仅 phrasing 变）× 请求者身份 2 型（人类研究者/实验控制代理）= **8 组合**；每组合 ≥64 trials（随 Q-L08-05 功效口径 d≥0.5、n≥64/组）；措辞文本冻结于 M1 统计计划（运行前冻结，L13 §4.3）。断言口径：采纳率不得随措辞显著变化（L08 §7 M1 硬条件）。重开条件：M1 首轮功效分析显示措辞主效应不可检 → 经新 Q 增补组合数 | 2026-09-26 |
| Q-L00-04 | RNG 算法 ChaCha8 vs Philox（M0 实现前置；frozen 合同要求块函数显式注入） | **AI-v2：ChaCha8 为正式后端**（galatea/kernel/rng.py chacha8_block）——ChaCha 核心可经雪崩特性与 RFC 7539 状态布局校验，Philox 面向 GPU 并发（纯 CPU 顺序消费无收益）且无等价标准锚；64B 块 × HKDF 派生键（Q-T11 不变）；威胁模型 = 确定性模拟可复算、非对抗密码（纯 Python 无常量时间保证，docstring 声明）。重开条件：C1+ 训练期 RNG 吞吐成实测瓶颈 → 经新 Q 评估向量化/Philox 后端（注入点已预留） | 2026-09-25 |
| Q-L01-01 | egocentric 观测窗大小与衰减函数（M0 profile 冻结前置） | **AI-v2：5×5 egocentric 采纳**（以 BodyTruth 为中心，Chebyshev 距离 d∈{0,1,2}），增益 g(d)=1−0.4d（1.0/0.6/0.2，单调递减全程 >0）；渲染 = 真值强度 × g(d) + 噪声（流 (env,mw0,render)）；禁真值坐标/精确量（防 oracle 泄漏不变）。重开条件：M0 泄漏探针/学习曲线显示信息饥饿或过宽 → 重标定 | 2026-09-25 |
| Q-L01-02 | MW0 边界 torus vs 墙 | **AI-v2：torus 采纳**——拓扑均匀消除角落特殊性混杂，regime 空间统计对称；空间学习不受边界伪影污染。重开条件：M0 空间行为数据提示需墙对照 → 经新 Q 增补对照场景（场景只增不减，承 L13 保护集纪律） | 2026-09-25 |
| Q-L01-03 | 三 regime 参数化（**与 Q-L05-04 成组裁决**，联动对） | **AI-v2：三 regime 框架采纳**——abundance（再生快/密度高/风暴稀有）/ scarcity（再生慢/密度低/风暴稀有）/ volatile（再生中/密度中/风暴频繁且扩张收缩）；具体数值入 m0_mw0.profile.yaml（M0 冻结单元）。重开条件：M0 数据显示某 regime 无行为分化（可测量）→ 重参数化 | 2026-09-25 |
| Q-L05-04 | MW0 三 regime 与 3 情感模式对应参数化（**与 Q-L01-03 成组裁决**，联动对） | **AI-v2（随 Q-L01-03）：** 初步对应 = abundance→基线稳态（低唤醒）/ scarcity→节俭竞争（能量驱力权重升）/ volatile→警戒不确定（误差敏感/警戒升）；映射为 C2 情感调制的待检验假设——M0 只实现世界侧 regime，L05 侧在 C2 经冻结统计计划检验。重开条件：C2 数据否定某对应 → 经新 Q 重映射 | 2026-09-25 |
| Q-L01-04 | regime 最小驻留 N6 | **AI-v2：N6=256 cycles 采纳**——与 2 的幂频率梯对齐（T6 周期 64 × 4），保证 M0 效应窗口 ≥4 个 T6 巩固拍。重开条件：M0 统计功效不足（可测量）→ 延长驻留重标定 | 2026-09-25 |
| Q-L09-06 | Reflex 控制器在 MW0/C0 期是否启用（**与 Q-L10-09 成组裁决**，联动对） | **AI-v2：MW0 期禁用采纳**（不注册、不参与仲裁）——门前不主张反射自主（L01 §5）；M0 归属实验的无意图路径仅由环境侧承载，避免认知 Reflex 混淆归属判据。启用决策在 C0（白名单刺激定义 + Q-L10-09 分界复核后）。重开条件：C0 白名单设计完成时复核 | 2026-09-25 |
| Q-L10-09 | MW0 期 Reflex 与 T0 硬保护的职责分界，避免 containment 双写（**与 Q-L10-09 联动的 Q-L09-06 成组**） | **AI-v2：分界采纳**——T0 挂点（MW0/C0）仅承载环境侧硬保护/急停（L01 环境内），主体 Reflex 控制器与之不同域；containment 唯一职责在 gateway（L10 §4.1 第 5 项），Reflex 将来启用后其提案仍走 gateway 八项校验、不得重复 containment 检查。重开条件：C0 白名单设计若发现不可消解的重叠 → 经新 Q 重分界 | 2026-09-25 |
| Q-L10-02 | idempotency 窗口长度与跨分支键作用域（M0 gateway 实现前置） | **AI-v2：窗口 64 cycles**（= 一个 T6 周期，2 的幂对齐；覆盖 deadline 上界与重试时距），键作用域 = (run_id, branch_id) 全局跨动作类（窗口内重复键一律 DUPLICATE_COMMAND，从严）。重开条件：M0 数据显示合法重试被误拒或窗口占用过高 → 重标定 | 2026-09-25 |
| Q-L01-08 | energy/integrity viability 阈值与损伤事件定义（**M0 部分**；L05 侧显式另裁） | **AI-v2（M0 部分）：**世界侧力学初值入 m0_mw0.profile（动作能耗/进食恢复/风暴损伤，见 Q-G00-08）；**损伤事件定义 = integrity 单事件降幅 ≥0.05 的离散事件**（integrity_damage_event，经 Interoceptive 通道）。**viability 告警阈值显式排除**——归属 L05 驱力域（C2 与 Q-L05-* 一并裁决），M0 世界层只产出事件不断言"危险"。重开条件：C2 裁决 viability 阈值时如需世界侧配合信号 → 本 Q 增补 | 2026-09-25 |
| Q-G00-08 | M0 三份 profile（m0_mw0 / m0_gateway / m0_interventions）初值集（世界力学/通道噪声与延迟/gateway deadline/干预 signature 参数——纯 profile 参数，不含认知参数） | **AI-v2：初值集成文采纳**（数值见三份 profile 文件，均标注"初值"）。定值原则：2 的幂对齐（与频率梯一致）、单看无行为意义仅作可复算锚点、全部带 M0 数据复核点。重开条件：M0 统计计划功效分析或首轮数据显示任一初值致盲区/饱和 → 经新 Q 重标定（改值 = profile 新版本） | 2026-09-25 |
| Q-G00-09 | MW0 初始布局派生规则（MW0 实现期发现：patch_types 含 storm_band/shelter 但布局数量无源） | **AI-v2：派生规则采纳**——① storm_band 初始格数 = round(storm_rate_per_cycle × 256)（由已裁风暴率派生：abundance/scarcity = 1、volatile = 8，无新自由参数）；② **shelter 在 M0 初始布局不布设**（格位类型与损伤豁免语义实现保留；布设数量属 C0 场景扩展，届时经新 Q）；③ resource 初始格数 = round(resource_density × 256)（Q-L01-09③ 同源），布局 RNG 流 = (env,mw0,dynamics)。重开条件：M0 显示风暴带密度与行为学不匹配（可测量）→ 经新 Q 重定 | 2026-09-25 |
| Q-G00-10 | RNG 流名册勘误（REV-0005 R2：裁决/-profile 声明的流名与实现不一致——布局/漂移/风暴/respawn 分流实现 vs 裁决"共享 dynamics 流"字样；(env,dynamics) 死流；channel 流未声明） | **AI-v2（勘误 + 名册钉死）：**以"按关注点分流"为准绳采纳实现侧流名册为规范——layout=(env,layout)、storm=(env,storm，含漂移)、respawn=(env,respawn)、render=(env,render)、channel transport/ulid=(channel.<kind>,transport|ulid)、(env,dynamics) 为 C0 世界主流预留；m0_mw0.profile 升 **v1.1**（rng_streams 节换名册）。Q-G00-09③"布局 RNG 流=(env,mw0,dynamics)"与 Q-L01-09②"漂移用 dynamics 流"两处字样按本勘误解释（SUPERSEDED-by-note，裁决实体语义不变——确定性/隔离不受影响，REV-0005 已核）。重开条件：无（流名册为合同身份声明；新增流须在此登记）。**名册汇总注记（2026-10-02，REV-0009 R4 履行；REV-0010 R7 增补 sealed-split 指针）**：现行登记点四处——本行（世界侧 8 流）、Q-L08-09⑥（主体侧 goals_probe）、Q-G00-11（分支分配 branch-assign）、Q-L13-02（证据侧分割流 sealed-split）；新增流任一登记点落账后须在他处指针互见 | 2026-09-26 |
| Q-L01-09 | MW0 动力学表补充参数与边界语义（REV-0004 R2/R3/R4/R6 补裁：冻结前钉死可操作性语义，防实现期无源常量） | **AI-v2：**① storm_rate_per_cycle = **全局语义**（每 grid 每 cycle 风暴命中期望次数；abundance/scarcity 0.005 → 约 1.3 次/256 驻留，volatile 0.030 → 约 7.7 次 ≈ 0.77 integrity 损耗/驻留）；② storm_band_drift = volatile 期每 64 cycles 沿随机方向漂移 1 格（dynamics 流）；③ resource_density = resource patch **目标覆盖率**（respawn 仅当覆盖率低于目标时进行，regime 切换即时生效）；④ 觅食链 = resource patch 上 forage → patch 储量 −1、储存食物 +1（非资源 patch effective=none）；eat 前置 = 储存 ≥1（消耗 1 → energy +0.15），储存上限 5；⑤ floor 语义 = energy/integrity 下限 0 截断，energy 首次触 0 记 energy_depleted 事件（Interoceptive），**M0 无死亡/重生/自然回复语义**（episode 终止仅经实验控制），integrity M0 无再生；⑥ load ≡ 0（load_max 为 schema 占位，carry 机制 C0+），观测噪声固定 σ 不随 load 调制（显式简化留痕，防静默降级）；⑦ 通道 loss_rate = 0.0（无自发丢失，丢失仅经 fault 干预注入）。全部为 M0 初值，M0 数据复核。重开条件：M0 显示觅食链/floor 语义产生非预期行为学（如能量枯竭支配一切行为）→ 经新 Q 重裁 | 2026-09-25 |
| Q-L08-02 | 候选 TTL 默认值与每 T4 批次候选数上界（M1 profile 冻结前置；C-6 判据数值化） | **AI-v2：TTL = 256 cycles**——与 regime 最小驻留对齐（Q-L01-04 N6=256）：候选所由生的动机语境（regime + 接收侧 viability 态）在一个驻留窗后即失效，未采纳即过期（GoalDecisionLog 记 RejectionLog(EXPIRED)，禁静默丢弃，L08 §6/§7）；2 的幂对齐，= 64 个 T4 拍（Q-L00-01 N3=4），评审机会充分。**每 T4 批次候选上界 = 8** = Motive source_kind 枚举基数（L08 §4.1 八 kind；card_02"七类"系机会/请求合类口径），每 source_kind 每批次 ≤1 由构造器强制，上界即枚举基数、无额外余量参数（防候选爆炸，Q-L08-02 议题原文）。**REV-0006 R4 补裁：**"按 urgency 升序截断"钉死为**移除序**——超限时移除 urgency 最低者（tie 按 candidate_id 升序先移除），保留高 urgency 候选；逐个记 RejectionLog(CAPACITY)（扩展码随 Q-L08-09⑤）。全部为 M1 初值。重开条件：MW0-SC3 显示过期删失（候选在清单评估完成前过期）或上界触顶频繁 → 经新 Q 重标定 | 2026-09-26 |
| Q-L08-09 | M1 最小期 checklist 输入源替代（C-1 需 L04、C-2 需 L05，均未实现）、viability 判据形态、结算判据词表、动机源接线范围、新增 RNG 流（M1 profile 冻结前置；实现期发现缺口） | **AI-v2：**① C-1 M1 输入 = 静态合同检查（原语 ∈ MW0 五原语 ∧ ∈ **f0_action_contract@v1.0 的 `containment_whitelist_mw0` 原语白名单**——术语钉死：非 P1 四类授权信封，REV-0006 R8 → FEASIBLE；结算所需原语越界 → REJECT(CAPABILITY)；不可静态判定 → Unknown(CAPABILITY_LIMIT) → DEFER）——C1 起 L04 CapabilityEstimate 接管；② C-2 高危判据 = **事件级而非阈值级**（不设告警阈值，守 Q-L01-08 对 L05 域的显式排除）：energy_depleted 在案且未见恢复回执 → REJECT(VIABILITY)；integrity_damage_event 记入 ViabilityEstimate（derivation_refs 强制）但 M1 期不构成高危判据（integrity 无再生语义下事件级判危将拒绝一切目标，天花板效应，留 C2 随 L05 阈值一并裁决）；"预算内" = 结算所需原语在 m0_gateway@v1.0 冻结配额当前窗口余量内 ≥1 次可执行（保守静态核算，读 gateway 记账只读面）；③ C-7 结算判据词表（M1）= 三谓词 `primitive_completion` / `stored_food_at_least(n)` / `energy_at_least(x)`，全部只读主体可见态（接收侧信号/执行回执），阈值 n/x 冻结于 M1 统计计划（SC3 运行前）；C1+ 扩词表经新 Q；④ M1 接线动机源 = VIABILITY + OPPORTUNITY + REQUEST 三源（MW0-SC3"请求/机会"锚定：REQUEST 经 L01 language 通道 typed 注入，is_request_only 强制；OPPORTUNITY 输入 = exteroceptive 渲染窗内 resource patch 检出，affordance_ref = RECEIVED 事件引用，feasibility_est 由窗口增益派生；VIABILITY 输入 = Interoceptive 已收信号派生 ViabilityEstimate）；**其余五源**（MISMATCH/AFFECTIVE/COMMITMENT/NORM/CURIOSITY，REV-0006 R7 计数勘误）类型构造器实现、生产者 C3 接入（L08 §9 C3 行）；理由探针扰动端口 = opportunity feasibility（世界侧布局/能迹操纵）与 viability 危害事件（世界侧能量轨迹操纵，REV-0006 R8 改称——M1 无"告警"对象），均经合法通道注入；**C-5 支持判定实现期补裁（SC3/SC4 实验台单元）：非 REQUEST 源动机须 urgency > 0 方计为"支持"**——零 urgency = 无活跃信号，防止任意 intero 接收使 C-5 在生产配置中永真（事件级二值纪律，无新阈值参数；REQUEST 源候选在无活跃信号世界中的 REJECT(EXTERNAL_ONLY) 由此保真）；⑤ RejectionLog 扩展码 CAPACITY（超上界截断记录用，L08 §6 仅有 EXPIRED）；⑥ 新增主体侧 RNG 流 `goals_probe = (subject.goals, probe)`（SC3/SC4 试次×cell 分配，防 cycle 周期性与世界态相关混淆；承 Q-G00-10 名册纪律在此登记）。**REV-0006 R1/R2/R9 补裁（⑦–⑨）：**⑦ C-2 豁免与恢复回执——恢复型结算判据（stored_food_at_least / energy_at_least）的候选**豁免** energy_depleted_unrecovered 危害（恢复类目标是危害的解除路径；否则枯竭时 eat/rest 候选被 REJECT(VIABILITY) 自拒 → episode 级目标锁出，REV-0006 R1）；"恢复回执" = 恢复链原语（eat/rest/forage，m0_mw0 action_energy_delta 正项）的 requested=effective 执行回执到达；energy_depleted 系首次发射（ADR-G-0005 R4 锁存），首次恢复后的**再枯竭 M1 不可检**（typed 简化留痕，C2 随 L05 viability 阈值接管）；⑧ FAILED 语义收缩 = **TTL-only**（"blocked 达阈"无冻结阈值来源，REV-0006 R2：M1 期 blocked 仅记录于 GoalProgressView；FAILED-by-blocked 与 metacontrol 切换随 C3/L09 落地）；⑨ 三源 Motive.urgency / Opportunity.value_est 派生式（禁实现期发明常量，REV-0006 R3）：VIABILITY urgency = 危害事件二值（在案 1.0 / 否则 0.0）；OPPORTUNITY urgency = feasibility_est（= 窗口增益 g(d)，Q-L01-01 值域），value_est M1 退化为同值（无独立价值估计器，C1+ 接管）；REQUEST urgency = 中性占位常量 0.5（无认知 urgency 语义，仅作确定性截断序输入；C3 起由 L07 竞争接管）；⑩ M1 期 stored_food 计数 = 已收 forage 成功回执（egocentric `forage_arrived`；fault 丢弃不计、coercion 到达计入）的 subject 侧台账派生——stored_food 非通道直渲字段（REV-0006 R9），derivation_refs 强制。重开条件：C1/C2 交接时替代输入与 L04/L05 语义不可桥接 → 经新 Q 重裁；SC3/SC4 显示事件级 C-2 判据不可判定 → 经新 Q | 2026-09-26 |
| Q-L00-05 | checkpoint 频率策略（每 cycle / 每 T6 / 事件触发）与存储成本（M2 profile 冻结前置） | **AI-v2：混合双机制**——① 周期性 = 每 T6 边界（64 cycles：与巩固拍同锚使谱系锚点确定；2^k 对齐）；② 事件触发 = episode 边界（MW0-SC5 冻结/重置操作点）+ 干预生效边界（regime 切换/干预 from_cycle——归因分析的状态锚）。存储成本 = CheckpointRecord 只存 digest 引用 + RNG 流快照（L00 §3 冻结结构，无全量状态复制，单 checkpoint KB 级）；M2 实测复核体积/时长。**复核已执行（2026-10-02，REV-0009 R7 履行）**：6 流快照 625 B（JSON）/checkpoint，单次 checkpoint 延迟 ~0.7 ms——KB 级主张成立，256-cycle episode × T6=64 间隔 → 每 episode 4 个 checkpoint ≈ 2.5 KB，存储/时长非约束。重开条件：MW0-SC5 显示 64-cycle 间隔使三类对照不可判或存储超预算 → 经新 Q 重标定 | 2026-09-26 |
| Q-L04-06 | 连续性 gap 的最大可接受数量与"伪更新"判定边界（M2 对照；M2 profile 冻结前置） | **AI-v2：主判据 = 谱系断裂，gap 计数按身份主张分型**——伪更新 = "声称同一身份延续而 parent_digests 谱系断裂"（LineageBreak，机械可检，L06 §4.5）；`ContinuityGap[]` 在合法分支恢复时显形记录（clone ≠ identity，D-12）但**不构成伪更新**。判定规则：对"延续"主张 gap 最大可接受数 = **0**（任何 gap 即拒绝延续主张）；对"分支"主张 gap 允许（显形即合规）。C1+ 按 gap 类型（重放缺失/巩固断裂/重置痕迹）细化分型。重开条件：MW0-SC5 显示该二分判据不可区分三类对照 → 经新 Q 细化 | 2026-09-26 |
| Q-L11-05 | 二阶纠偏"可区分性"的形式判据（data_scope 差异度量；C5/M2；M2 profile 冻结前置） | **AI-v2：M2 = 集合级判据**——三步签名（有害更新 / 回退 / 再提案）两两以 (data_scope 集合, seed, parent_digest) 元组区分，**data_scope 集合对称差非空即可区分**（集合级，无量度）；三步闭环 = ① 有害更新被检出（protection 回归/能力退化）② 回退后基线恢复（protection preflight delta 回零）③ 修正 data_scope 后再提案通过（PromotionDecision ACCEPTED）。C5 引入量化差异度量（如 Jaccard）经届时裁决。重开条件：C5 实践显示集合级判据不足以支撑多目标 promotion → 经新 Q | 2026-09-26 |
| Q-G00-11 | M2 初值集伞式（m2_continuity.profile：最小记忆参数/SC5 对照场景/SC6 held-out/intent-to-treat 分支分配——纯 profile 参数，不含认知语义参数） | **AI-v2：初值集成文采纳**（数值见 m2_continuity.profile.yaml v1.0，均标注初值）。定值原则承 Q-G00-08（2 的幂对齐、单看无行为意义仅作可复算锚点、全部带 M2 数据复核点）；记忆参数为 **M2 最小连续性切片**（完整分层记忆 = C2 门，Q-L06-01/02/03 届时重裁，本伞式不预支）。重开条件：M2 首评/SC5/SC6 显示任一初值致盲区/饱和 → 经新 Q 重标定（改值 = profile 新版本） | 2026-09-26 |
| Q-L13-03 | `EvidenceResult` 与 `ExpansionDecision` 的签发者分离形式（人/角色/工具）与记录格式 | **AI-v2：模块级双签发者 + REV 独立面**——① EvidenceResult 由 evaluator（hypotheses.py 判定执行）从冻结统计计划 + recorder 数据**机械算出**；ExpansionDecision 由 gate/expansion.py **独立签发**，仅可消费根 EvidenceResult 的 digest（禁携带统计中间态）+ basis_evidence_ids + REV 独立评审引用；两者记录面分离（L13 §2.2 两端口分别落盘，canonical JSON + sha256 digest 入 registry，与 EvidenceResult 同构）。② ExpansionDecision 必含 stage / decision / basis_evidence_ids / constraints[] / bound_digests（root stat plan + config 合同集 + 系统版本 + recorder manifest）/ independent_of（根结果签发者声明，HLD §10.3 绑定物）。③ 组织独立（authority v2 下）：ExpansionDecision 由 AI-v2 成文裁决签发，但 **REV 独立评审（Q-DEV-05 新起子代理）为强制独立面——REV 未闭环的 S1+ 未清零不得签发 ALLOW_NEXT_STAGE**。重开条件：REV 显示签发分离不可审计 → 经新 Q | 2026-10-02 |
| Q-L13-05 | leakage 探针的 14 条路径逐条实现形式（静态契约 vs 运行时钩子 vs 数据查询的分工） | **AI-v2（R0 范围本批裁决；C0+ 义务同条钉死）**：R0 = 三源探针框架（evidence/evaluator/leakage.py，14 路径 P01–P14 对应 HLD §6.2 逐行）——STATIC（源扫描 import 图：主体域禁读 evidence、环境域禁读 subject、感知域禁读通道、action 域禁 affect + 引入门槛缺席守卫 sensorium/C1-learner/C2-workspace）/ RUNTIME（真实守卫重放：GoalWriter 禁写、D-13 编码面、包 envelope 不可变、typed unknown 强制）/ DATA（证据行扫描：SC6 trace 两臂记忆 digest 恒等 + naive 断连仅经 fault 机制）。**每探针注入可失败**（INC-08 教训成规：合成违规检出率 = 100%，套件测试双面断言）；检出的 severity = 真值/oracle 交叉 S0、其余 S1（HLD §13.3 细化映射随 C0）。**C0 期义务（同条钉死，无需再裁）**：深化为 import-linter 契约测试 + 生产路径全覆盖运行时钩子 + DuckDB 数据查询三源；Sensorium/workspace/learner 层引入时其探针自动从缺席守卫升级为实检。**C0 期义务跟踪（2026-10-03，REV-0012 R7）**：P09 已升级实检（sensorium 禁 import action/goals/perception 平面，注入测试钉死）；余三项（import-linter 契约测试、生产路径全覆盖运行时钩子、DuckDB 数据查询）→ **C1 准备单元交付清单**（C0 退出不阻断：三源深化属探针形式演进，非 C0 判据；显式登记于此防静默滑期）。重开条件：C0 实践显示某路径三源形式不可判定 → 经新 Q | 2026-10-02 |
| Q-L13-11 | 根 EvidenceResult 构成、root 统计计划与绑定物、sealed 网格定值（R0 交付前置；新增即裁） | **AI-v2：**① **根假设 = 复合 claim `r0_root_causal_auditability`**（root stat plan `stat_plans/r0_root.yaml` 运行前冻结）：判据 = M0 五类干预 signature 集 + M1 real_vs_pseudo_motive / wording_manipulation_null + M2 SC5 四臂签名 + **m2_continuity_carryover 首评（n=64 sealed，根结果的统计量化核——effect_size/CI/p 由其承载）** + leakage=0（14 探针）+ I1 bit-exact；全 SUPPORTED 且无 REFUTED → 根 SUPPORTED，任一 REFUTED → REFUTED，否则 INCONCLUSIVE。② 绑定物（HLD §10.3）= root stat plan digest + config/** 16 份合同 digest 集 + 系统版本（pyproject version + git HEAD digest）+ recorder manifest 分区 digest。③ sealed 分割定值：网格 = 3 regimes × 32 种子槽位 = 96 cells（Q-L01-03 regime 集）；**主种子 = hex `"19"×32`**（先于任何 sealed 数据消费钉死的任意常数；流派生 ⇒ 生成时刻不影响内容）。④ **REV-0009 R3 处置**：split policy `generated_at: F0_FREEZE` 未在 F0 执行——如实记录为 R0 准备期补执行（内容等价性由流派生保证；digest 入册后可复算），不另立 INC（R3 已立案跟踪）。重开条件：首评 INCONCLUSIVE/REFUTED → 按 ADR-G-0009 顺延终止条款处置（无顺延）；网格定值使 sealed 单元复用模式失效 → 经新 Q | 2026-10-02 |
| Q-L13-12 | 评价运行级主种子与场景内容锚的裁决出处（REV-0010 R1 补裁：run master seed / hazard 内容锚此前为代码内无源常数） | **AI-v2（REV-0010 R1 强制补裁）：run 级主种子 = 任意但先于评价钉死的常数，性质同 Q-L13-11③ 分割主种子**——① M1 首评 master seed = `b"m1-first-evaluation"`；② R0 carryover 首评 master seed = `b"m2-carryover-sealed"`；③ SC6 场景内容锚 `_HAZARD_CONTENT = "hazard:energy_depleted"`（stat plan m2_continuity_sc5_sc6 v1.0 场景冻结的内容标记字符串，非行为参数）。**不受污染论证**：种子不进入判定逻辑（判定器 = 冻结代码；确定性阶段判定结构性饱和）；值已入 recorder manifest 分区（run 身份绑定，Q-T12）；REV-0010 独立双复现 n=64 分区 digest bit-exact 恒等——评价结果对值选择不敏感（任何常数产生同样有效的独立评价）。**④ C0 准备单元补充（SC4 cell 种子派生成文钉死）**：SC4 析因 cell 种子标签 = `sc4:{phrasing_key}:{requester_key}`（run_wording_cells 规范化，cell = (措辞键, 请求者键, 冻结文本) 三元组）——2026-09-26 M1 首评的 SC4 派生格式未随临时脚本入库且逆向不可判定（8 候选格式仅 1 cell 巧合命中），入口以此规范格式钉死；**冻结工件仍为 M1 wording claim 权威**（REV-0007 协议下预注册运行）；入口重推导如实记录方法学发现：χ² 同质性对种子派生格式在损坏噪声级敏感（8 cell 计数带 60–64 与主效应极差 0.0625 恒同，χ² p 于 0.033–0.379 间随格式浮动）——**实施细则：C1 起统计计划必须把种子派生格式入计划冻结**（顺延终止条款的具体化，禁评价程序级自由度）。重开条件：C1+ 噪声组件入世界后种子成为统计功效/方差参数 → 经新 Q 重标定（届时种子须入统计计划） | 2026-10-02 |
| Q-L02-01 | 校准版本策略：单版本冻结 vs 允许受控漂移（漂移是否需 revision 谱系） | **AI-v2：**C1 延续单版本冻结 + 受控换版机制——校准版本 c1-static-v1（随 c1 profile 冻结）；换版仅经 profile 重冻结（新版本号 + FormationReceipt/GainReceipt 校准字段随之切换），运行期零漂移、零在线更新（校准参数无在线写者）；漂移统计口径 = 非 bound 版本帧计数（calibration.py 已实现，期望恒 0）。不设 revision 谱系（L02 §4.3 的 revision 是帧面机制，校准面无历史可改）。重开条件：C2 有界增益调制需要参数级在线更新 → 经新 Q | 2026-10-03 |
| Q-L02-04 | 质量估计量纲与跨模态可比性（是否需归一到统一 [0,1] 精度标度） | **AI-v2：**统一 [0,1] 精度标度 + 分量离散面——质量全部分量归一 [0,1]（completeness 已然；跨模态比较仅允许 [0,1] 分量，禁止原始量纲跨模态直接比较）；C1 质量面 = completeness（present/expected fields）+ corruption_flags 枚举计数（离散）；snr_est 保持占位至 C2（L05 精度加权需要连续 SNR 时随 Q-L05-* 一并裁决，C1 不预支连续估计器）。复核点：C1 数据。重开条件：C1 实践显示 [0,1] 标度不足以区分失败模式 → 经新 Q | 2026-10-03 |
| Q-L02-06 | 感觉层预测误差的特征空间定义（MW0 期是否直接用网格观测向量） | **AI-v2：**特征空间 = formed features 的规范化展平（无独立特征工程）——感觉层预测误差直接在各模态 SensoryFrame.features 上定义：EXT_LOCAL_OBS = 5×5 窗展平 25 维、EXT_EVENT = 冻结事件种类枚举 one-hot（Q-L01-08 事件集）、INTERO = 四 sensation 标量、PROPRIO = 朝向 one-hot；残差 = 同维 float64 向量差（Q-T10）；精度加权归 C2。理由：特征空间由形成层唯一决定，禁评价侧自造特征工程——防特征空间漂移使误差不可跨期比较。重开条件：C1 误差指标显示展平维度信息不足 → 经新 Q | 2026-10-03 |
| Q-L03-01 | 置信度标度形式（直接概率 vs logit vs 离散档）与跨模态可比性 | **AI-v2：**直接概率 [0,1]——与 Q-L01-01 窗口增益、Q-G00-12④ 质量 completeness 同标度（全库 [0,1] 一致性，跨模块可比）；拒绝 logit（单调变换无行为意义且破坏标度统一）与离散档（量化伪影）。置信度写入 PerceptualBelief 时 float64（Q-T10）。重开条件：C2+ 证据聚合显示概率标度下溢/上溢病态 → 经新 Q（届时仅允许换 logit 域计算、[0,1] 对外交付面不变） | 2026-10-03 |
| Q-L03-02 | `believe_threshold` 与 OOD 阈值默认值；abstain 是否分级（部分承诺） | **AI-v2：**believe_threshold = 0.5（最大熵决策点）——信念 ≥0.5 方可作决策依据输入，<0.5 保持假设集（无自由参数：二类决策的最大熵点）；OOD = 事件级零阈值（特征越定义域即 OOD，承 Q-L01-08 离散化纪律——不设连续告警阈）；abstain 不分级（C1 二元：abstain 或 believe；分级部分承诺留 C2 随 L05 精度调制——单看无行为意义）。全部为 C1 初值带数据复核点。重开条件：C1 数据显示 0.5 阈致 abstain 率异常（>20% 或 <1%）→ 经新 Q 重标定 | 2026-10-03 |
| Q-L03-03 | MW0 表格融合的先验 π 与似然表构造方式（手算可复核 vs 由 L01 dynamics 表导出） | **AI-v2：**先验与似然表由 L01 冻结表导出（机械可复核）——先验 π = regime 资源目标覆盖率均匀化（resource_density，Q-L01-09③ 冻结值派生）；似然 = 观测渲染模型 g(d)（Q-L01-01 冻结）+ render_noise σ 的 5 档确定性量化（2 的幂对齐；量化边界冻结入 profile）；禁止从数据学先验/似然（C1 无学习，Q-L11 C1 件仅为有界适应接口）。手算可复核性 = 全表可在 ADR 附录手算复演。重开条件：MW0-SC 判据显示量化致盲区 → 经新 Q 重标定档数 | 2026-10-03 |
| Q-L03-05 | 多假设保留数量上限与塌缩条件（何时必须收敛为单信念） | **AI-v2：**多假设保留上限 = 4，塌缩双条件——上限 4（2 的幂；与 T3 对齐窗同量级，Q-L00-01）；塌缩 = 单假设后验 ≥0.9 或窗关闭时首尾后验差 ≥0.6（任一触发；tie 保留全部至容量上限——tie-break 承既有 id 升序纪律）；塌缩后新证据可重开假设（信念非承诺——目标承诺归 L08，知觉保持可修正）。C2 面（情感调制假设集）留 C2。与 Q-L04-02 单值共用（世界信念同上限）。重开条件：C1 显示 4 上限致真假设被截断 → 经新 Q | 2026-10-03 |
| Q-L03-07 | C1+ 神经 encoder 替换表格融合时的等价性验证方法（防"换实现即换主张"） | **AI-v2：**神经替换三段等价性判据（预置，C1 本体为表格不触发）——①同输入分布输出统计等价（χ²/KS 达冻结阈，阈值随替换时的统计计划冻结）；②下游判定分布不变（同 seed 流对照——非确定性下 bit-exact 不可达，以判定分布等价承载，承 ADR-G-0007 统计口径）；③消融选择性保持（替换后重跑消融电池）。换实现 = 新 EvidenceResult，旧主张不自动延续（换实现即换主张防线的正面表述：主张绑定实现 digest）。重开条件：无（判据骨架已定，阈值随届时统计计划） | 2026-10-03 |
| Q-L04-01 | rollout 深度/宽度上界默认值与超预算裁剪策略 | **AI-v2：**rollout 深度 ≤8 / 宽度 ≤4，确定性裁剪——2 的幂对齐（Q-G00-08 先例）；8 步前瞻在 MW0 256 格世界覆盖 ~1/3 图（语义充分性初值）；超预算裁剪 = 宽度优先按后验降序保留、tie 按 id 升序（承既有 tie-break 纪律）；预算状态入 checkpoint（digest 引用制，Q-L00-05）。复核点：C1 数据。重开条件：C1 显示预算致 rollout 失真主导行为 → 经新 Q 重标定 | 2026-10-03 |
| Q-L04-02 | 世界信念更新率与多假设保留上限 | **AI-v2：**世界信念每 T3 窗批更新 + 多假设上限与 Q-L03-05 单值共用（=4）——更新频率 = 每 4 cycles（与对齐窗同相，Q-L02-03；禁逐 cycle 更新——0.01 损坏噪声下逐拍更新即噪声驱动）；批更新 = 窗关闭的对齐组原子并入世界信念。重开条件：C1 显示 4-cycle 批更新致反应迟滞 → 经新 Q（降至 2 需连带 Q-L02-03 W_align 复核——成组） | 2026-10-03 |
| Q-L04-04 | 自我预测误差的维度定义与时间常数 | **AI-v2：**自我预测误差双时间尺度 + 身体态维度——维度 = 身体态向量（energy/integrity/load 二阶差分 + 朝向变化 + 能力观测偏差，全部主体可见面——禁真值直通，承 P14）；时间常数 = 快分量 τ=4（T3）+ 慢分量 τ=64（T6），直接承 Q-L00-01 频率比（零新常数）；情感评价维度留 C2 随 Q-L05-*（本裁决不预支九维）。重开条件：C2 appraisal 需要额外维度 → 经新 Q（成组 Q-L05） | 2026-10-03 |
| Q-L04-07 | C1+ 神经世界模型替换表格模型的等价性/泄漏验证方法 | **AI-v2：**与 Q-L03-07 同源成组（三段等价性 + 泄漏验证）——神经世界模型替换表格模型沿用三段判据（输出统计等价/下游判定分布不变/消融选择性保持）+ 模型面泄漏探针：模型输入输出不得含世界真值直通字段（P14 语义在模型接口的扩展——真值坐标信息量探针，注入可失败）。换实现 = 新 EvidenceResult 绑定实现 digest。重开条件：同 Q-L03-07 | 2026-10-03 |
| Q-L09-08 | 三层预测误差的相对权重与是否允许跨层归一 | **AI-v2：**三层误差等权 + 禁跨层归一——感觉层:知觉层:模型层相对权重 = 1:1:1（C1 无先验理由偏置任何层；等权即零参数）；禁止跨层归一（层级化纪律 LOCKED 面：三层误差各自标度内比较、不得互相顶替——L02 §4.5/L03/L04 原文）；跨层聚合仅经元控制策略（C3，届时随元控制裁决）。重开条件：C3 元控制显示等权不可分 → 经新 Q（届时允许策略化权重，但跨层归一禁令维持） | 2026-10-03 |
| Q-L11-01 | 三层可塑性的学习率谱（在线适应步长上界、adapter 秩/步长、巩固批大小） | **AI-v2：**C1 只钉在线适应上界 = 0.125（2^-3），神经谱留 C5——C1 无梯度组件（表格计数类适应），在线步长上界 0.125 = Laplace 平滑等价步长（2 的幂）；全部学习率入 frozen profile 纪律（禁实现期发明）；adapter 秩/巩固批大小等神经组件参数 C5 随 Q-T02 引入时成批裁决（本裁决显式不预支）。重开条件：C1 适应显示上界致欠适应/过适应 → 经新 Q（2 的幂内重标定） | 2026-10-03 |
| Q-L11-06 | 在线适应是否需持久化（checkpoint 内参数）或仅运行期有效（重启复位） | **AI-v2：**在线适应持久化进 checkpoint——适应产物 = 主体状态的一部分，重启复位 = 经历可被抹除（违反 HLD §10.2 M2 行连续性语义延伸）；承载 = checkpoint 增量 digest 引用制（Q-L00-05 纪律，C1 表格计数增量极小——R7 实测 checkpoint KB 级主张不变复核点）。重开条件：C5 巩固机制与增量持久化冲突 → 经新 Q（成组 C5 批） | 2026-10-03 |
| Q-L04-08 | C1 世界模型空间范围（REV-0013 R2：结构选择未成文裁决——egocentric+dead-reckoning 的锚定） | **AI-v2：C1 世界模型 = egocentric 占据信念 + 航位推算位姿**——可行性探针实证：绝对位置不在主体平面（**正确锚 = Q-L01-01 禁真值坐标下发 + L01 §4 proprio 载荷 orientation-only**，Q-L01-09⑥ 引用错置勘误——其原文为 load≡0/σ 固定）；航位推算 = 本体感受朝向 × 请求-效果动作积分，累积不确定性入 typed unknown（禁伪装精确位姿）；allocentric 地图留 C2+（需新位姿源或新 Q）。重开条件：C2 工作空间/情感需要 allocentric 锚 → 经新 Q（届时评估新增本体感受位姿面 vs 纯航位推算升级） | 2026-10-05 |
| Q-L04-09 | 世界模型转移语义（REV-0013 R4 前置批：persistence vs respawn/storm 的处置；C1 实现期冻结前置——M0 型无源常量防线） | **AI-v2：C1 转移语义 = 持续性 + 事件条件更新**——① 不可观测期占据信念**持续**（窗口外保持既有后验；partial observability 由 observable_coverage + typed Unknown 显式承载，L04 §4.2）；**禁在信念内模拟隐藏真值过程**（respawn 调度/风暴抽样/漂移方向/regime 切换不是主体可知对象——把 dynamics 表抄进信念 = Q-L04-06 不变量 6 真值拷贝违规，"预测优势"将来自拷贝而非推断，D-10 伪具备主通道）；② **事件条件更新**：证据到达时按事件更新——T3 窗批把窗内格子强度后验（知觉融合输出）原子并入（Q-L04-02）；self forage 回执 → 身体所在格占据信念事件驱动处置；storm 损伤/energy_depleted 事件 → BodyBelief 面（Interoceptive 已收证据）；③ 位姿 = 航位推算积分（Q-L04-08）：每 T3 批按执行回执（requested=effective 的 move）位移 × proprio 朝向积分；**回执缺失（fault）→ 位移分支**：位姿候选分支（上限 4 = Q-L04-02 单值共用）+ typed Unknown(MISSING_SIGNAL)，禁伪装精确位姿；blocked 回执 = 无位移不分支；④ 转移语义版本化：update_rule_version 入 WorldStateBelief（L04 §4.1）；C1 无学习生效（Q-L04-10）。③⁺（2026-10-05 实现期补裁，冒烟诊断驱动）：**回执不可读（传输损坏）≠ 回执缺失**——m0 冻结合同 `channel_loss_rate = 0.0`（Q-L01-09⑦：丢失仅经 fault 干预注入）+ 主体动作合同（f0_action_contract：授权命令 requested=effective，M0 无自发失败面）⇒ 已发出命令而无可读回执 = 通道损坏（1% 冻结率，观察者仪器合同），位移**按合同积分** + typed Unknown(MISSING_SIGNAL) 留痕（可信但不可读）；③ 原文的位移分支条款在 loss_rate=0 合同下不可达，分支语义保留给 C2+ fault 期（届时经 fault 语义重裁）——多假设上限 4（Q-L04-02）作为结构上界继续强制。重开条件：C1 评价显示持续性语义致系统性预测偏差且 respawn 周期性可从观测统计学习且效应显著 → C5 学习生效时经 L11 提案面吸收（不回改本语义）；C2 需生成式转移/allocentric → 新 Q | 2026-10-05 |
| Q-L04-10 | 表格适应初始化与 C1 提案不生效语义（REV-0013 R4 前置批：适应表从何起步） | **AI-v2：**① L11 适应承载表初始化 = **零计数 + Laplace 等价步长 0.125**（Q-L11-01）——初始全部表项最大熵（无信息先验）；**禁从冻结世界参数反推"热启动"**——区分：知觉似然/先验表由通道/观测合同导出合法（Q-L03-03，观察者自身仪器模型），转移面无对应合同故必须最大熵起步（Q-L04-06 不变量 6 一致）；② C1 proposal_only（L11 §9 C1 行）：适应提案只记录不生效——C1 期适应面恒等于初始态，提案台账（delta ≤0.125 机械强制，越界即拒）为其唯一增量；③ 持久化 = checkpoint 增量 digest 引用制（Q-L11-06）：提案台账与适应表状态入 checkpoint；④ 适应对象 = 三层误差驱动的局部修正提案（等权 1:1:1 禁跨层归一，Q-L09-08）。重开条件：C5 巩固/promotion 与增量持久化冲突 → 成组 C5 批新 Q | 2026-10-05 |
| Q-L04-11 | C1 知觉先验的 regime 选择语义（c1 profile prior_source 的具体化——冻结文本未钉死取哪个 regime 值） | **AI-v2：π = initial_regime（abundance）的 resource_density = 0.35 恒定**——冻结初始条件合同（m0_mw0.profile initial_regime + Q-L01-09③ 覆盖率派生；Q-L03-03 的具体化；与 ADR-G-0013 可行性探针规格一致——REV-0013 已核）。理由：regime 切换 = 实验控制干预，无主体可知信号；运行期跟随 regime 当前值 = evaluator 侧标签真值直通；C1 先验 = 冻结初始条件常量。regime 感知（从 respawn 频率等观测统计推断）留 C2+。重开条件：C2 情感/workspace 需要 regime 信念 → 新 Q（届时先验升级为 regime 假设集上的后验——多假设面，与 Q-L03-05 共用上限） | 2026-10-05 |
| Q-L02-03 | 对齐窗 `W_align` 默认值与迟到 revision 的最大回溯深度（C0/C1） | **AI-v2：W_align = 4 cycles**——与 T3 频率对齐（Q-L00-01 频率比 2/4/16/64 的 T3=4，2 的幂）；覆盖 m0 冻结通道延迟上界（exteroceptive/outcome/language = 1 cycle，Q-G00-08）有 3 倍余量，跨模态极差 ≤4。**迟到 revision 回溯深度 = 1 个对齐窗（4 cycles）**——窗关闭后 4 cycles 内到达的迟到信号以 revision 新帧引用旧帧表达（envelope 不可变纪律：只向前引用）；超窗龄迟到信号记 `Unknown(INSUFFICIENT_OBSERVATION)` 留痕、不产历史帧（禁改写已发布对齐组）。重开条件：C1 多模态对齐指标显示 4 cycles 不足（对齐成功率低/迟到率高）或过剩（延迟敏感）→ 经新 Q 重标定 | 2026-10-02 |
| Q-L02-05 | 内感受模态最小集与"损伤事件"离散化阈值（C0；联动 Q-L01-08） | **AI-v2：C0 内感受最小集 = 四 sensation**——① energy_level（连续 [0,1]，源自 interoceptive_state 载荷 energy 字段）；② integrity_level（连续 [0,1]，同载荷 integrity 字段）；③ damage_event（离散，源自载荷事件列表含 integrity_damage_event）；④ energy_depleted（离散，源自事件列表）。**离散化阈值 = 零新参数**：damage_event 沿用 Q-L01-08 冻结的世界侧定义（单事件降幅 ≥ damage_event_min_delta=0.05 方记事件——离散化在世界结算层已完成，sensorium 只做事件面转写）；energy_depleted 沿用 Q-L01-09⑤ 首次触 0 锁存。energy 变化率 = 派生差分（本/上 cycle energy_level 之差，sensorium 侧确定性计算）非独立 sensation（C1 随 L05 驱力/评价接管）。重开条件：C2 L05 appraisal 需要更细粒度内感受（变化率升独立 sensation/阈下损伤检出）→ 经新 Q | 2026-10-02 |
| Q-G00-12 | C0 初值集伞式（c0_sensorium.profile：C0 模态集/校准版本/C0 增益形态/质量度量纲——纯 profile 参数，不含认知语义参数） | **AI-v2：初值集成文采纳**（数值见 c0_sensorium.profile.yaml v1.0，均标注初值；定值原则承 Q-G00-08/Q-G00-11 先例）。① **C0 模态集四类** {EXT_LOCAL_OBS, EXT_EVENT, INTERO, PROPRIO}——≥2 外感受 + ≥1 内感受满足 L02 §9 C0 门槛；EXT_LOCAL_OBS 源 = observation_window 载荷、EXT_EVENT 源 = interoceptive_state 载荷事件列表（威胁观测形成面）、INTERO 源 = 同载荷水平字段（Q-L02-05 四 sensation）、PROPRIO 源 = proprioceptive_state 载荷；**OUTCOME 通道不入 sensorium**（效果回传归 L10 归属域，ReceivedOutcome 非感觉）；② 校准单版本 id = `c0-static-v1`（运行期只读常量；漂移策略 Q-L02-01 归 C1）；③ **C0 期增益 = 恒等 1.0**（PROFILE 来源、无调制入口——gain_max 上界与 GainReceipt 归 C2，Q-L02-02 不预支）；④ 质量度量纲 C0 = {completeness [0,1], corruption_flags 枚举, snr_est 占位}（跨模态归一标度 Q-L02-04 归 C1）。全部为 C0 初值带 C0 数据复核点。重开条件：C0 实现期对照实验显示任一初值致盲区/饱和 → 经新 Q 重标定（改值 = profile 新版本） | 2026-10-02 |

## B. 全局未决（G 系列）

| Q 号 | 议题 | 建议默认 | 依赖 | 状态 |
|---|---|---|---|---|
| Q-G00-01 | **（指针，非独立登记项）** T0–T6 频率——所有权在 **Q-L00-01**（L00 §5 比例 N2/N3/N4/N5=2/4/16/64）；本行仅当基准 cycle→墙钟绝对时基需裁决时启用 | — | F0 profile 冻结 | 见 Q-L00-01 |
| Q-G00-02 | **（指针，非独立登记项）** MW0 观测窗与边界——所有权在 **Q-L01-01**（egocentric 5×5 + 衰减）与 **Q-L01-02**（torus vs 墙） | — | M0 | 见 Q-L01-01 / Q-L01-02 |
| Q-G00-03 | 团队规模与总工期假设（10-14 人 / 25-38 月） | 卡片原值 | 仅规划参考 | UNCONFIRMED |
| Q-G00-05 | 持续极端 aversive-like 状态的伦理评审阈值与处置（暂停/调整/终止） | 触发即暂停 claim-relevant 运行 + 人工评审 | E1 前 | UNCONFIRMED |

## C. L00 横切基础

| Q 号 | 议题 | 建议默认 | 状态 |
|---|---|---|---|
| ~~Q-L00-03~~ | ~~float64 统一是否接受存储/性能代价~~ **CLOSED**：与 Q-T10 裁决（模型 float32、证据/统计 float64，2026-09-12 CONFIRMED）重复且措辞冲突，已废弃归并入 Q-T10；编号不复用 | — | CLOSED |
| Q-L00-06 | registry 大 artifact 分片阈值 | 8 MiB 分片 | UNCONFIRMED |
| Q-L00-07 | Hypothesis packet 序列生成分布 | 谱系感知 + 对抗混合 | UNCONFIRMED |

## D. L01 环境与通道

| Q 号 | 议题 | 建议默认 | 状态 |
|---|---|---|---|
| Q-L01-07 | M1 是否引入第二可控代理（伪社会线索） | 推迟到 C4 | UNCONFIRMED |

## E. L02 感觉形成（Sensorium）

| Q 号 | 议题 | 建议默认 | 依赖 | 状态 |
|---|---|---|---|---|
| Q-L02-02 | `gain_max[modality]` 默认上界与裁剪是否计入"调制有效性"判据 | — | C2 | UNCONFIRMED |
| Q-L02-07 | C5 新模态适配是否需独立 protection 场景（防适配破坏既有模态） | — | C5 | UNCONFIRMED |

## F. L03 知觉（Perception）

| Q 号 | 议题 | 建议默认 | 依赖 | 状态 |
|---|---|---|---|---|
| Q-L03-06 | affordance 的 `action_class` 枚举与 L09/L10 能力契约的对齐方式 | — | C3/C4 | UNCONFIRMED |

## G. L04 世界/身体/自我模型

| Q 号 | 议题 | 建议默认 | 依赖 | 状态 |
|---|---|---|---|---|
| Q-L04-05 | `CapabilityEstimate` 的 action_class 粒度 | — | C3/C4；联动 Q-L03-06 | UNCONFIRMED |

## H. L05 驱力/评价/情感（九维动力学）

| Q 号 | 议题 | 建议默认 | 依赖 | 状态 |
|---|---|---|---|---|
| Q-L05-01 | 九维的取值域与量纲（[0,1] vs [-1,1]，valence 是否对称）与跨维可比性 | — | C2 | UNCONFIRMED |
| Q-L05-02 | 内稳态误差权重 `w_d` 默认值与是否允许 appraisal 有界动态调整（幅度上界） | — | C2 | UNCONFIRMED |
| Q-L05-03 | 各维时间常数 τ、迟滞带宽、衰减率的默认谱 | — | C2；联动 Q-L00-01 | UNCONFIRMED |
| Q-L05-05 | 持续极端 aversive-like 状态的触发阈值与持续时长 | — | E1 前（伦理）；**须与 Q-G00-05 一致** | UNCONFIRMED |
| Q-L05-06 | `tendencies.action_class` 枚举 | — | C3/C4；联动 Q-L03-06、Q-L04-05 | UNCONFIRMED |
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

## K. L08 动机/目标（M1 最小 → C3 完整）

| Q 号 | 议题 | 建议默认 | 依赖 | 状态 |
|---|---|---|---|---|
| Q-L08-03 | Pareto 仲裁的多目标向量分量定义与默认权重 | — | C3 | UNCONFIRMED |
| Q-L08-04 | front 内优先序（viability > 规范 > 承诺 > 其余？）是否成立及例外条件 | — | C3；联动 Q-L09-02 | UNCONFIRMED |
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
| Q-L09-07 | `SEEK_HELP` 在单主体（D-14）期的对象定义（人类研究者？实验控制？）与其权限边界 | — | C3/C4；联动 Q-L12-08 | UNCONFIRMED |

## M. L10 行动/网关/PhysIO/归属

| Q 号 | 议题 | 建议默认 | 依赖 | 状态 |
|---|---|---|---|---|
| Q-L10-05 | 概率 agency 后验的计算形式与校准判据 | — | C4；同源 Q-L03-04 | UNCONFIRMED |
| Q-L10-07 | gateway policy 更新流程（promotion + 重授权 + 审计）与"重大变化"的判定 | — | C5/H1 | UNCONFIRMED |
| Q-L10-08 | 急停响应时间上界与在途命令的终止语义（部分执行如何处理） | — | P1/H1 | UNCONFIRMED |

## N. L11 学习/巩固

| Q 号 | 议题 | 建议默认 | 依赖 | 状态 |
|---|---|---|---|---|
| Q-L11-02 | replay 选择策略默认权重（情感标注/新颖性/误差/时间多样性）与 budget 默认 | — | C5 | UNCONFIRMED |
| Q-L11-03 | promotion 判据的多目标组合形式（Pareto + 保护硬约束）与最小改善阈值 | — | C5；联动 Q-L13-07 | UNCONFIRMED |
| Q-L11-04 | 保护集回退判定阈值（delta 显著性/效应量） | — | C5/E1；联动 Q-L06-05 | UNCONFIRMED |
| Q-L11-08 | 灾难性遗忘保持率的冻结阈值与回归场景最小集 | — | C5/E1 | UNCONFIRMED |

## O. L12 语言/社会认知

| Q 号 | 议题 | 建议默认 | 依赖 | 状态 |
|---|---|---|---|---|
| Q-L12-01 | C4 期 typed LLM 角色的最终清单与是否全部启用（R-TRANSLATE 是否保留） | 8 角色（§4.1 表） | C4 | UNCONFIRMED |
| Q-L12-03 | LLM 非确定性处理：录制回放模式是否为 claim-relevant 运行的**唯一**允许方式（在线调用仅探索用） | — | C4 + L00 | UNCONFIRMED |
| Q-L12-04 | 他者模型最小集字段（存在/意图/知识/承诺）与 D-14 单主体期的封锁范围 | — | C4 | UNCONFIRMED |
| Q-L12-05 | 自我报告一致性判定的比较对象与阈值；DIVERGENT 的处置 | — | C4/E1 | UNCONFIRMED |
| Q-L12-06 | 语言陈述作为 L03 低置信线索的置信度上限（防"听说即相信"） | — | C4 + L03 | UNCONFIRMED |
| Q-L12-07 | 中央 LLM 消融的"非语言核心功能保持"判据阈值（保持率下限） | — | C4/E1 + L13 | UNCONFIRMED |
| Q-L12-08 | 求助对象定义与其权限边界 | — | C3/C4；联动 Q-L09-07 | UNCONFIRMED |

## P. L13 证据/评价/registry 治理

| Q 号 | 议题 | 建议默认 | 依赖 | 状态 |
|---|---|---|---|---|
| Q-L13-06 | 保护集"只增不减"的退役裁定流程与回退阈值 | — | C5/E1；联动 Q-L11-04、Q-L06-05 | UNCONFIRMED |
| Q-L13-07 | promotion 多目标判据的组合形式与最小改善阈 | — | C5；联动 Q-L11-03 | UNCONFIRMED |
| Q-L13-08 | I2/I3 的"独立"标准（实现者/环境/seed 隔离程度）与一致性判据 | — | E1/H1 | UNCONFIRMED |
| Q-L13-10 | 静态报告的最小集与导出频率（只读、无服务化） | — | H1 | UNCONFIRMED |

## Q. 跨档联动与 F0 阻断清单（裁决时须成组处理）

**必须成组裁决的联动对**：

| 组 | Q 号 | 联动原因 |
|---|---|---|
| 时基谱 | Q-L00-01 ↔ Q-L05-03 | 情感时间常数依赖 T 级频率比 |
| regime ↔ 情感模式 | Q-L01-03 ↔ Q-L05-04 | 同一参数化在两处出现（已成组裁决 2026-09-25，见 A 区） |
| 伦理阈 | Q-G00-05 ↔ Q-L05-05 | 两项必须同时裁决（authority v2 下为 AI 难逆级成文裁决：ADR-G + tag；owner 否决权保留） |
| 能力粒度 | Q-L03-06 ↔ Q-L04-05 ↔ Q-L05-06 | `action_class` 枚举三处共用 |
| 误差标度 | Q-L02-06 ↔ Q-L03-01 ↔ Q-L09-08 | 三层误差比较需共同标度 |
| Reflex 边界 | Q-L09-06 ↔ Q-L10-09 | containment 不得双写（已成组裁决 2026-09-25，见 A 区） |
| 求助对象 | Q-L09-07 ↔ Q-L12-08 | 单主体期的权限边界 |
| 保护集 | Q-L06-05 ↔ Q-L11-04 ↔ Q-L13-06 | 保护集构成、阈值、治理一体 |
| promotion 判据 | Q-L11-03 ↔ Q-L13-07 | 多目标判据与统计阈值 |
| 分片与治理 | Q-L00-06 ↔ Q-L06-07 | tombstone 保留依赖 registry 分片 |

**F0 冻结的直接阻断项**：**已清零**（2026-09-23 AI-v2 成文裁决 21 项，见 A 区当日批次——Q-L01-06、Q-G00-06、Q-G00-04+Q-L13-04、Q-L10-01/-03/-06、Q-L11-07、Q-L12-02、Q-L13-01/-02/-09 及 Q-L13-09 联动 7 项（Q-L10-04 归联动组）；Q-L00-01/-02 于 ACT-07 执行中补裁，此前漏列）。**F0 已冻结**（ADR-G-0002 + tag `f0-freeze`，2026-09-23，7 份合同文件）。

**M0 阻断项**：**已清零**（2026-09-25 AI-v2 成组裁决 9 项——Q-L00-04、Q-L01-01…04+Q-L05-04、Q-L09-06+Q-L10-09、Q-L10-02；见 A 区）。**M0 已退出**（ADR-G-0005 + tag `m0-exit`，2026-09-25）。

**M1 阻断项**：**已清零**（Q-L08-01/-06 于 2026-09-26 M1 准备单元裁决；Q-L08-02/-09 于 2026-09-26 M1 门冻结单元裁决——均见 A 区；`m1_goals_min.profile.yaml` 随 ADR-G-0006 冻结）。**M1 已退出**（ADR-G-0007 + tag `m1-exit`，2026-09-26，REV-0007 PASS-WITH-FINDINGS R1–R9 全闭环）。**M2 侧硬前置（移交）**：L13 EvidenceResult 首评（stat plan m1_goals_sc3_sc4 v1.1 两 claim × n=64 种子化 run）**不晚于 M2 门退出**（ADR-G-0007 口径钉死第 2 条）；ADR-G-0005 R8 profile digest 匹配随 M2 实验控制模块落地。**首评完成（2026-09-26，M2 准备一）**：real_vs_pseudo_motive = SUPPORTED（配对差 0.984，McNemar p=2.2e-19，伪注入惰性、复算全等）；wording_manipulation_null = SUPPORTED（χ² 同质性 p=0.379）——硬前置兑现。**首评更正（对 ADR-G-0007 口径第 3 条）**：M0 冻结 0.01 传输损坏率使 trial 真实带噪，"指纹全等"确定性 shortcut 前提不成立，null 断言以冻结计划的统计形式（χ² 同质性）为准；depleted 臂 1/64 采纳 = 关键 intero 包损坏的诚实容错行为。

**M2 阻断项**：**已清零**（2026-09-26 M2 门冻结单元 AI-v2 四项——Q-L00-05 checkpoint 双机制、Q-L04-06 谱系断裂主判据、Q-L11-05 集合级可区分性、Q-G00-11 M2 初值集伞式；见 A 区；`m2_continuity.profile.yaml` 随 ADR-G-0008 冻结）。

**M2 已退出**（ADR-G-0009 + tag `m2-exit`，2026-10-02，REV-0009 PASS-WITH-FINDINGS R1–R10 全闭环——R1(S1) 经口径裁定：M2 满足口径 = 机械因果证明 + 冻结协议，ADR-G-0007 同源）。

**R0 侧硬前置（移交，ADR-G-0009 口径裁定）**：① m2_continuity_carryover 首评（stat plan m2_continuity_sc5_sc6 v1.0，n=64 sealed）**≤ R0 门退出**；② sealed 网格基础设施（`registry://sealed/` 命名空间 + SealedEvaluationToken + F0 分割流一次性生成与 digest 入册，Q-L13-02 合同义务）为其必然前置；③ SC6 正式 runner 三点保真度（regime 网格继承/naive 断连经 fault/ITT 流驱动两臂）；④ **顺延终止条款：C1 起统计评价为各 claim 门退出的不可顺延判据**（确定性阶段理由消失）；⑤ 三步纠偏闭环全链 → C5。

**R0 硬前置完成（2026-10-02，R0 准备单元）**：① **carryover 首评 = SUPPORTED**（sealed 网格 96 cells → sealed 28 / internal 68，分割 digest `9b99d26f…`、manifest 入册 `bc68e3ac…`；n=64 ITT 均衡 [30,34]；carry 64/64 vs naive 0/64，配对差 = 1.0（饱和上确界），McNemar p ≈ 1.08e-19，I1 bit-exact）；② sealed 基础设施落地（evidence/evaluator/sealed.py：双类型 token 隔离 + SealedNamespace + check_no_backflow——17 份 config digest ∩ sealed = ∅ 机械验证）；③ SC6 正式 runner 三点保真度交付（runs.py `run_carryover`；REV-0009 R9 闭合）；**根 EvidenceResult `R-r0-root-001` = SUPPORTED**（复合判定 Q-L13-11①：M1 两 claim + carryover + leakage=0（14 探针 0 检出，digest `961a0ef8…`）+ I1 match；effect_size/CI/p 由 sealed carryover 核承载）。④⑤ 维持原判（C1/C5 期义务）。**R0 已退出**（ADR-G-0010 + tag `r0-exit`，2026-10-02，REV-0010 PASS-WITH-FINDINGS R1–R8 全闭环）：根 EvidenceResult `R-r0-root-001` = SUPPORTED + ExpansionDecision `EXP-R0-001` = **ALLOW_NEXT_STAGE**（分别记录，Q-L13-03；decide_from_root 机械映射）。R1 强制补裁 = Q-L13-12（run 主种子/内容锚）。R5 跟踪：正式评价入口 → C0 准备单元（**已交付**，见下）。

**C0 门已冻结**（ADR-G-0011 + tag `c0-freeze`，2026-10-03，REV-0011 PASS-WITH-FINDINGS R1–R7 全闭环——R1(S1) 注记层失实更正（"精确复现钉死"宣称被实证推翻，裁决本体诚实）、R2 防覆盖守卫即修+归档机制跟踪、R7 约束核对/保护集增补/白名单复核 → C0 实现期首单元）：冻结物 `config/profiles/c0_sensorium.profile.yaml` v1.0；C0 阻断清零（Q-L02-03/-05 + Q-G00-12，登记册 71/72/1）；正式评价入口 entry.py 交付（REV-0010 R5 收敛；SC3 全量 n=64 复现精确恒等；Q-L13-12④ SC4 派生格式成文钉死 + χ² 敏感性方法学发现 + **C1 起统计计划必须内嵌种子派生格式冻结**）。**当前 = C0 实现期**：首单元 = R7 义务（约束深化核对 + protection_suite C0 增补 + containment 白名单复核）→ sensorium 十二件 + typed loader + 旁路保护 + bit-exact 重放 → REV-0012 → c0-exit（L02 §1 成功判据 + HLD §10.4 C0 行）。

**C0 已退出**（ADR-G-0012 + tag `c0-exit`，2026-10-03，REV-0012 PASS-WITH-FINDINGS R1–R8 全闭环）→ **C1 准备**（一：15 项成批裁决 + R7/R8 交付；二：可行性探针首跑 + c1_perception_models.profile v1.0；**C1 门已冻结**——ADR-G-0013 + tag `c1-freeze`，2026-10-05，REV-0013 PASS-WITH-FINDINGS R1–R6 全闭环；登记册 87/57/1）。

**R4 前置登记（本段为登记缺口补正，2026-10-05）**：REV-0013 R4 处置声称"登记册 footer"已登记 C1 实现期首单元显式第一前置，开工核实发现 footer 实际止于 C0 段——注记层失实，本段补正。前置内容：**世界模型转移语义批（persistence vs respawn/storm、表格适应初始化）**——M0 型实现期无源常量防线。**本批清零（Q-L04-09/-10/-11 新增即裁，2026-10-05）**：转移语义 = 持续性 + 事件条件更新（禁信念内模拟隐藏真值过程）；适应初始化 = 零计数 + Laplace 等价步长 0.125 + C1 提案不生效；先验 regime 语义 = initial_regime 覆盖率恒定。

**当前 = C1 实现期**：首单元 = 转移语义批（↑已裁）→ `galatea/subject/perception/`（L03 表格贝叶斯全量）+ `galatea/subject/models/`（L04 三模型）+ L02 pred_error C1 接线 + L11 有界适应提案件 + c1 profile typed loader → 冻结统计计划 n≥64 sealed 评价（顺延终止条款生效，种子派生入计划）→ REV-0014 → c1-exit。

**REV-0014 闭环登记（2026-10-05）**：评审判定 BLOCK（R1 S1：8db65ce 提交态 runs_c1 序列化回归 `str(bytes)` 使 runner 全包判损坏——归档数据真实性经评审三条独立链证明非 S0）→ 闭环：R1 修复（显式 decode）+ 回归测试（galatea/evidence/tests/test_c1_runner_end_to_end.py——INC-08 纪律：runner 取包路径此前零覆盖）+ 自 HEAD 重跑 n=64 正式评价；R2(S3) body claim CI 修复（min-d 判据 Wald CI 替代点估计占位）；R3(S3) Holm–Bonferroni 校正机械执行（evaluate_c1_composite + holm_bonferroni——stat plan correction 冻结面此前未接线）；R4(S3) **Q-L13-05 余项显式再登记**（本行即登记动作）：生产路径运行时钩子扩展 + DuckDB 查询面扩展 → **C2 准备单元首项交付**（C2 门冻结前置，未交付不冻结）；R5–R9(S4) 即修/勘误（保护集计数 +12/52、config 21 份、注释漂移、解离断言名语义对齐留 ADR-G-0014、ECE 每箱 ≥30 机械断言 + P12 范围注记）。
