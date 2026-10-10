# L01 环境与声明通道：WorldTruth、Channel Adapter、干预注册、最小世界 MW0

> LLD: L01/14 · v1.0.3 · 2026-10-02（v1.0.3：§10 补录 test_m2_sc6.py，REV-0009 R6）· v1.0.2 2026-09-26 · 状态：WORKING（M0 已退出 · M1/M2 场景层已落地）· v1.0.1（2026-09-26）：§10 测试清单补录 test_m1_sc3_sc4.py（MW0-SC3/SC4 实验台，L08 §9 M1 行/L13 冻结统计计划挂点）；头部状态栏勘误（REV-0007 R7："M0 冻结前"残留）· v1.0.2（2026-09-26）：§10 测试清单补录 test_m2_sc5.py（MW0-SC5 四臂连续性对照，m2_continuity.profile sc5 节挂点）
> 上游：`HLD.md` §3.2/§3.5/§4/§10.2 · 下游消费者：L02（Sensorium 唯一合法输入源）
> 引入门槛：**F0**（schema 合同）→ **M0**（可审计因果通道 + 非平凡动作效应）→ **M2**（MW0 切片支撑连续性实验）
> 本档承载阶段 0 蓝图（16×16 资源 niche）**门体系化后的实例 MW0**；旧蓝图切片 S1–S6 与验收 D1–D7 已重映射（§4.6；Q-L01-06 已裁决采纳重建映射，AI-v2 2026-09-23，见 open_questions A 区）。

## 1. 目标与范围

**目标**：提供 (a) 确定性、可干预、可复算的实验环境；(b) WorldTruth→ReceivedSignal 的**唯一合法声明通道**；(c) 干预注册与外部记录；(d) M0–M2/R0 阶段的最小世界 MW0。

**范围内**：Environment（世界动力学、真值、效果事实）、Channel Adapter（外感受/内感受/本体感受/语言/结果五类声明通道）、Intervention Registry（no-op/sham/blocked/fault/coercion 电池）、MW0 世界定义与 profile。

**范围外**：感觉形成（L02）、任何主体侧语义、evaluator 统计（L13）、物理 PhysIO（L10 + P1 专属）。

**成功判据（对应 M0 退出纪律）**：W/O、A/Ä、Y/Ŷ 三类对象隔离经权限测试；动作效应非平凡且可归因；无 oracle 泄漏（LeakageProbe）；evaluator 不读主体日志；环境确定性重放 bit-exact。

## 2. Ports（输入输出契约）

### 2.1 PortOut（环境侧发布，注意 access_scope）

| 端口 | 数据 | access_scope | 可见方 |
|---|---|---|---|
| `world.truth_stream` | `WorldTruthEvent(world_state_ref, effective_time, causal_parent)` | EVIDENCE_ONLY | Recorder（L13）；**主体平面不可见** |
| `world.effect_facts` | `EffectFact(action_window, requested_effect, effective_effect, domain=simulated)` | EVIDENCE_ONLY | Recorder、Evaluator |
| `channel.received` | `ReceivedSignalPacket`（representation_level=RECEIVED，L00 envelope） | MODULE_LOCAL→Sensorium | 仅 L02 |
| `channel.delivery_facts` | `ChannelDeliveryFact(sent_truth_ref, delivered, delay, corruption, channel_version)` | EVIDENCE_ONLY | Recorder/Evaluator（**仅实验室可见**） |
| `outcome.received` | `ReceivedOutcomePacket`（世界后果经通道回到主体，RECEIVED） | MODULE_LOCAL→L02 | 仅 L02 |
| `intervention.log` | `InterventionRecord(kind, target, params, registered_by, protocol_ref)` | EVIDENCE_ONLY | Recorder |

### 2.2 PortIn（接受）

| 端口 | 调用方 | 数据 | 纪律 |
|---|---|---|---|
| `world.step(profile_cycle)` | L00 调度环 | 推进世界一个虚拟周期 | 确定性：RNG 只来自 L00 流 |
| `world.apply(SubmittedCommand)` | Capability Gateway（L10） | 已授权命令 | **只接受 gateway 签名**；未授权写入 = S1 缺陷 |
| `channel.configure(channel_profile_ref)` | Experiment Control | 版本化通道参数（噪声/延迟/丢失/增益上界） | 参数冻结于 claim profile |
| `intervention.register(spec)` | Experiment Control | 干预规格 | 干预先注册后生效（干预外记） |

