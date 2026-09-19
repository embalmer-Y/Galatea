# PhysIO 需求清单（RESEARCH_03）

> 版本：v0.1 · 2026-09-18 · 状态：**DRAFT——待 owner review**（本清单是架构改动前的需求基线快照）
> 设立动因（前因后果）：owner 即将对 PIO 架构提出改动（2026-09-18），改动前需要一份**完整、可逐条圈改**的需求清单作为对照基线；此前需求散落在 README/RESEARCH_01/02/appendixA/ADR/已裁决 Q 号中，无法整体 review。
> 条目编号 `REQ-PIO-<nn>`（登记于根 DEV_SPEC.md §11.3）。每条含：需求（是什么）、前因后果（为什么存在/为什么这样定）、来源与状态。
> 状态标记：**[已裁决]** owner 已裁（Q 号）；**[合同]** Galatea L10 §4.6 对固件端的强制约束；**[候选]** 调研结论/抢救合同，未经 owner 裁决；**[待裁]** 悬而未决。
> ⚠️ 本清单不引入任何新决定；owner review 后的改动与重新汇总的待裁项将产生 v0.2。

---

## A. 身份与总体架构（6 条）

| ID | 需求 | 前因后果 | 来源/状态 |
|---|---|---|---|
| REQ-PIO-001 | 双重身份：① Galatea P1 物理具身的固件端；② 独立可复用的 Zephyr MCU 末端 I/O 框架 | 前因：owner 要求 PhysIO 能复用于其他机器人/系统项目，同时 Galatea P1 需要固件端。后果：架构必须"框架核心无 Galatea 概念"，对接逻辑收敛到薄层 | physio/README 定位；ADR-PIO-0001 [候选→已被 owner 认可方向] |
| REQ-PIO-002 | 核心原则四条：**非学习、确定性、版本化、fail-safe**——固件只做驱动/校准/滤波/有界控制图/局部保护，不产生语义、不做决策 | 前因：Galatea L10 §4.6 合同规定物理层不得具备学习能力或自行决策（防"硬件旁路主体"）。后果：所有功能设计以此为界 | Galatea `design/lld/L10` §4.6 [合同] |
| REQ-PIO-003 | `module/`（框架核心）**零 Galatea 依赖**：不 include/不链接任何 Galatea 类型或概念 | 前因：REQ-PIO-001 的机械保证手段。后果：Galatea 对接全部在 `app/galatea_node/` 薄层 + 宿主 Bridge，整体删除不影响框架 | ADR-PIO-0001 [候选] |
| REQ-PIO-004 | CI 必须能**单独构建 `module/`（不带 app）**且通过 | 前因：`module/` 零依赖只是声明，需要机械证据。后果：这是"可独立复用"的唯一可自动验证判据 | ADR-PIO-0001 [候选] |
| REQ-PIO-005 | 三大子系统 COM（通信）/IO（输入输出）/CORE（系统内核），子系统间**只经 zbus 通道 + 公开 C API** 交互，禁止直接函数私链 | 前因：可插拔与解耦要求——若子系统私链，替换/裁剪任一子系统会波及其他。后果：片内一切跨子系统数据流走 zbus | RESEARCH_01 §2 [候选] |
| REQ-PIO-006 | 与宿主的**唯一边界 = COM 协议层**（宿主不直接触碰 IO/CORE） | 前因：单一协议边界使宿主工具、Bridge、测试都面对同一合同，防止旁路。后果：所有宿主侧能力（发现/订阅/命令/OTA）都经协议表达 | RESEARCH_01 §2 [候选] |

## B. 平台与版本（3 条）

