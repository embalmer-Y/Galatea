# PhysIO tests（twister）

> ⚠ 状态：RESEARCH 期规划（2026-09-16）。本目录**没有任何测试代码**；
> 测试在 HLD/LLD 冻结后随实现一同生成。以下为验收面的规划描述。

- `unit_host/`：纯主机单测（调理链确定性、协议编解码），可 native_sim 跑。
  - 其中“调理链确定性” = “同一输入序列必得同一输出序列”重放断言（见附录 A §A.3.4），**与协议选型无关，可先定**。
  - 其中“协议编解码” **依赖 Q-PIO-07b/07c 裁决**，裁决前不建。
- `integration/`：twister 场景（注册表热插拔、fail-safe、estop 时序），native_sim + 硬件板。
- CI 机械验证项（提案，待裁决）：
  1. （ADR-0001）单独构建 `module/`（不带 app）必须成功 ⇒ 框架零 Galatea 依赖的唯一证据。
  2. （Q-PIO-07a “最小可替换面”契约）**依赖方向检查**：`io/`、`core/` 源码不得 include COM 的
     framing/link/session 内部头；`io/`、`core/`、`config/`、schema 中不得出现帧字段名
     （magic / crc16 / batch / session_zid / scouting …）。黑白名单以 YAML 声明，grep 级脚本，违反即 fail。
  3. （Q-L10-08 对齐）**急停路径隔离检查**：estop ISR 符号不得调用 COM 任何 API（符号级静态检查）。
  4. 内存预算断言：若引入第三方协议栈（如 zenoh-pico），flash/RAM 上限进 CI 断言 + SBOM。

M0 起逐个填充；命名遵循 Zephyr twister 约定（testcase.yaml）。