**五类声明通道**（通道外无边界）：Exteroceptive（MW0 局部观测渲染）、Interoceptive（能量/完整性/负载→形成前的原始内感受事件）、Proprioceptive（位置/姿态/能力观测）、Outcome（动作世界后果）、Language（L12 typed 陈述入口，EXTERNAL_STATEMENT）。

## 3. 状态所有权与单写者

| 状态 | 唯一写入者 | 读者 | 边界 |
|---|---|---|---|
| WorldTruth（含 MW0 网格/资源/身体真值） | Environment 进程内模块 | Recorder（只读导出） | EVIDENCE_ONLY 命名空间；主体平面 import 即 CI 失败 |
| ChannelDeliveryFact | Channel Adapter | Recorder/Evaluator | 仅实验室可见（HLD §3.5） |
| ReceivedSignal（RECEIVED 包） | 边界接收端（Adapter 出口） | L02 Sensorium 只读 | 不可改写；无修正语义，只有 revision 事件 |
| InterventionRecord | Intervention Registry | Recorder | 注册先于生效 |
| MW0 profile/dynamics 表 | registry（经 L00） | Environment 只读加载 | digest 引用；运行期禁改 |

**禁止**：Environment 写主体状态；Channel Adapter 写 PerceptualBelief（通道终点是 RECEIVED 包）；任何主体模块 import `galatea.env.truth` 命名空间（import-linter 强制）。

## 4. 算法与数据结构

### 4.1 WorldTruth 与效果模型

```text
WorldTruthEvent(tick, world_state_digest, state_ref: ArtifactRef(WorldState), causal_parents)
WorldState(MW0): grid[16×16] of Patch(kind, resource_level, respawn_timer),
                 body: BodyTruth(pos, orientation, energy, integrity, load),
                 events: list[WorldEvent(kind, pos, tick)]   # 资源涌现/风暴/威胁等
EffectFact: domain=simulated（MW0 期）；requested vs effective 分离——blocked/fault 干预在此显形
```

世界推进：`step()` 按 frozen dynamics 表（资源再生、事件生成，RNG 流 `("env","mw0","dynamics")`）；效果结算 `apply()` 将 gateway 命令映射为 `EffectFact`，**requested 与 effective 分别记录**（coercion/blocked 时二者不等，归属系统 L10 依赖此分离）。

### 4.2 Channel Adapter（渲染 + 传输语义）

每通道 = `render(WorldTruth 子集) → transport(delay/loss/corruption, 参数版本化) → ReceivedSignalPacket`。纪律：

- **DeliveryFact 与 Signal 分离**：投递事实（发了什么、何时、是否损坏）只入证据侧；主体只拿到 RECEIVED 包——兑现"投递≠接收"。
- 缺失/损坏不静默补零：产生 `MissingSignalEvent(typed unknown=MISSING_SIGNAL)` 随包 provenance 下发，由 L02 决定形成策略。
- 通道参数（观测窗、噪声 σ、延迟分布、增益上界）冻结于 claim profile；运行期修改 = 新 channel_version + 新 profile。
- 外感受渲染：以 BodyTruth 为中心的 egocentric 观测窗（Q-L01-01 CONFIRMED 2026-09-25：5×5、Chebyshev 距离增益 g(d)=1−0.4d，初值 M0 复核），按距离衰减 + 噪声；**不含**真值坐标/资源精确量（防 oracle 泄漏）。

### 4.3 干预电池（M0 必备五类，先注册后生效）

| 干预 | 机制 | 证明对象 |
|---|---|---|
| no-op | 命令被环境忽略，回执仍送达 | 回执≠效果；归属不盲信回执 |
| sham | 命令效果被替换为伪效果 | 主体依赖形成后结果而非意图 |
| blocked | gateway 拒绝，ExecutionFact=拒绝 | 意图≠执行；拒绝类型化 |
| fault | 通道/世界故障注入 | 失败类型化；无自动改写为"主体选择" |
| coercion | 效果发生但 effective≠requested 且标记外因 | 归属区分自产/强迫，可保持 unknown |