| ID | 需求 | 前因后果 | 来源/状态 |
|---|---|---|---|
| REQ-PIO-007 | Zephyr 版本：**4.5 基线**（2026-10 发布后锁定），PIO-M0 bring-up 期间用 4.4.0 过渡；切换 = west.yml revision 一行 + `west update` + pristine 重建 | 前因：项目周期与 2027-04 LTS4 重叠，4.5 有更成熟 LLEXT/zbus；LTS3 缺新特性。后果：west.yml pin 4.4.0，4.5 发布后切换并复验 CI | Q-PIO-01 [已裁决 2026-09-18] |
| REQ-PIO-008 | 目标板集（暂定）：**ESP32-S3 / ESP32-P4 / STM32H7 / RP2350** + native_sim（CI 平台） | 前因：owner 指定（2026-09-18，考虑手头硬件与工具链经验）；四款架构均在 LLEXT 支持列表。后果：① 该板集无成熟 TF-M，设备安全走"烧录证书 + MCUboot 签名 + Crypto API"；② 板级网络能力差异是架构输入（见 REQ-PIO-014 注） | Q-PIO-02 [已裁决 2026-09-18，暂定] |
| REQ-PIO-009 | west 工作区在 Galatea 仓库**之外**初始化，Zephyr 树不进本仓库 | 前因：Zephyr 树数 GB，进库会淹没有效变更历史。后果：仓库只持有 manifest（physio/west.yml） | physio/west.yml [候选] |

## C. 通信 COM（10 条）——⚠️ 本组是架构改动的高概率区域

| ID | 需求 | 前因后果 | 来源/状态 |
|---|---|---|---|
| REQ-PIO-010 | V1 传输集：**UART + 网络传输（WiFi / 以太网 / BLE）**；USB 待定 | 前因：owner 裁决（2026-09-18），改变了调研默认"以太网→V2"。后果：网络进 V1 使 zenoh-pico 的优势链路（TCP/UDP）可用，直接支撑了 REQ-PIO-011 | Q-PIO-03 [已裁决 2026-09-18] |
| REQ-PIO-011 | 通信后端：**Zenoh**（MCU 端 zenoh-pico），V1 即引入 | 前因：owner 裁决（2026-09-18），否决了调研建议"自研帧"——网络传输进 V1 后 Zenoh 的发现/命名空间/订阅模型可直接满足"设备异构兼容"主判据。后果：COM 架构需按 Zenoh 重新设计（REQ-PIO-012），SP-1…12 验证项升格为 PIO-M0–M1 门禁 | Q-PIO-07b/07d [已裁决 2026-09-18] |
| REQ-PIO-012 | **COM 架构按 Zenoh 原生重设计**（ACT-06）：peer/client 拓扑、key expression 命名空间、自研语义层定位 | 前因：原设计围绕自研帧展开，选 Zenoh 后不能只是"换编码"，架构要重新推导。后果：产出新设计文档，完成后一次性改写 RESEARCH_01 §3.2 与后续 HLD COM 章 | Q-PIO-07a [已裁决 2026-09-18] |
| REQ-PIO-013 | payload 编码：**CBOR**（Zephyr 内置 tinycbor）+ `tools/schema/` 单一事实源生成 C 头与 Python(Pydantic) 模型 | 前因：防固件/宿主两侧 schema 漂移；CBOR 无第三方依赖、schema 演进友好。后果：schema 文件成为两端的唯一生成源 | Q-PIO-07c [已裁决 2026-09-18] |
| REQ-PIO-014 | 板集网络能力差异（架构输入，bring-up 核实）：ESP32-S3 原生 WiFi+BLE；ESP32-P4 无无线电（配 ESP32-C6 或用以太网 MAC+外挂 PHY）；STM32H7 有 EMAC 需外挂 PHY；RP2350 无原生网络（需外挂模块）；zenoh-pico 上游**无 USB-CDC 链路实现** | 前因：REQ-PIO-008 板集与 REQ-PIO-010 传输集叠加后的现实约束。后果：各板的数据面链路选择不同；USB 若保留大概率只做调试/DFU | Q-PIO-02/03 推论 [候选，随 REQ-PIO-012 重设计定稿] |
| REQ-PIO-015 | **命令-回执分离**：`CMD(command_id, idempotency_key, deadline, payload)` → 固件立即回 `ACK`（已接受/已拒绝+原因）→ 执行完另发 `RECEIPT(command_id, result, error_code?)`；宿主可三分"没收到 / 没执行完 / 执行失败" | 前因：源自 Galatea 认识链（意图≠执行≠回执）但独立成立——任何宿主都需要区分这三态，Zenoh 的重传层不提供应用层回执。后果：无论后端是谁，这条语义必须自研（放在 Zenoh 之上的应用语义层） | ADR-PIO-0002 抢救语义 / appendixA §A.2.1 [候选，随 REQ-PIO-012 定稿] |
| REQ-PIO-016 | 幂等与超时：`idempotency_key` 会话内去重；`deadline` 过期命令不执行 | 前因：网络重传/重复发布不可避免，执行侧必须幂等；过期执行有安全风险。后果：固件侧维护去重窗口 | 同上 [候选] |
| REQ-PIO-017 | 会话管理：握手协商（协议版本/设备清单摘要/能力集）；状态机 `IDLE→HANDSHAKING→ACTIVE→DEGRADED→LOST`；**断链→触发 fail-safe profile**；重连后由宿主重建订阅（固件不缓存跨会话订阅） | 前因：链路不可靠是常态；断链必须映射到确定的安全行为。后果：COM 会话层持有状态机并与 IO 保护联动 | appendixA §A.2.2 [候选]；注：Zenoh 有 lease/liveliness 但只报"链路活/死"，不覆盖 fail-safe 语义，需自持断链判定（Zenoh 默认 lease 10s×3，远慢于保护要求的 500ms） |
| REQ-PIO-018 | 管理面复用 **MCUmgr/SMP**：OTA 镜像上传/确认/回滚/重启/镜像查询/只读设备注册表查询（自定义 handler）；SMP shell 默认关闭、授权开启 | 前因：Zephyr 已有成熟管理协议，自研即违反负清单"不复刻已有能力"。后果：管理面与数据面分离，可走不同物理链路 | RESEARCH_01 §3.2 / appendixA §A.2.3 [候选] |
| REQ-PIO-019 | 时间戳：**设备单调 µs**（`k_uptime` 换算）+ 宿主"请求-应答时延补偿"对齐绝对时间；**无 RTC 依赖** | 前因：事件时序对 Galatea 归属/证据链是刚需；RTC 增加硬件依赖与不一致源。后果：所有 EVENT/TELEMETRY 携带单调时间戳，绝对时间只在宿主侧换算 | Q-PIO-06 [已裁决 2026-09-18] |

