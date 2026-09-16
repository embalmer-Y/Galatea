# ADR-PIO-0002：Wire Protocol v1 设计基线（CBOR + 命令-回执分离）

- 状态：PROPOSED（待 owner 批准；关联 Q-PIO-07）
- 日期：2026-09-15

> ⚠️ **本 ADR 属研究阶段的过早决定，owner review 中，不得作为任何实现依据（2026-09-16）。**
> 问题：它以"编码选型"（Q-PIO-07）之名，实际上一次性决定了三层东西：
> COM-L2 帧格式（第 2 条）、COM-L3 寻址方式（固定消息类枚举，无命名空间/无通配/无发现协议）、COM-L5 payload 编码（第 1 条），
> 其中 **COM-L2 framing 与整个 COM-L3 从未被登记为 Q 号** ⇒ 裁决边界不清。
> 另：曾把结论固化进构建系统（`module/Kconfig` 的
> `choice PHYSIO_COM_PROTOCOL_VERSION` / `default PHYSIO_COM_PROTOCOL_V1 "v1 (CBOR)"`），该文件已随实现产物一同删除。
>
> **处理候选（待裁决，见 `RESEARCH_02_comm_protocol.md` §8.4）**：
> ① ACCEPTED（整体生效）｜② **拆为 0002a + 0002b**（0002a = COM-L5 payload 编码 + schema 单一源，长期有效且与后端无关；
> 0002b = V1 COM-L2/COM-L3 = 自研帧，显式标注"V2 可被后续 ADR 替换"）｜③ SUPERSEDED（V1 直接用 Zenoh 则整份作废）。
>
> 其中**第 1、5 条（CBOR 编码 + schema 单一事实源）与传输后端选型正交**，可归入 Q-PIO-07c 独立裁决。
> **第 3 条（命令-回执分离）同样是传输无关的 COM-L4 语义**，即使换 Zenoh 也必须自己实现（Zenoh 的重传层不等于应用层回执）⇒ 抢救价值最高。
> 本文内容已全量收入 `RESEARCH_01_appendixA_contract_notes.md` §A.2（NON-NORMATIVE 研究输入）。

## 背景

宿主（PC/机器人主控/Galatea Bridge）与 MCU 之间需要单一协议边界。要求：可版本化、带宽友好（BLE 场景）、能区分"没收到/没执行/执行失败"、与 MCUmgr/SMP 并存不重复。

## 决策

1. **编码 CBOR**（Zephyr 内置 tinycbor，无第三方依赖；二进制自描述，schema 演进友好）。备选 nanopb 被否：schema 文件工具链重、字段演进语义弱于 CBOR map。
2. **帧**：`magic(2B) | version(1B) | len(2B) | crc16 | payload`；单帧 ≤ 传输 MTU，长消息会话层分片。
3. **命令-回执分离**（继承 Galatea L10 认识链但独立成立）：
   - `CMD(command_id, idempotency_key, deadline, payload)` → 固件立即 `ACK`（已接受/已拒绝+原因）；
   - 执行完成另发 `RECEIPT(command_id, result, error_code?)`；
   - 宿主因此可三分：无 ACK=没收到；ACK+无 RECEIPT=没执行完；RECEIPT(error)=执行失败。
4. **管理面复用 SMP/MCUmgr**（OTA、镜像、重启），不重复造轮子；数据面/控制面走本协议。
5. **schema 单一事实源**：`tools/schema/` 定义 → 代码生成 C 头 + Python(Pydantic) 模型，机械防止固件/宿主两侧漂移。

## 后果

- 正面：与 Galatea P1 合同天然对齐（ACK≈SubmittedCommand 接受、RECEIPT≈ReceivedExecutionReceipt）；独立项目使用时语义同样自明。
- 代价：CBOR 体积略大于 protobuf；自研会话层（分片/去重/超时）需要自建测试（PIO-M1 主机侧单测覆盖）。