### 4.4 MW0：16×16 资源 niche 最小世界（阶段 0 蓝图 → 门体系实例）

- **几何**：16×16 网格，环形边界（torus，Q-L01-02 CONFIRMED 2026-09-25）；Patch 类型：资源丛（多级储量+再生）、中立、风暴带、遮蔽点。
- **身体**：单主体（D-14）；状态 = pos/orientation/energy/integrity/load；energy 随行动消耗、进食恢复；integrity 受风暴损伤；load 影响观测噪声（内感受源之一）。
- **动作原语**（低维、可枚举，M0 期）：move(4 向) / forage / eat / rest / look（主动感知，L09 可提案）。
- **内感受原始事件**（→ 经 Interoceptive 通道形成 InteroceptiveSensation，**不是** telemetry 直填）：energy 变化率、integrity 损伤事件、load/过载、恢复事件。
- **三种资源 regime（对应蓝图"3 情感模式"的 MW0 投影，参数实例化在 L05 profile）**：`abundance`（资源充足）/ `scarcity`（稀缺竞争再生慢）/ `volatile`（风暴带扩张收缩）。regime 切换由 Experiment Control 注册为干预，主体只能经通道感知（三 regime 框架 Q-L01-03 CONFIRMED 2026-09-25，与 Q-L05-04 成组；数值入 m0_mw0.profile）。
- **表格化动力学**：MW0 期世界转移与 respawn 全部为**表格/枚举**（呼应阶段 0"表格贝叶斯"），保证 M0 重放与干预分析可手算复核；神经模型仅存在于主体侧 C1+。

### 4.5 时间语义

世界 tick = L00 cycle；通道延迟以 cycle 表达并记入 DeliveryFact；`effective_time`（世界时）与 `delivered_time`（接收时）严格分离。

### 4.6 蓝图切片与验收的重映射（旧 S1–S6 / D1–D7 → MW0 切片 → 门）

| MW0 切片 | 内容 | 承接旧蓝图 | 服务门 |
|---|---|---|---|
| MW0-SC1 | 通道分离与投递事实（W/O 隔离） | 切片 1-2 | M0 |
| MW0-SC2 | 动作效应 + 五类干预电池（A/Ä、Y/Ŷ 隔离、非平凡效应） | 切片 2-3 | M0 |
| MW0-SC3 | 请求/机会→目标采纳实验台（真实理由 vs 伪理由） | 切片 3-4 | M1 |
| MW0-SC4 | 来源线索与归属交叉操纵 | 切片 4-5 | M1 |
| MW0-SC5 | 连续性：checkpoint 谱系/冻结/重置/伪更新对照 | 切片 5 | M2 |
| MW0-SC6 | sealed held-out + protection 场景（分布偏移/恢复） | 切片 6 | M2/R0 |

**裁决（Q-L01-06，AI-v2 2026-09-23）**：旧 D1–D7 原文判定**永久不可得**；上表重建映射**采纳为规范文本**，验收约束力由门退出判据承载（§9 + L13 `EvidenceResult`），本表降为溯源记录（不再单列验收义务）。重开条件：原文若现身，一 session 内复审。

## 5. 时间尺度与调度挂点

- T1 挂点：每 cycle `world.step()` + 通道渲染投递（接收/形成同拍，L02 消费）。
- T0 挂点：MW0 期无主体 T0 反射（门前不主张反射自主）；containment 由 gateway/实验控制承担。
- 干预生效点：注册后于指定 cycle 边界原子生效，记入 InterventionRecord。
- regime 切换：最小驻留 N6=256 cycles（Q-L01-04 CONFIRMED 2026-09-25；保证 M0 效应窗口 ≥4 个 T6 拍）。

## 6. 失败模式与 typed unknown