## D. IO 子系统（8 条）

| ID | 需求 | 前因后果 | 来源/状态 |
|---|---|---|---|
| REQ-PIO-020 | 设备注册表：Devicetree 静态设备 + 运行时动态注册**同表管理**；每设备一份能力描述符（type/class/version/量程/采样能力/**digest**） | 前因："可插拔"要求统一设备身份与能力声明，无论静态还是热插。后果：digest 是设备身份锚点，更换设备即换 digest | appendixA §A.3.1 [候选] |
| REQ-PIO-021 | 设备生命周期事件：`DEVICE_ADDED / REMOVED / FAULTED / REVALIDATED` 上 zbus + 上报宿主；设备更换 = 旧描述符失效 + 新描述符注册 | 前因：宿主（和 Galatea）必须知道设备拓扑变化——L10 合同要求"设备新增/更换/隔离/重新纳入"各有独立流程。后果：注册表是事件源 | appendixA §A.3.1 [候选] |
| REQ-PIO-022 | 热插拔 V1 边界：USB 设备（Zephyr USB host）+ GPIO 类即插即用 + I2C/SPI 总线探测（注册表指令触发扫描）；不做 surprise removal 全覆盖 | 前因：owner 裁决（2026-09-18）。后果：总线级意外拔出的芯片差异由驱动层消化，框架不承诺 | Q-PIO-04 [已裁决 2026-09-18] |
| REQ-PIO-023 | 输入通道三路归一：Zephyr Input 子系统（事件型：按键/编码器/触摸）+ Sensor API（读数型：IMU/温湿度…）+ RTIO（异步/DMA 批量）；统一封装 `physio_stream`（携带频率/时间戳/单位/量程元数据，含缓冲与背压） | 前因：三类输入设备的内核接口不同，宿主与调理链不应感知差异。后果：`physio_stream` 是输入侧唯一数据抽象 | RESEARCH_01 §3.3 / appendixA §A.3.2–3.3 [候选] |
| REQ-PIO-024 | 确定性信号调理链：原始读数 → 校准表（线性/分段/温度补偿，DYN-1 参数下发）→ 确定性滤波（滑动均值/中值/一阶低通；**定点优先，禁非确定浮点路径**）→ 单位/量程归一 → 上报。**硬合同：同一输入序列必得同一输出序列**（重放测试机械验证） | 前因：Galatea 认识链要求传感数据可复算（bit-exact 重放的前提在固件端就成立）；浮点非确定路径破坏可复算性。后果：调理链是 V1 验收判据载体 | appendixA §A.3.4 [候选] |
| REQ-PIO-025 | 输出通道：GPIO/PWM/DAC + 执行器模板驱动（舵机/步进/直流/继电器）；**每通道显式声明三安全态**（上电态/断链态/故障态） | 前因：输出作用于物理世界，任何状态下都必须有确定行为；三态是 fail-safe 的最小完备划分。后果：无三态声明的输出通道不予注册 | appendixA §A.3.5 [候选] |
| REQ-PIO-026 | **写入路径唯一**：一切输出写入必经 `protection` 校验（限幅/slew-rate 强制执行）后才落驱动；绕过 protection 的驱动写入 = 违规（可机械检查） | 前因：多路径写输出会产生"绕过保护的命令"，这是安全事故入口。后果：HLD 应写成不变量 + CI 检查件 | appendixA §A.3.5 [候选] |
| REQ-PIO-027 | 局部保护（L0 级）：软件限幅（每通道 min/max/slew-rate）+ 断链 fail-safe profile + 看门狗超时→全输出安全态；**保护动作先于一切上层逻辑**且产生强制 EVENT 上报 | 前因：固件是物理安全最后一道闸，不能依赖宿主在线或协议栈正常。后果：保护路径的优先级/独立性是架构级约束（联动 REQ-PIO-031 estop） | appendixA §A.3.6 [候选] |

## E. CORE 子系统（8 条）

| ID | 需求 | 前因后果 | 来源/状态 |
|---|---|---|---|
| REQ-PIO-028 | 初始化顺序固定：`storage → health → timebase → io.registry → io.protection → com.session → control_graph`；**任一步失败 → 全系统 fail-safe，不得半启动** | 前因：protection 必须先于 com.session 就绪，否则宿主可能在保护逻辑装载前下命令（顺序不是任意的）。后果：配一条单元测试断言"protection 未就绪时任何下行 CMD 一律被拒" | appendixA §A.1.1 [候选] |
| REQ-PIO-029 | 持久化键空间（Settings/NVS/ZMS）：`physio/cal/<device_digest>/…`（校准，版本化）、`physio/prot/…`（保护阈值）、`physio/dev/…`（运行时设备清单摘要） | 前因：键空间用 device_digest 而非设备名 → 设备更换后旧校准表天然失效，与 Galatea"设备更换带独立授权 + digest"同构 | appendixA §A.1.2 [候选] |
| REQ-PIO-030 | 健康监控：**每子系统独立 task watchdog channel**（可定位哪个子系统卡死）；panic → retention 环形黑匣子（最近 N 事件）→ 自恢复或等宿主复位 | 前因：单一看门狗无法区分故障源；黑匣子使现场故障可追溯。后果：三子系统各自喂狗是结构性要求 | appendixA §A.1.3 [候选] |
| REQ-PIO-031 | 急停（estop）：`estop_in`（硬件 GPIO 中断/比较器）→ **ISR 直接落安全态，不经协议层、不经调度排队、不经任何中间件会话栈** → 事后补发 `EmergencyStopExecuted` EVENT；**响应时间上界可测**（目标 `response_budget_us: 1000`，实测标定） | 前因：急停若经 zenoh session/调度排队，其时延受协议栈负载影响——Zenoh 的 batching mutex 官方注释明写"有丢连接风险"，安全路径附近必须禁用。后果：estop ISR 符号级不得调用 COM 任何 API（机械检查）；此条与 Galatea Q-L10-08 对接 | appendixA §A.3.7 / RESEARCH_02 SP-8 [候选，SP-8 为一票否决线] |
| REQ-PIO-032 | 动态编程三层：**DYN-1 配置动态**（Settings 参数：校准/增益/滤波/保护阈值，重启或热生效）；**DYN-2 图动态**（控制图，见 REQ-PIO-033）；**DYN-3 代码动态**（LLEXT 运行时装载 ELF 扩展）——**三层均进 V1** | 前因：owner 裁决 LLEXT 进 V1（2026-09-18，否决调研默认"延后 V2"）；四款目标板架构均支持 LLEXT。后果：DYN-3 的安全合同（下条）从 V1 起生效；RAM/flash 预算压力前移 | Q-PIO-05 [已裁决 2026-09-18] + appendixA §A.1 [候选] |
| REQ-PIO-033 | 控制图（DYN-2）四条不可放松合同：① 图文件**必须签名**，验签 + digest 比对不符 → **拒载**；② **算子集封闭枚举**、每算子参数范围显式声明并校验；③ 执行有**超时/预算**，越界 → 回退安全态 + 上报；④ **固件端绝不生成/修改图**（非学习） | 前因：控制图 = "不刷固件改变控制行为"，风险居中但必须有界；与 Galatea PhysIOControlGraph 合同（有界、digest 冻结、禁未签名加载）逐条对齐。后果：M4/图动态的验收即此四条 | appendixA §A.1.5 [候选]；算子集清单 [待裁 Q-PIO-09] |
| REQ-PIO-034 | DYN-3（LLEXT）安全合同：默认 Kconfig 开关状态 HLD 冻结时定（进 V1 后倾向可开）；**只接受通过签名校验的扩展**；**装载失败 → 拒绝并上报，不影响主镜像**（失败隔离）；装载流程 = 验签 → `llext_load` → 符号白名单绑定 → 运行时预算 | 前因：LLEXT 实验性且无 MPU 隔离时与主镜像同权，签名+隔离是最低安全线；"进 V1"的裁决不豁免此合同。后果：LLEXT 相关 CI 检查件从 V1 起存在 | appendixA §A.1.6 [候选]，叠加 Q-PIO-05 [已裁决] |
| REQ-PIO-035 | 引导与 OTA：MCUboot 签名镜像 A/B 双槽 + 防回滚计数；MCUmgr SMP 承载上传/确认/回滚/重启；镜像元数据含版本/digest/构建时间/兼容协议版本；升级失败自动回滚 | 前因：设备可插拔+可远程管理的前提是可安全更新；A/B 槽保证变砖可回退。后果：bootloader 预算（flash 双槽）计入板选约束 | RESEARCH_01 §3.1 [候选] |

## F. Galatea P1 对接合同（5 条，来自 L10 §4.6）

| ID | 需求 | 前因后果 | 来源/状态 |
|---|---|---|---|
| REQ-PIO-036 | 传感数据必经 `PhysIO Bridge → Channel Adapter(L01) → ReceivedSignal → Sensorium(L02)` 进入 Galatea，**不得因物理来源绕过形成层** | 前因：Galatea 认识链铁律（RECEIVED 是唯一合法输入层）；若物理传感直填身体信念 = 硬件旁路主体。后果：固件侧只产生"事件/流"，语义化全部在 Galatea 侧完成 | Galatea L10 §4.6 [合同] |
| REQ-PIO-037 | 执行必经 Galatea gateway 授权链（`SubmittedCommand` 签名校验），固件侧校验 gateway 签名；未签名命令到达 = 拒绝 + S1 级缺陷记录 | 前因：`intention ≠ execution`，物理执行是最高危动作。后果：固件命令入口 = gateway 签名验证（与 REQ-PIO-015 命令链衔接） | Galatea L10 §4.6 + L01 §2.2 [合同] |
| REQ-PIO-038 | 四类现实授权（functional_ability / enabled_interface / containment_allowance / deployment_authorization）在对接层以**只读配置**落地，固件与主体均不可写 | 前因：物理能力授权必须独立于被授权方（组织独立原则）。后果：授权记录存在独立配置/命名空间，gateway 只读校验 | Galatea L10 §4.6 [合同] |
| REQ-PIO-039 | Galatea 侧语义映射（ReceivedSignal 承载体、四类授权校验对接）只存在于 `app/galatea_node/` 与宿主 Bridge | 前因：REQ-PIO-003 零依赖要求的落点。后果：对接层可整体删除而不影响框架 | ADR-PIO-0001 [候选] |
| REQ-PIO-040 | PhysIO 永不旁路 Galatea 的 Sensorium / gateway / receipt / evidence 四环节 | 前因：这是 Galatea 的 S0 级红线（硬件旁路 = 立即停止）。后果：任何固件功能设计先对照此条 | Galatea L10 §9 [合同] |

## G. 负清单 V1（6 条）

| ID | 需求（不做什么） | 前因后果 | 来源/状态 |
|---|---|---|---|
| REQ-PIO-041 | 不做片上学习/自适应控制 | 前因：REQ-PIO-002 非学习原则的直接表达 | RESEARCH_01 §4.1 [候选] |
| REQ-PIO-042 | 对外中间件约束：原第 2 条（"不做通用机器人中间件"）**修订待裁**——07b=Zenoh 后 NL2-a（全面禁止）出局，剩 NL2-b（分层豁免+四机械检查件）/NL2-c（直接采用 Zenoh） | 前因：原条文谓词歧义且与 Zenoh 选择冲突。后果：变体裁决后本条定稿 | RESEARCH_01 §4.2 / RESEARCH_02 §7.3 [待裁] |
| REQ-PIO-043 | 不做文件系统级插件市场；代码动态仅限签名 LLEXT | 前因：插件市场 = 未签名代码入口，违反 REQ-PIO-034 | RESEARCH_01 §4.3 [候选] |
| REQ-PIO-044 | V1 不做多 MCU 组网路由（单 MCU 单宿主直连）；组网条款与第 2 条配套修订待裁 | 前因：原第 4 条与第 2 条暗中耦合，Zenoh 的卖点恰是组网——两条必须一起改 | RESEARCH_01 §4.4 [待裁] |
| REQ-PIO-045 | 不复刻 SMP/MCUmgr 已有能力（管理面直接复用） | 前因：避免重复造轮子与双协议并存 | RESEARCH_01 §4.5 [候选] |
| REQ-PIO-046 | 不做 GUI/仪表盘；宿主侧工具最小化为 CLI + Python SDK | 前因：与 Galatea 负清单"禁 dashboard 服务"精神一致；固件调试不依赖图形界面 | RESEARCH_01 §4.6 [候选] |

## H. 资源与安全基线（4 条）

| ID | 需求 | 前因后果 | 来源/状态 |
|---|---|---|---|
| REQ-PIO-047 | 资源治理：每子系统独立 workqueue/线程与栈预算；内存池**静态分配为主**（Kconfig 可调）；CPU 负载统计上报 | 前因：动态分配是碎片与不确定时延之源；分子系统预算使故障可定位。后果：与 zenoh-pico 的堆依赖（`k_malloc`、`z_realloc` 未实现）存在张力，SP-5/SP-9 实测定夺 | appendixA §A.1.7 [候选] |
| REQ-PIO-048 | 设备身份与签名：设备唯一身份（烧录证书；板集无 TF-M 路径）；**命令 / 控制图 / 镜像三重签名校验** | 前因：命令与图都能改变物理行为，必须与镜像同级信任。后果：Crypto API + MCUboot 已有能力承载 | RESEARCH_01 §3.1 + Q-PIO-02 注记 [候选] |
| REQ-PIO-049 | Zenoh 引入的附加验证门禁（SP-1…12，升格为 PIO-M0–M1 前置必做）：构建通过/双向通信/RAM≤目标 25%/ROM≤64KB/堆依赖量化/断链恢复≤500ms/**estop 独立性（SP-8 一票否决）**/单线程模式可行性/宿主部署形态/版本 pin 符号面≤30/特性裁剪 | 前因：07b+07d 把 Zenoh 提前进 V1，原先"V2 再验证"的 spike 变成门禁。后果：PIO-M0/M1 验收含 SP 项 | Q-PIO-07b/07d [已裁决] + RESEARCH_02 §6 [候选→门禁] |
| REQ-PIO-050 | Zenoh 版本锁定与供应链：pin zenoh-pico 具体 revision（west project 声明，不在 Zephyr 默认 manifest）；纳入 SBOM | 前因：zenoh-pico 快速演进（1.10.1，多份迁移指南），不锁版本则重放/复算不可保证 | RESEARCH_02 §3.2 [候选] |

