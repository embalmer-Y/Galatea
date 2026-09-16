# RESEARCH_01 附录 A：从骨架 stub 抢救的合同措辞

> 版本：v0.1 · 2026-09-16 · 状态：**NON-NORMATIVE（研究输入）**
> 来源：2026-09-15 误在研究阶段写出的 `module/**` C stub、`module/Kconfig`、`module/CMakeLists.txt`、
> `module/zephyr/module.yml`、`app/galatea_node/*`。这些实现产物已按 owner 指示撤回
> （流程：research → HLD → LLD → 实施，不得跳步）。
> 本文档只做一件事：**把 stub 注释里已经想清楚的合同措辞保留下来**，作为 HLD / LLD 的输入素材。
> 其中每一条在冻结前都仍需 owner 裁决；本文档不构成任何决定。
>
> ⚠️ 与本文档相关的未裁决项：ADR-0001（独立 Zephyr module）、ADR-0002（线协议 = CBOR，**属过早决定，待降级为候选**）、
> Q-PIO-01…10、以及 §一.3 提出的 Q-PIO-07a–07e / Q-PIO-11 拆分（全部待 owner review）。

---

## A.0 抢救总览

| 来源文件（已删除） | 抢救出的内容 | 去向 |
|---|---|---|
| `module/src/core/core_init.c` | 初始化顺序合同 + 任一失败即 fail-safe | A.1 |
| `module/src/core/storage.c` | Settings 键空间规划 | A.1 |
| `module/src/core/health.c` | 每子系统一个 wdt channel + panic→retention 黑匣子 | A.1 |
| `module/src/core/timebase.c` | 单调 µs 时间基准（Q-PIO-06） | A.1 |
| `module/src/core/control_graph.c` | 控制图四条不可放松合同（M4/D2） | A.1 |
| `module/src/core/llext_loader.c` | LLEXT 仅签名、拒载不影响主镜像（V2/D3） | A.1 |
| `module/src/com/protocol.c` | 帧结构 + 消息类清单 + 命令-回执分离 | A.2（**待 Q-PIO-07b 裁决后才能成立**） |
| `module/src/com/session.c` | 会话状态机 + 断链 fail-safe + 幂等去重 | A.2 |
| `module/src/com/mgmt_smp.c` | 管理面复用 SMP、默认关闭授权开启 | A.2 |
| `module/src/io/registry.c` | 单一注册表 + 能力描述符 + 生命周期事件 | A.3 |
| `module/src/io/input_channel.c` | 输入数据路径 | A.3 |
| `module/src/io/conditioning.c` | 确定性调理链 + 回放一致性硬合同 | A.3 |
| `module/src/io/stream.c` | `physio_stream` 统一抽象 | A.3 |
| `module/src/io/output_channel.c` | 三安全态声明 + 唯一写入路径 | A.3 |
| `module/src/io/protection.c` | 局部保护先于一切上层逻辑 + 强制 EVENT | A.3 |
| `module/src/io/estop.c` | ISR 直达安全态、绕开协议与调度、事后补发事件 | A.3（**与 Galatea Q-L10-08 对接**） |
| `module/Kconfig` | Kconfig 树形状 + `PHYSIO_COM_PROTOCOL_VERSION` choice | A.4（**该 choice 是过早决定，必须拆除**） |

---

## A.1 CORE 子系统合同候选

### A.1.1 初始化顺序（M0 冻结候选）

```text
storage → health → timebase → io.registry → io.protection → com.session → (M4) control_graph
```

- **原则**：任何一步失败 → 系统进入 fail-safe（输出落安全态 + 上报），**不得半启动**。
- 抢救理由：这个顺序不是任意的——`protection` 必须在 `com.session` 之前就绪，否则宿主可能在保护逻辑装载前就能下命令；`io.registry` 在 `protection` 之前，因为保护阈值按设备挂接。
- 机械检查件（HLD 阶段落地）：一条单元测试断言"在 protection 未就绪时，任何下行 CMD 一律被拒并返回错误码"。

### A.1.2 持久化存储键空间（Settings/NVS/ZMS）

```text
physio/cal/<device_digest>/...   校准表（版本化）
physio/prot/...                  保护阈值
physio/dev/...                   运行时注册设备清单摘要
```

- 键空间用 `device_digest` 而非设备名 → 设备更换后旧校准表天然失效，与 Galatea"设备新增/更换/隔离/重新纳入各带独立授权 + digest"同构。
- M2 起承载校准参数与配置动态层（D1）。

### A.1.3 健康监控

- **每子系统一个 task watchdog channel**（而非全局一个）→ 可定位是哪个子系统卡死。
- panic → retention 环形记录最近 N 事件（黑匣子）→ 自恢复或等待宿主复位指令。
- M3 接入 panic 钩子与黑匣子回放。