| 失败 | 类型化 | 行为 |
|---|---|---|
| 通道损坏/延迟超界 | `ChannelFault(channel_version, kind)` + MissingSignalEvent | 下发 typed unknown（MISSING_SIGNAL）；不补零不静默 |
| 未授权 apply() | `UnauthorizedCommand(cause)` | 拒绝 + S1 缺陷记录；fail closed |
| 世界状态 digest 与 profile 不符 | `WorldStateViolation` | 停止 claim-relevant 运行 |
| RNG 流污染（env 使用非派生流） | CI/lint + 运行时钩子拒绝 | 构建失败 |
| oracle 泄漏检出（主体输入含真值衍生量） | `LeakageDetected(probe_id)` | S0：立即停止 + 废止证据 |

环境侧不确定性（如事件生成时刻）对主体是 unknown，但**对 recorder 是全量事实**——两者永不混写。

## 7. 可测性

| 层 | 测试 | 断言 |
|---|---|---|
| unit | dynamics 表推进、渲染衰减、延迟/损坏采样 | 确定性（同 stream 同输出） |
| contract | 五通道 schema、DeliveryFact/Signal 分离、gateway 签名校验 | schema 强制 |
| invariant | WorldTruth 命名空间对主体平面不可 import；RECEIVED 包 provenance 完备 | 边界不可穿透 |
| deterministic replay | 同 (profile, seed) 世界轨迹 tick 级 bit-exact | M0 核心退出条件 |
| leakage（LeakageProbe 环境侧） | 主体可见信号与隐藏真值的未声明相关性检测（互信息抽样 + 对抗 probe） | 无 oracle 泄漏 |
| integration | 五类干预全电池端到端：注册→生效→效果事实→回执→归属输入分离 | M0/M1 场景 |
| protection suite | MW0 回归场景（每门冻结）在后续门不退化 | E1 回归 |

**指标**：重放 bit-exact 率=100%；泄漏 probe 检出=0；干预覆盖率（五类×全动作原语）=100%；no-op/sham 判别力（主体归属正确率 vs 随机基线，冻结最小效应 → Q-L01-05）。

**消融/对照**：关闭 DeliveryFact 分离 → 泄漏 probe 应报警；用真值坐标渲染 → 应被检出。

## 8. 不变量与禁止写入路径

**专属不变量**：
1. 主体可见 ⊆ 五类声明通道输出（无第六类边界）；
2. requested ≠ effective 必须显形于 EffectFact（禁合并）；
3. 环境确定性：无墙钟、无非派生 RNG、无容器序依赖；
4. regime/干预先注册后生效，注册记录不可变。

**禁止写入路径（本档强制）**：`environment/channel → PerceptualBelief`｜`WorldTruth → 主体可见命名空间`｜`recorder truth → belief（绕过声明通道）`｜`evaluator label → subject attribution`（本档不产生主体归属输入，只提供回执与形成后结果）｜`未注册干预 → 世界状态`。

## 9. 引入门槛

- **F0**：五通道 schema 与 WorldTruth/DeliveryFact/ReceivedSignal/EffectFact 对象图、typed unknown 对接以本档 §2/§4 规范文本 + L00 `schema_versions`（`f0_l00.profile.yaml`）承载，无独立 config 文件（REV-0002 R2 澄清，2026-09-23）；MW0 profile 骨架归 M0（`m0_mw0.profile.yaml`）。
- **M0**：MW0-SC1/SC2 全量实现；五类干预电池；确定性重放与 LeakageProbe 通过——**M0 失败的运行不启动 M1 主评价**。
- **M1**：MW0-SC3/SC4 实验台（请求/伪理由/来源线索操纵）。
- **M2/R0**：MW0-SC5/SC6（checkpoint 对照场景、sealed held-out 世界分布偏移）。
- **C0+**：MW0 保留为回归保护集；新感觉模态/更丰富虚拟具身由 C0 profile 扩展通道实现，仍走本档 Adapter 合同。

## 10. 实现清单（文件级）

