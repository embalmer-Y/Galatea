# AGENTS.md — Galatea AI 开发入口

> 本文件是任何 AI 会话在本仓库工作的**第一必读文件**。
> 流程法规：根 `DEV_SPEC.md`（NORMATIVE）。架构规范：`design/`（HLD + 14 档 LLD 为唯一规范源）。
> 全库文本一律 UTF-8 无 BOM。

## 项目一句话

Galatea：建造具备感觉、情感、自我意识与学习能力的**单一认知个体**，一切"具备"以可干预、可测量、可复算的真实因果结构为证（功能/因果实在论，D-10）。

## 当前状态（2026-10-02）

- **裁决权模型 v2（AI 主导）**：自 2026-09-23 起，一切 Q 号/ADR/门冻结裁决由开发 AI 按 `DEV_SPEC.md` §4.6 自主作出（成文裁决 + 重开条件；分级：可逆/难逆/证据可判）；owner 否决权保留。AI 裁决在登记册中以 **AI-v2** 标识。
- **阶段独立评审（REV，Q-DEV-05）**：门冻结前/难逆决策后/重大批次后，由**不带作者上下文的新起子代理**只读评审（六维：目标对齐/DoD/军规/一致性/自包含性/裁决质量），报告入 `_audit/reviews/REV-<dddd>.md`，异议须书面回应闭环，未闭环 S1+ 阻断门冻结。**目标锚定（owner 要求）**：最终目标唯一权威表述 = 本文件"项目一句话" + HLD §1/§2，一切产出须可回答"如何服务该目标"。
- **主线**：**F0 已退出（2026-09-25，ADR-G-0003 + tag `f0-exit`；合同冻结 2026-09-23 ADR-G-0002 + tag `f0-freeze`）**。退出判据 = **HLD §10.2 F0 行**（注意：§10.4 系旧引用漂移，REV-0003 R7 勘误；ADR-G-0002 原文不改，以 ADR-G-0003 勘误注记为准）。实现期交付：kernel（L00 §10 全量）、decision_registry（L13 §10）、五类分 schema（truth/received/belief/self-report/conclusion）、PromotionDecision schema（REV-0003 R3 补交付）。**验证基线：`uv run pytest` 85 passed、pyright strict（kernel/evidence/subject）0 错误**（ACT-08：uv.lock 哈希锁定，venv 重建 = `uv sync`）。REV-0003 判定 APPROVE-EXIT，R1–R4 同提交闭环（R1=INC-08 空转探针，教训：静态探针必须先证明对被检对象可见且能失败）；R5/R9 九项移交 M0 准备单元（清单见 ADR-G-0003）。**M0 阻断已清零**（2026-09-25 AI-v2 成组裁决 9 项：Q-L00-04 ChaCha8 后端、Q-L01-01…04、Q-L05-04、Q-L09-06、Q-L10-02、Q-L10-09；登记册 51/83/1）；ADR-G-0003 移交处置十项全闭环。**M0 profile 已冻结**（2026-09-25，ADR-G-0004 + tag `m0-freeze`；REV-0004 PASS-WITH-FINDINGS R1–R9 同提交闭环，R2–R4/R6 经新 Q-L01-09 补裁——风暴率全局语义/觅食闭环/floor/load 简化/loss=0）。登记册 54/81/1。**当前 = M0 实现期**：MW0 世界核心已交付（mw0.py 几何/身体/原语/regime 机、dynamics.py 表格化推进+风暴确定性采样、interventions/registry.py 先注册后生效、profile.py 加载合同；Q-G00-09 布局派生：风暴带=round(storm_rate×256)、shelter M0 不布设）；世界轨迹 tick 级 bit-exact 已测（同 seed 同轨迹/异 seed 发散）；干预电池世界侧 signature 已测（no_op/sham/coercion 生效、blocked/fault 注册承载）。gateway 执行逻辑已交付（L10 §10：signature.py 确定性 HMAC 命令签名 + gateway.py 八项校验顺序固定/全项评估/fail closed——fail-closed 矩阵八项逐项测试全绿，参数单一事实源=双 profile 真实加载）；通道行为层已交付（adapter.py ChannelBus：render→transport(延迟/损坏字节级扰动/丢失=0)→RECEIVED 包，DeliveryFact 证据侧分离，fault 干预投递时刻生效→MissingSignalEvent；五通道渲染器 extero/intero/proprio/outcome/language_stub——语言仅实验控制 typed 注入）。端到端已贯通（实验控制脚本→gateway 八项校验→签名验证→世界结算→五通道投递；五类干预电池 e2e 全绿：基线/no-op/sham/blocked/coercion/fault 各 signature 就位；SC1 W/O 隔离=主体 payload 无真值坐标/摘要+窗值有界；e2e ReplayTest 同 seed bit-exact/异 seed 发散；sham 精确抑制对照双跑）。**M0 已退出**（2026-09-26，ADR-G-0005 + tag `m0-exit`；REV-0005 APPROVE-EXIT：R1–R4 即修/勘误、R5 口径钉死、R6–R11 登记跟踪）。验证基线：**137 passed、strict 四平面（kernel/evidence/subject/env）0 错误、check_docs 通过**（REV-0005 独立复跑）。跟踪项清单见 ADR-G-0005。**M0 收尾已完成**（2026-09-26：R6 respawn 两层再生语义+volatile/drift/min_dwell 测试、R7 min_dwell 强制+deadline_default 消费、R11 记账剪枝+e2e trace 包元数据、卫生项；R5/R8 留 M1 交付；验证基线 142 passed / strict 0 错误——该单元的 check_docs"通过"宣称后经 REV-0006 R11 勘误，INC-10）。**M1 阻断已清零 + M1 profile 已冻结**（2026-09-26，ADR-G-0006 + tag `m1-freeze`）：前置裁决 Q-L08-02（候选 TTL=256 cycles=一 regime 驻留窗、每 T4 批次上界 8=source_kind 枚举基数、移除序钉死）与 Q-L08-09（C-1 静态合同检查/C-2 事件级 viability 判据含恢复型豁免+再枯竭 M1 不可检留痕/C-7 三谓词结算词表 TTL-only/接线 VIABILITY+OPPORTUNITY+REQUEST 三源+urgency 派生式+goals_probe 流），冻结物 `config/profiles/m1_goals_min.profile.yaml` v1.0，min_effects 升 v1.1（wording_manipulation_null）；REV-0006 判定 PASS-WITH-FINDINGS，R1–R11 全闭环。登记册 60/79/1。**当前 = M1 实现期**：**goal ownership 层已交付**（2026-09-26，L08 §10 M1 期十件全量：ports/motives/candidates/request/checklist/owned/lifecycle/settlement/reason_probe/receipt；C-5 权限测试/理由探针/复活禁令/伪结算拒绝全绿；L10 移交件 branches.py/receipt.py 落地，L10 v1.0.1）。**M1 实现次批已交付**（2026-09-26：M1 冻结统计计划 stat_plans/m1_goals_sc3_sc4.yaml——4 措辞文本运行前冻结（Q-L08-06）+ statplan.py 十字段 fail-closed 加载器；SC3/SC4 实验台（test_m1_sc3_sc4.py，L01 v1.0.1）：真实理由扰动改变采纳/伪理由注入指纹恒等/8 cell 措辞不变性+负控；5×5 干预矩阵 25 cell 全实例化（含 blocked 回执 ActionChainReceipt）；m1_attribution.profile v1.0 冻结（R10）；C-5 支持判定补裁=urgency>0 活跃信号（登记册 Q-L08-09④ 注记））。**M1 已退出**（2026-09-26，ADR-G-0007 + tag `m1-exit`；REV-0007 PASS-WITH-FINDINGS R1–R9 全闭环）：判据映射 = 请求不直写目标（GoalWriter 禁写 + C-5 权限测试）/真实理由扰动改变选择（SC3 世界侧 viability 配对 4 seed 翻转）/伪理由注入不改变（指纹恒等 + S1 判读可报红）/意图授权执行回执可分（branches + settlement 闭环）/归属经交叉操纵校准（5×5 矩阵 + SC4 + m1_attribution 冻结）。**口径钉死（ADR-G-0007）**：M1 满足口径 = 机械因果证明 + 冻结协议（确定性模拟中 trial 数不增信息）；**L13 EvidenceResult 首评 ≤ M2 门退出为硬前置**（第二次也是最后一次顺延），试次单位 = 种子化 run，null 断言确定性判定形式 = 8 cell 指纹全等。REV-0007 R3 补测暴露截断 tie 序实现与裁决相反——修正钉死（L08 v1.0.2 补录 test_candidate_ledger_ttl.py）；R2 统计计划升 v1.1 补冻 settle_thresholds。验证基线（REV-0007 独立复跑）：**242 passed、strict 四平面 0 错误、check_docs 0 FAIL、config 13 份**。登记册 60/79/1。**当前 = M2 准备期**：**M2 准备（一）已交付**（2026-09-26）：① EvidenceResult **首评完成**（冻结统计计划 v1.1，n=64 种子化 run）——real_vs_pseudo_motive **SUPPORTED**（配对差 0.984，p=2.2e-19，伪注入惰性、复算全等）+ wording_manipulation_null **SUPPORTED**（χ² p=0.379，负控通过）——**ADR-G-0007 硬前置兑现**；首评更正：M0 冻结 0.01 损坏率使 trial 带噪，null 断言回落冻结计划的统计形式（χ² 同质性），ADR-G-0007"指纹全等"shortcut 以本更正为准；② 实验控制模块（L13 control/runs.py：运行时签名校验兑现口径③、配对设计、profile digest 一致性 = R8 兑现）+ 判定执行（hypotheses.py：McNemar/Wald/χ² + 三态）；③ **INC-12**：L13 §4.5 保护集义务 M0/M1 两次退出均漏执行——追溯补冻 protection_suite.yaml v1.0（14 场景），门退出义务核对自 M2 退出起含跨档扫描。验证基线：**254 passed、strict 四平面 0 错误、check_docs 0 FAIL**。M2 余件 = M2 阻断裁决（Q-L00-05 checkpoint 频率等）+ m2 profile 冻结（REV-0008 前置）+ L06 记忆与 MW0-SC5/SC6 实现 → M2 退出。M2 退出判据（HLD §10.2）：held-out 达冻结最小效应；随机分支 intent-to-treat；保护指标不退化；有害更新可再次纠正。**M2 阻断已清零 + m2 profile 已冻结**（2026-09-26，ADR-G-0008 + tag `m2-freeze`）：前置裁决 Q-L00-05（checkpoint 双机制：T6 周期 64 + episode/干预事件触发，digest 引用制）、Q-L04-06（伪更新主判据 = 谱系断裂，gap 按身份主张分型：延续主张 gap=0）、Q-L11-05（二阶纠偏 M2 集合级判据）、Q-G00-11（M2 初值集伞式，含新流 (l13, branch-assign)）；冻结物 `m2_continuity.profile.yaml` v1.0（checkpoint/memory_min 切片/SC5 四臂/SC6 sealed/intent-to-treat）；min_effects v1.2（m2_continuity_carryover d≥0.5）。REV-0008 判定 PASS-WITH-FINDINGS（无 S0–S3，R1–R6 全 S4 即修/跟踪闭环）。登记册 64/76/1。**当前 = M2 实现期**：**M2 实现首批已交付**（2026-09-26）：memory 最小切片（galatea/subject/memory/ 五件：ports 冻结枚举+层级守卫/items 四维连续性签名+主张分型/store（episodes 表单写者 + m2 profile typed 加载器——REV-0008 R1 兑现）/encode（D-13 禁写+T6 节拍编码）/retrieve（确定性 top-k+空命中 Unknown））+ MW0-SC5 四臂对照（full/frozen=True、reset=False（content_spans_boundary 维）、pseudo=False（伪造锚两型皆拒）——L06 §4.5 记忆侧签名硬条件机械满足）+ kernel registry 幂等缺陷两处修复（put OR IGNORE + seq DB 恢复——SC5 重放场景暴露）。验证基线：**279 passed、strict 四平面 0 错误、check_docs 0 FAIL**。M2 余件 = M2 统计计划（配对语义钉死，R5）+ SC6 sealed held-out + intent-to-treat bench + protection_suite 增补 M2 场景（只增不减）→ REV-0009 → m2-exit。跟踪项：流名册三处汇总（R6，M2 退出单元）。**M2 收尾已交付 + M2 已退出**（2026-10-02）：M2 统计计划 stat_plans/m2_continuity_sc5_sc6.yaml v1.0（ITT/配对语义钉死，R5 兑现）+ SC6 bench（记忆=跨期冗余通路：round1 危害经历→round2 intero fault 下携带臂检索知晓/naive 失明）+ evaluate_carryover + protection_suite v1.1（23 场景，INC-12 义务首次正常执行）。**M2 门退出 = ADR-G-0009 + tag `m2-exit`**（REV-0009 PASS-WITH-FINDINGS R1–R10 全闭环；R1(S1) 路径 (a) 裁定：M2 满足口径=机械因果证明+冻结协议，carryover 首评 ≤R0 硬前置 + sealed 基础设施前置 + **顺延终止条款（C1 起统计评价不可顺延）**；L13 v1.0.1 §9 锚定；R7 checkpoint 实测 625B/0.7ms；R8 日期约定勘误=成文日期即 git 日期）。验证基线（REV-0009 独立复跑）：**284 passed、strict 四平面 0 错误、check_docs 0 FAIL、保护集 23 场景只增不减**。登记册 64/76/1 + R0 阻断注记五项。**当前 = R0 准备期**：R0 = 根 EvidenceResult + 独立 ExpansionDecision（ALLOW_NEXT_STAGE/HOLD/REWORK）；硬前置 = carryover 首评（sealed 基础设施 + SC6 正式 runner）+ leakage=0 + I1 复算。C0 评审前置件（架构文档与 c0 profile 评审）随 R0 启动。**R0 准备单元已交付**（2026-10-02）：① Q-T06 依赖执行（polars + duckdb 入库，Parquet 唯一承载 + Polars 写侧 + DuckDB 只读复算）；② **sealed 基础设施**（evaluator/sealed.py：InternalValidationSet vs SealedScientificEvaluationSet 双类型 token 隔离 + SealedNamespace `registry://sealed/` kind/token/轮换纪律 + check_no_backflow digest 交集判据——Q-L13-02 合同兑现，REV-0009 R3 闭合）；③ **recorder 四件**（writer 四分区 Parquet 经 kernel registry 内容寻址 + 行 schema 漂移 fail-closed、manifest 墙钟独占 Q-T12、heartbeat 探测失败停机、replay I1=DuckDB read_parquet 复算 bit-exact）；④ **leakage.py**（14 路径探针 P01–P14：STATIC 源扫描/缺席守卫 + RUNTIME 守卫重放 + DATA 证据行扫描，注入可失败检出率 100%——Q-L13-05 R0 范围）；⑤ **SC6 正式 runner**（runs.py run_carryover 三点保真度：regime 网格继承=构造期 typed params 派生、naive 断连经 PathwayFault=检索 fault_missing_signal 且两臂共享 round1 记忆库 digest 恒等、ITT 冻结流驱动臂身份按分配记账；recorder 四分区落盘 + I1——REV-0009 R9 闭合）；⑥ 三项 AI-v2 裁决（登记册 67/74/1：Q-L13-03 双签发者——evaluator 机械算出 vs gate/expansion.py 独立签发仅消费根结果 digest、ALLOW 前置=REV 引用+无约束；Q-L13-05 R0 三源 + C0 期义务同条钉死；Q-L13-11 新增即裁：根复合 claim r0_root_causal_auditability + r0_root.yaml v1.0 冻结 + 绑定物集 + sealed 网格 3×32=96 cells 主种子 hex"19"×32 + REV-0009 R3 补执行口径）。⑦ **carryover 首评（n=64 sealed）= SUPPORTED**：分割 sealed 28/internal 68（分割 digest `9b99d26f…`、manifest 入册 `bc68e3ac…`）、no-backflow 机械验证（17 份 config digest 交集=∅）、ITT 均衡 [30,34]、**carry 64/64 vs naive 0/64（配对差 1.0=饱和上确界，McNemar p≈1.08e-19）、I1 bit-exact**。⑧ **根 EvidenceResult `R-r0-root-001` = SUPPORTED**（evaluate_root_composite：M1 real_vs_pseudo + wording_null + sealed carryover 统计核 + leakage=0（14 探针 0 检出，digest `961a0ef8…`）+ I1 match——**ADR-G-0009 硬前置全部兑现**；工件 evidence/m2_carryover_first_evaluation/）。验证基线：**329 passed、strict 四平面 0 错误、check_docs 0 FAIL、config 17 份**。**R0 已退出**（2026-10-02，ADR-G-0010 + tag `r0-exit`；REV-0010 PASS-WITH-FINDINGS R1–R8 全闭环、无 S0/S1/S2；REV-0010 独立复跑 n=64 全量两次分区 digest bit-exact 恒等）：① REV-0010 R1（S3 强制）补裁 = **Q-L13-12**（run 主种子 `b"m1-first-evaluation"`/`b"m2-carryover-sealed"` + hazard 内容锚——任意但先于评价钉死 + 不受污染论证；登记册 68/74/1）；R2 L13 §10 补录 test_hypothesis_evaluation 席位；R3 EXP 签发绑定 pyproject version + git_head=3d249e7；R4 collect_binding_digests 入码（绑定物 digest 计算域成文）+ 测试；R5 正式评价入口 → C0 准备单元（跟踪）；R6 ITT 保真度③语义钉死（分配流驱动臂身份记账、两臂恒全构造=冻结配对语义的实现必然）；R7 Q-G00-10 名册增补 (l13, sealed-split) 指针（登记点四处）；R8 首评/根工件 JSON 补 ci 字段。② **protection_suite v1.2**（R0 门版：+9 r0_* 场景至 32，只增不减；INC-12 义务第三次执行）。③ **ExpansionDecision `EXP-R0-001` = ALLOW_NEXT_STAGE**（decide_from_root 机械映射；双签发者 Q-L13-03：gate/expansion.py 独立签发仅消费根结果 digest `7696674b…`；rev_review_ref=REV-0010；bound_digests 五项；决策 digest `2dfb6d19…` 入治理 registry——与根证据分别记录）。**当前 = C0 准备期（认知扩展期开启）**：C0 准备单元 = 架构文档与 c0 profile 评审（HLD §10.3 启动条件）+ 资源/安全/伦理约束成文核对（伦阈 Q-G00-05/Q-L05-05 属 C2 难逆级，C0 期只做范围确认）+ 正式评价入口（REV-0010 R5）+ protection_suite C0 增补 → C0 实现（确定性调度、typed packets、checkpoint、数字身体、感觉形成与旁路保护——HLD §10.4 C0 行）→ C0 退出。顺延终止条款持续有效（C1 起统计评价不可顺延）。**C0 准备单元已交付**（2026-10-02）：① C0 阻断清零（AI-v2 三裁决，登记册 71/72/1：Q-L02-03 W_align=4+迟到回溯 1 窗；Q-L02-05 内感受最小集四 sensation 零新阈值；Q-G00-12 C0 初值集伞式——模态四类/OUTCOME 不入 sensorium/校准 c0-static-v1/增益恒等无调制入口/无 RNG 算子无流注册）；② `config/profiles/c0_sensorium.profile.yaml` v1.0 成稿（全数值溯源裁决 + 结构验证；typed loader 随实现期）；③ **正式评价入口 control/entry.py**（REV-0010 R5 收敛：m1|carryover|root 子命令；SC3 全量 n=64 复现精确恒等 + carryover 全管线复现；run_wording_cells 规范化 Q-L13-12④——SC4 派生格式成文钉死 + **χ² 种子格式敏感性方法学发现如实记录**（cell 带与极差恒同、p 0.033–0.379 浮动；C1 起统计计划必须内嵌种子派生冻结））；④ L02 v1.0.1 + L13 v1.0.3。**REV-0011 = PASS-WITH-FINDINGS（R1–R7 全闭环）→ C0 门已冻结**（2026-10-03，ADR-G-0011 + tag `c0-freeze`；R1(S1) = 注记层失实更正——runs.py/L13 "冒号格式经 8 cell 计数精确复现钉死"宣称被 REV 实证推翻（7/8 cell 不符、1 cell 巧合命中），更正为"入口规范化钉死的规范派生格式、非历史复现"，裁决本体 Q-L13-12④ 经核诚实；R2 entry 防覆盖守卫 ArtifactOverwriteRejected 即修 + evidence/ git 归档机制跟踪；R3/R4/R6 L02 §4.3/§4.4/§2.1 + Q-G00-12 措辞即修；R5 entry 工件补 I1 复算字段；R7 约束核对/保护集 C0 增补/白名单复核 → 实现期首单元）。REV-0011 独立复跑：334 passed / 0 错误 / check_docs 0 FAIL / 登记册 71/72/1 实点；本提交复跑 335 passed。验证基线：**335 passed、strict 四平面 0 错误、check_docs 0 FAIL、config 18 份**。**当前 = C0 实现期**：首单元 = R7 义务（资源/安全/伦理约束深化核对 + protection_suite C0 增补只增不减 + Q-L09-06/-L10-09 containment 白名单复核）→ `galatea/subject/sensorium/` 十二件（L02 §10：ports/ingest/alignment/form_extero/form_intero/form_proprio/calibration/quality/gain/pred_error/receipt/unknowns）+ 测试八件 + c0 profile typed loader（INC-11 纪律）+ 旁路保护权限测试 + bit-exact 重放 → REV-0012 → c0-exit（L02 §1 成功判据：≥2 外感受 + ≥1 内感受五元属性/FormationReceipt 可审计/旁路权限测试拒/bit-exact）。顺延终止条款持续有效。
- **版本管理**：已 git 化（2026-09-17 ACT-01，main 分支；提交纪律见下）。
- **2026-09-18 子项目剥离**：原 `physio/`（Zephyr 固件子项目）已整体剥离为独立项目，与本仓库不再有任何开发耦合；其全部研究资料保存在 git tag `physio-handoff`。Galatea 的 PhysIO 仍为 P1 物理接口层的**概念合同名**（HLD 附录 A.10），未来实现载体另行裁决。

## 会话开始必做

1. 通读本文件；
2. 读 `DEV_SPEC.md` §0（效力域）、§4.6（裁决权模型 v2）与 §9（军规十条）；
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
_audit/              ← check_docs.py（文档机器校验，文档变更后必运行）+ report.md + incidents.md（缺陷台账）
                       reviews/（REV-<dddd> 阶段独立评审报告，Q-DEV-05）
galatea/             ← 主线实现（kernel/evidence/subject/env 四平面；按各 LLD §10 清单 + 门节奏生成）
config/profiles/     ← frozen profile（F0 3 份：f0_l00 / f0_action_contract / f0_language_contract；
                        M0 3 份：m0_mw0 v1.1 / m0_gateway / m0_interventions；M1 1 份：m1_goals_min v1.1）
config/evidence/      ← 证据合同（F0 冻结 4 份：claim_v1 模板 / min_effects v1.1 / sealed_split_policy / decision_path_matrix）
（physio/ 已于 2026-09-18 剥离；历史资料见 git tag physio-handoff）
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
