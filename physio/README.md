# PhysIO

基于 **Zephyr RTOS** 的 MCU 末端输入输出框架：让单片机成为各种系统/机器人的可插拔末端 I/O 模块。

- 定位：独立可复用子项目（Zephyr module），同时作为 Galatea P1 物理具身的固件端（见 `../design/lld/L10_action_gateway_physio_attribution.md` §4.6）。
- 核心原则：**非学习、确定性、版本化、fail-safe**——固件端只做驱动/校准/滤波/有界控制图/局部保护，不产生语义、不做决策。

## 三大子系统（计划布局，源码待 HLD/LLD 冻结后生成）

| 子系统 | 计划目录 | 职责 |
|---|---|---|
| 通信 COM | `module/src/com/` | 线协议（握手/流订阅/命令-回执分离）、传输抽象（USB-CDC/UART/BLE）、MCUmgr/SMP 管理与 OTA |
| 输入输出 IO | `module/src/io/` | 设备注册表与热插拔、输入通道（Input/Sensor/RTIO）、输出通道（GPIO/PWM/执行器）、校准/确定性滤波、局部保护与急停 |
| 系统内核 CORE | `module/src/core/` | 引导/MCUboot 集成、参数存储（Settings/NVS）、控制图执行器（digest 冻结+签名）、LLEXT 动态扩展（V2 门控）、看门狗/黑匣子/健康上报、身份与时间基准 |

解耦骨架：三子系统之间只经 **zbus** 通道与公开 C API 交互。

> ⚠️ "Wire Protocol v1 = CBOR" 曾是研究期的过早决定（`docs/adr/ADR-0002*`）。
> 该决定**待 owner review**，可能降级为候选；因此上表 COM 一行暂不写具体编码。
> 协议选型调研见 `docs/RESEARCH_02_comm_protocol.md`（尚未落盘，结论已在会话中给出，等裁决后再写）。

## 目录结构

```text
physio/
├── README.md               ← 本文件
├── west.yml                ← west 工作区清单（研究期草案，revision 待 Q-PIO-01 裁决）
├── docs/                   ← 调研、ADR（架构决策记录）
├── module/                 ← ★ 框架核心（规划为 Zephyr module，独立可复用，不含 Galatea 概念）
│   │                         研究期：仅空目录 + .gitkeep，无任何源码/构建文件
│   ├── zephyr/               ← （M0 起）module.yml
│   ├── include/physio/{com,io,core}/    ← （M0 起）公共头
│   ├── src/{com,io,core}/               ← （M1–M4 起）实现
│   ├── dts/bindings/       ← （M0 起）自定义设备绑定（physio,*）
│   └── samples/            ← （M0 起）最小示例
├── app/
│   └── galatea_node/       ← Galatea 对接固件（薄映射层，可整体删除而不影响框架）；研究期为空
├── config/
│   ├── devices/            ← 设备清单/能力描述符（YAML 格式草案）
│   ├── control_graphs/     ← 控制图定义（签名前源文件）
│   └── protection_profiles/← 保护阈值/安全态 profile（草案）
├── tests/                  ← twister 测试（native_sim + 硬件）；研究期仅有规划说明
└── tools/                  ← 宿主侧 CLI / Python SDK / 签名与图编译工具；研究期仅有规划说明
```

## 构建（研究期：不适用）

**当前仓库没有任何可构建目标**——`module/` 与 `app/` 只有空目录。这是刻意的：
流程为 research → HLD → LLD → 实施，实现产物须在 HLD/LLD 冻结后按文件级实现清单生成。

M0 起（west 工作区在仓库**之外**初始化，Zephyr 树不进 Galatea 仓库）：

```bash
# 例：在 d:\Software\project\ 下建工作区
mkdir physio-ws && cd physio-ws
west init -l ..\Galatea\physio     # 以 physio/west.yml 为 manifest（self.path=physio）
west update                        # 拉取 Zephyr 及默认模块（约数 GB）
west build -b native_sim physio/app/galatea_node
west build -b nrf52840dk/nrf52840 physio/app/galatea_node   # 真实板（Q-PIO-02 待定）
```

## 状态

- 当前阶段：**RESEARCH（研究中）**。
  - 已完成：Zephyr 平台调研 + 功能范围确定（`docs/RESEARCH_01_scope.md`）；Zenoh/协议选型调研（结论待落盘为 `docs/RESEARCH_02_comm_protocol.md`）。
  - **2026-09-16 已撤回**：2026-09-15 误在研究阶段写出的 27 个实现产物（19 个 `.c` + 4 个 `.h` + `module/CMakeLists.txt` + `module/Kconfig` + `module/zephyr/module.yml` + `app/galatea_node/{CMakeLists.txt,prj.conf,src/main.c}`）。
    stub 注释中有价值的合同措辞已抢救进 `docs/RESEARCH_01_appendixA_contract_notes.md`（NON-NORMATIVE 研究输入）。撤回明细见该文 §A.5。
- 下一步：owner review 裁决项 → 冻结 HLD → LLD → M0 实施。
- **待 owner review 的裁决项**（全部 UNCONFIRMED）：
  - Q-PIO-01…10，登记在 `docs/RESEARCH_01_scope.md` §6（版本基线 / 目标板 / 传输集 / 热插拔边界 / LLEXT / 时间戳 / 协议编码 / 许可证与仓库形态 / 算子集 / SDK 位置）；
  - **Q-PIO-07 的升级提案**：拆为 07a（COM 五层分层 + 最小可替换面契约）/ 07b（V1 L2-L3 后端：自研帧 vs Zenoh vs MQTT-SN vs CoAP）/ 07c（L5 payload 编码 = 原 Q-PIO-07 收窄）/ 07d（V2 是否引入 Zenoh + spike 前置）/ 07e（是否允许宿主常驻进程）；
  - **Q-PIO-11（新增提案）**：Galatea 主体负清单（禁消息队列/RPC/编排框架/dashboard）的适用域是否覆盖 `physio/**`、`physio/host/`、以及宿主侧 PhysIO Bridge；
  - **负清单第 2 条修订变体** N2-a / N2-b / N2-c，及第 4 条（组网）配套修订；
  - **ADR-0002 处置**：ACCEPTED（整体保留）/ 拆为 0002a（payload 编码）+ 0002b（V1 帧，标注 V2 可替换）/ SUPERSEDED。
  - ⚠️ `docs/RESEARCH_01_scope.md` §3.2、§4 第 2/4 条、§6 Q-PIO-07 与 `docs/adr/ADR-0002*` **尚未按上述提案修改**，等裁决后一次性改，避免半成品文档互相矛盾。
- 许可证：待裁决（Q-PIO-08，建议 Apache-2.0）。