### A.1.4 时间基准（Q-PIO-06 待裁决）

```c
uint64_t physio_timestamp_us(void);   /* = k_ticks_to_us_floor64(k_uptime_ticks()) */
```

- **约定**：全部时间戳为**设备单调 µs**；与宿主的绝对时间对齐由协议层"请求-应答时延补偿"完成；**固件不引入 RTC 依赖**。
- 这是撤回的 stub 中**唯一有实际实现的函数**，其余全是 `LOG_MODULE_DECLARE` + TODO。

### A.1.5 控制图执行器（M4；D2 图动态层）—— 四条不可放松合同

1. 图文件**必须携带签名**；加载前验签 + 计算 digest，与声明不符 → **拒载**；
2. **算子集封闭枚举**（Q-PIO-09），参数范围显式声明并校验；
3. 执行**有超时/预算**；执行中任一步越界 → **回退安全态 + 上报事件**；
4. **固件端绝不生成/修改图**（非学习）。

- 对齐 Galatea L10 §4.6：`PhysIOControlGraph` 必须有界、算子确定性、整图 digest 冻结、禁止未签名动态控制逻辑。

### A.1.6 LLEXT 动态代码装载（V2；D3；Q-PIO-05）

- 默认 Kconfig **关闭**；即便开启，**只接受通过签名校验的扩展**；
- **装载失败 → 拒绝并上报，不影响主镜像**（关键：失败隔离）。
- 预期流水线（V2）：验签 → `llext_load` → 符号白名单绑定 → 运行时沙箱预算。
- 上游约束：LLEXT 实验性，架构限 RISC-V/ARM/ARM64/ARC/x86/Xtensa；Zephyr 中路径已从 `kernel/llext` 移到 `services/llext`。

### A.1.7 资源治理

- 每子系统独立 workqueue/线程与栈预算；内存池**静态分配为主**（Kconfig 可调）；CPU 负载统计上报。
- ⚠️ **与 Zenoh 候选的冲突点**（若 Q-PIO-07b 选 Zenoh 必须重新裁决本条）：zenoh-pico 的 Zephyr 移植依赖
  POSIX pthreads（`CONFIG_POSIX_API`）+ NET_SOCKETS + POSIX select + 堆（`k_malloc`；且 `z_realloc` 未实现、直接返回 NULL）。

---

## A.2 COM 子系统合同候选

> ⚠️ **本节 A.2.1 的帧结构与消息类清单来自 ADR-0002，属研究阶段的过早决定。**
> 若 Q-PIO-07b 裁决为 Zenoh/MQTT-SN/CoAP 后端，A.2.1 整节作废，仅 A.2.2/A.2.3（L4 会话语义层）保留。
> 按分层模型：A.2.1 = L2/L3（Zenoh 会接管），A.2.2 = L4（任何后端下都是我们自己的），A.2.3 = 管理面。

### A.2.1 线协议 v1（L2/L3，**候选，非决定**）

- 帧：`magic(2B) | version(1B) | len(2B) | crc16 | CBOR payload`
- 消息类：`DISCOVER` `HELLO/CAP` `STREAM_SUB` `STREAM_UNSUB` `CMD` `ACK` `RECEIPT` `EVENT` `TELEMETRY` `ESTOP` `MGMT`
- **命令-回执分离**（借自 Galatea 但通用）：`CMD` → `ACK`（已接受）与 `RECEIPT`（已执行完/失败 + 错误码）**两条独立消息**；
  宿主据此可三分："没收到" / "没执行" / "执行失败"。
- `CMD` 携带 `command_id` + `idempotency_key` + `deadline`。
- **抢救理由**：即使最终换传输后端，"命令-回执分离 + 幂等键 + deadline"这三件事是**传输无关的应用语义**，
  在 Zenoh 下也必须由我们在 payload/queryable 里自己实现（Zenoh 的重传层不等于应用层回执）。

### A.2.2 会话管理（L4，任何后端下都成立）

- 握手协商：协议版本、设备清单摘要、能力集。
- 会话状态机：`IDLE → HANDSHAKING → ACTIVE → DEGRADED → LOST`。
- **链路断开 → 触发 `io.protection` 的 fail-safe profile**（输出进声明的安全态）。
- 重连 → 握手协商后**由宿主重建订阅**（固件不缓存跨会话订阅状态）。
- `CMD` 以 `idempotency_key` 去重。
- ⚠️ 若选 Zenoh：`Z_TRANSPORT_LEASE=10000ms`（×3 过期因子）与 `config/protection_profiles/default.yaml` 的
  `link_loss_after_ms: 500` 相差约 20 倍 → **断链检测必须自己做**，不能依赖 Zenoh 的 lease/liveliness。

