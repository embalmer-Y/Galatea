# PhysIO tools（宿主侧）

> ⚠ 状态：RESEARCH 期规划（2026-09-16）。本目录**没有任何工具代码**。
> 下表中标 ⚠ 的行依赖未裁决项（Q-PIO-07b/07c、ADR-PIO-0002），裁决前不得实现。
> 另外：宿主侧到底受哪套负清单约束尚未裁决（**Q-PIO-11 提案**），它直接决定 `physio_host/` 能否引入第三方客户端库。

| 工具 | 用途 | 里程碑 | 依赖裁决 |
|---|---|---|---|
| `physio_host/`（Python SDK） | 协议客户端：握手/订阅/CMD-ACK-RECEIPT/OTA；与 Galatea Bridge 分离（Q-PIO-10） | PIO-M1 | ⚠ Q-PIO-07b/07e/Q-PIO-11 |
| `sign_graph.py` | 控制图签名 + digest 计算（编码待 Q-PIO-07c 定，ADR-PIO-0002 草案为 CBOR） | PIO-M4 | ⚠ Q-PIO-07c |
| `sign_image.py` | 镜像签名包装（或直接走 imgtool/MCUboot 工具链） | PIO-M3 | 无（与协议选型无关） |
| `schema/` | 应用层 schema（COM-L5）单一事实源 → 生成 C 头与 Pydantic 模型（防两仓漂移） | PIO-M1 | ⚠ Q-PIO-07a/07c |
| `cli.py` | 最小命令行运维（list devices / stream / update firmware），无 GUI | PIO-M1 | ⚠ Q-PIO-07b |

约束：
- 不引入任何 GUI/仪表盘依赖（Galatea 负清单第 6 条同源纪律；注意：Galatea 主体负清单对 `physio/**` 是否适用待 Q-PIO-11）。
- **schema 单一事实源这条纪律与编码选型正交**：无论最终选 CBOR 还是 nanopb，C 头与 Pydantic 模型都由单一源生成。