```text
galatea/env/                       # EVIDENCE_ONLY 平面；主体平面禁止 import
  world/
    truth.py        WorldTruthEvent, WorldState, EffectFact
    dynamics.py     表格 transfer/respawn/事件生成（L00 RNG 流）
    mw0.py          MW0 几何/patch/body/动作原语/regime 机
  channels/
    adapter.py      ChannelBus 总线（render→transport→RECEIVED 包 + DeliveryFact 分离；M0 实现形态，2026-09-26 回写 REV-0005 R10）
    extero.py intero.py proprio.py outcome.py language_stub.py
    delivery.py     ChannelDeliveryFact, MissingSignalEvent
  interventions/
    registry.py     InterventionRecord, 五类干预实现
  profile.py        MW0/channel profile 加载与 digest 校验
tests/env/
  test_determinism.py test_leakage_env.py test_intervention_battery.py
  test_m1_sc3_sc4.py                # M1：MW0-SC3/SC4 实验台（v1.0.1 补录）
  test_m2_sc5.py                    # M2：MW0-SC5 四臂连续性对照（v1.0.2 补录）
  test_m2_sc6.py                    # M2：MW0-SC6 sealed/ITT bench（v1.0.3 补录，REV-0009 R6）
  test_gateway_signature.py test_channel_fault_typing.py
  # 注：test_gateway_signature.py 实际归属 galatea/subject/action/tests/（L10 §10 清单名；位置勘误 2026-09-26 REV-0005 R10）
config/profiles/
  m0_mw0.profile.yaml    MW0 全参数 + 通道参数 + regime 默认（冻结前 UNCONFIRMED）
  m0_interventions.yaml  干预电池规格
design/mw0/
  MW0_SPEC.md            （可选）MW0 场景图示与手算复核样例
```

## 11. 未决问题（→ open_questions.md）

| Q 号 | 问题 | 依赖 | 状态 |
|---|---|---|---|
| Q-L01-01 | egocentric 观测窗大小（默认 5×5）与距离衰减函数 | M0 profile 冻结 | CONFIRMED（AI-v2 2026-09-25：5×5 + g(d)=1−0.4d，见 A 区） |
| Q-L01-02 | MW0 边界：torus vs 墙（影响空间学习生态效度） | M0 | CONFIRMED（AI-v2 2026-09-25：torus） |
| Q-L01-03 | 三 regime 的参数化（再生率/风暴频率/资源密度）及其与 L05 情感模式的对应 | M0 + L05 | CONFIRMED（AI-v2 2026-09-25：框架采纳，数值入 m0_mw0.profile） |
| Q-L01-04 | regime 最小驻留 N6（默认 256 cycles） | M0 统计功效 | CONFIRMED（AI-v2 2026-09-25：256 cycles） |
| Q-L01-05 | no-op/sham 归属判别的冻结最小效应量与样本量 | M0 统计计划（L13） | CONFIRMED（AI-v2 2026-09-23，随 Q-L13-09：d≥0.5、n≥64/组） |
| Q-L01-06 | 旧 D1–D7 验收原文不可得：§4.6 重映射裁决 | F0 | CONFIRMED（AI-v2 2026-09-23：采纳重建映射为规范，见 §4.6 裁决注） |
| Q-L01-07 | M1 期 MW0 是否引入第二个可控代理（伪社会线索）或留到 C4 | M1 场景设计 | CONFIRMED（AI-v2 2026-10-07，裁决见 open_questions.md A 区） |
| Q-L01-08 | energy/integrity 的 viability 阈值与"损伤事件"定义（联动 L05 驱力） | M0/L05 | CONFIRMED（AI-v2 2026-09-25，M0 部分：损伤事件定义 + 力学初值；viability 阈值归 L05/C2，见 A 区） |
| Q-L01-09 | MW0 动力学表补充参数与边界语义（风暴率语义/觅食链/floor/load 简化/loss） | M0 | CONFIRMED（AI-v2 2026-09-25：REV-0004 R2–R4/R6 补裁，见 A 区） |
| Q-L01-10 | 物理通道映射与载体复用（P1；传感必经 Bridge→Channel Adapter→ReceivedSignal） | P1 | CONFIRMED（AI-v2 2026-10-10：载体复用 + `physio.host_telemetry.v1` schema；零新阈值维持 Q-L02-05；DeliveryFact/时间语义沿用；通道注册入 p1 profile，见 A 区） |