### A.2.3 管理面

- 直接复用 **MCUmgr/SMP**：OTA 镜像上传/确认/回滚/重启/镜像查询。
- **SMP shell 默认关闭，授权开启**。
- OTA 走 **MCUboot A/B 槽签名镜像**。
- 设备注册表查询以**自定义 mcumgr handler 暴露（只读）**。
- 负清单第 5 条：不复刻 SMP/MCUmgr 已有能力。

### A.2.4 传输抽象

- V1：USB-CDC / UART（默认与调试）+ BLE（无线形态）；V2 候选：Ethernet/UDP、CAN（Q-PIO-03）。
- 传输可**多路并存**（管理面走一路、数据面走另一路）。
- ⚠️ zenoh-pico 在 Zephyr 下的实测缺口：`Z_FEATURE_LINK_SERIAL` 默认关闭且**只有波特率可配**
  （数据位/校验/停止位/流控在源码中被注释掉），MTU 固定 1500；**无 Zephyr USB-CDC 串口 link**
  （`LINK_SERIAL_USB` 只有 rpi_pico/tinyusb 实现）；Zephyr 下 BLE link 未见上游验证。
  → V1 三条链路（UART / USB-CDC / BLE）在 zenoh-pico 上**一条都没有被上游重点覆盖**。

---

## A.3 IO 子系统合同候选

### A.3.1 设备注册表（M2）

- **单一注册表**：Devicetree 静态设备 + 运行时动态注册（热插拔）**同表管理**。
- **能力描述符**：`type / class / version / range / sampling capabilities / digest`。
- 生命周期事件（**上 zbus + 上报宿主**）：`DEVICE_ADDED` / `DEVICE_REMOVED` / `DEVICE_FAULTED` / `DEVICE_REVALIDATED`。
- **设备更换 = 旧描述符失效 + 新描述符注册（digest 变化强制上报）**。

### A.3.2 输入通道（M2）

```text
设备驱动 → physio_stream → conditioning（校准/滤波）→ protection → 协议层 EVENT/订阅流上报
```

- 事件型设备接 **Zephyr Input 子系统**回调；读数型走 **Sensor API / RTIO 批量**。

### A.3.3 统一流抽象 `physio_stream`（M2）

- 输入侧统一封装，携带**频率 / 时间戳 / 单位 / 量程**元数据；
- 底层对接三路：Input 子系统（事件型）/ Sensor API（读数型）/ RTIO（批量）；
- 含缓冲与背压策略。

### A.3.4 确定性信号调理链（M2）

```text
原始读数 → 校准表（线性/分段/温度补偿，D1 参数下发）
         → 确定性滤波（滑动均值/中值/一阶低通；定点优先，禁非确定浮点路径）
         → 单位/量程归一
```

- **硬合同：同一输入序列必得同一输出序列**（重放测试机械验证）。
- 这是 M2 的验收判据，也是与 Galatea 认识链可复算性要求对齐的关键点。

### A.3.5 输出通道（M2）

- GPIO/PWM/DAC + 执行器模板驱动（舵机/步进/直流/继电器）。
- **每个输出通道显式声明三安全态**：上电态 / 断链态 / 故障态。
- **写入路径唯一**：`protection` 校验通过后才落到设备驱动（限幅 / slew-rate 强制执行）。
- 抢救理由：这条"唯一写入路径"是可机械检查的（任何绕过 protection 的驱动写入 = 违规），HLD 应把它写成不变量。

### A.3.6 局部保护（L0 层，M2/M3）

- 软件限幅（每输出通道 `min` / `max` / `slew-rate`）；
- 链路断开 fail-safe profile；看门狗超时 → 全输出安全态；
- **保护动作先于一切上层逻辑**，且产生**强制 EVENT 上报**。

### A.3.7 急停（M3）—— 最高优先级不变量

```text
estop_in（硬件 GPIO 中断/比较器）→ ISR 直接落安全态
                                  → 不经协议层、不经调度排队
                                  → 事后补发 EVENT（EmergencyStopExecuted）
```

- **硬合同：急停响应时间上界可测**（与 Galatea **Q-L10-08** 对接时对齐；`config/protection_profiles/default.yaml`
  里 `estop.response_budget_us: 1000` 是目标值，须在 M3 实测标定）。