## I. 里程碑（结构待重构，仅存目）

| ID | 需求 | 前因后果 | 来源/状态 |
|---|---|---|---|
| REQ-PIO-051 | 里程碑序列（**待重构**）：PIO-M0 bring-up → PIO-M1 COM → PIO-M2 IO 核心 → PIO-M3 保护与 OTA → PIO-M4 图动态 → PIO-M5 Galatea 对接 | 前因：原表按"自研帧 + LLEXT 在 V2"编排；07b（Zenoh）与 Q-PIO-05（LLEXT 进 V1）已使 M1/M4/V2+ 划分失效。后果：待架构改动与 07e/NL2/Q-PIO-11 裁决后统一重构（禁半改） | RESEARCH_01 §5 [待重构] |
| REQ-PIO-052 | PIO-M0 bring-up 验收：west 工作区 + `module/` 空壳在 native_sim 与 ≥1 真实板构建通过；shell/logging/zbus 骨架；CI 双平台绿 | 前因：一切后续工作的地基。后果：当前无法执行（实现产物已撤回，属预期状态） | RESEARCH_01 §5 [待重构] |
| REQ-PIO-053 | 宿主侧 Python SDK 位置与 Galatea Bridge 分离（候选 `physio/host/`） | 前因：SDK 属固件域工具，Bridge 属 Galatea 主体域，两者负清单适用域不同（Q-PIO-11 待裁）。后果：目录归属随 Q-PIO-10/11 裁决定 | Q-PIO-10 [待裁] |
| REQ-PIO-054 | 许可证与仓库形态：候选 Apache-2.0；in-tree，首次外部复用前拆独立仓库 | 前因：Apache-2.0 与 zenoh（EPL-2.0/Apache-2.0 双许可）等未来依赖兼容；早拆仓 = 双仓维护成本 | Q-PIO-08 [待裁] |

---

## 当前悬而未决项快照（架构改动后将重新汇总呈递）

按 DEV_SPEC §4.4 新格式（含背景列）重述并呈递，当前仅存目防遗失：
**physio 域**：Q-PIO-07e（宿主常驻进程/peer vs router——已详释待裁）、Q-PIO-08/09/10/11/12、ADR-PIO-0002 处置确认（建议 SUPERSEDED）、NL2 变体 + 第 4 条配套修订。
**主线域**（不属 PIO，不受本次架构改动影响）：F0 阻断 11 项 + Q-G00-03/05 + Q-DEV-01/02/03（B/C 档按门时冻结）。

## 修订记录

- 2026-09-18 v0.1：首版。从 physio/README、RESEARCH_01/02、appendixA、ADR-PIO-0001/0002、Galatea L10 §4.6、已裁决 Q 号（Q-PIO-01…06、07a–07d）汇编 54 条需求，分 9 组；每条含前因后果与状态标记（DEV_SPEC §8.7）。用途：owner review 基线 → 架构改动 → v0.2 修订 + 待裁项重汇总。