- **本条是与传输后端选型无关的绝对不变量**：无论 Q-PIO-07b 选谁，**急停永不经过中间件会话栈 / 协议栈**。
  若选 Zenoh，此条应升格为 HLD 级不变量 + 机械检查件（estop ISR 函数不得调用 COM 任何 API，符号级检查）。
  ⚠️ 旁证：zenoh-pico 无硬实时优先级语义；`BATCH_TX_MUTEX`/`BATCH_PEER_MUTEX` 官方注释明写"有丢连接风险"
  → 安全路径附近禁用。

### A.3.8 热插拔 V1 支持边界（Q-PIO-04）

- V1 支持：① USB 设备（Zephyr USB host stack）② I2C/SPI 挂载设备探测（注册表指令触发扫描）③ GPIO 类即插即用；
- 不支持原生总线级 surprise removal 的芯片差异由驱动层消化。

---

## A.4 构建/Kconfig 形状（撤回，仅记录形态供 HLD 参考）

撤回的 `module/Kconfig` 树形状：

```text
menuconfig PHYSIO            depends on ZBUS && CBOR
├── PHYSIO_CORE_*            （storage / health / timebase / llext ...）
│   └── PHYSIO_CORE_LLEXT    default n      ← D3 默认关闭（Q-PIO-05）
├── PHYSIO_COM_*             （protocol / session / transport_* / mgmt_smp）
│   └── choice PHYSIO_COM_PROTOCOL_VERSION
│       └── default PHYSIO_COM_PROTOCOL_V1 "v1 (CBOR)"   ← ⚠️ 过早决定，必须拆除
└── PHYSIO_IO_*              （registry / stream / input / output / conditioning / protection / estop）
```

- **必须拆除项**：`choice PHYSIO_COM_PROTOCOL_VERSION`。一个 `choice` 意味着"多实现可选"，
  但 V1 只会存在一个实现；且在 Q-PIO-07b 尚未裁决前把 `"v1 (CBOR)"` 写成 default 是把研究结论固化进了构建系统。
  → 处置建议（待裁决）：删除该 choice，Kconfig 中不出现协议版本概念；协议版本只在**线格式的版本字段**里协商（运行时），不在编译期选。
- 撤回的 `module/CMakeLists.txt` 用 `zephyr_library()` + 19 行 `zephyr_library_sources_ifdef(...)`。
  → HLD 阶段若要恢复此形态，须先冻结模块清单；研究期不预建。
- 撤回的 `module/zephyr/module.yml` 内容为 Zephyr module 标准声明（`build: cmake: .` / `kconfig: Kconfig`）。
  → ADR-0001 的结论（PhysIO 作为 Zephyr module）**仍然成立且未变**，只是研究期不需要真的写出该文件。
  → 旁证（Zenoh 调研所得）：`eclipse-zenoh/zenoh-pico` 自身就带 `zephyr/module.yml`
  （`name: zenoh-pico` / `build: cmake: zephyr/` / `kconfig: zephyr/Kconfig.zenoh`），说明"第三方库以 Zephyr module 形式引入"是成熟路径；
  但它**不在 Zephyr 官方 default manifest**，故若引入须由 PhysIO 自己的 `west.yml` 声明为 west project 并 pin revision。

---

## A.5 撤回操作记录（可追溯）

- 时间：2026-09-16。指示：*"先撤回 C 产物，其他的裁决项我需要再 review 一下"*。
- 已删除（27 个文件）：
  - `module/src/core/{core_init,storage,control_graph,health,timebase,llext_loader}.c`（6）
  - `module/src/com/{protocol,session,transport_uart,transport_usbcdc,transport_ble,mgmt_smp}.c`（6）
  - `module/src/io/{registry,stream,input_channel,conditioning,output_channel,protection,estop}.c`（7）
  - `module/include/physio/physio.h`、`module/include/physio/{com/protocol.h,core/core.h,io/registry.h}`（4）
  - `module/CMakeLists.txt`、`module/Kconfig`、`module/zephyr/module.yml`（3）
  - `app/galatea_node/{CMakeLists.txt,prj.conf,src/main.c}`（3）
- 保留：目录骨架（以 `.gitkeep` 占位）、`config/**`、`docs/**`、`tests/README.md`、`tools/README.md`、`west.yml`、`README.md`（三者内容已改为研究期措辞）。
- **未触碰（等 owner review）**：`docs/adr/ADR-0001*`、`docs/adr/ADR-0002*`、`docs/RESEARCH_01_scope.md` §3.2/§4/§6。
- 后果：当前仓库**无任何可构建目标**；`west build` 路径失效属预期。

## A.6 恢复路径

HLD 冻结后，按 LLD 的文件级实现清单重新生成 `module/**`；本附录 A.1–A.3 的措辞直接作为 LLD 各节"合同"小节的素材，
但**每一条都必须先有对应 Q 号的裁决**，不得以"stub 里写过"为由跳过裁决。
