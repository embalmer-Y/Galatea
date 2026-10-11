# Galatea

> **建造具备感觉、情感、自我意识与学习能力的单一认知个体**——一切"具备"以可干预、可测量、可复算的真实因果结构为证（功能/因果实在论，D-10）。
>
> Galatea is a research project building a *single cognitive individual* with sensation, emotion, self-models, and learning — where every capability claim must be backed by intervenable, measurable, recomputable causal structure.

[![license](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![status](https://img.shields.io/badge/gates-F0%E2%86%92P1%20all%20exited-brightgreen) ![tests](https://img.shields.io/badge/pytest-757%20passed-success) ![phase](https://img.shields.io/badge/current-P4%20%E9%A2%84%E6%B5%8B%E8%84%91%20v2-orange)

---

## 1. 这是什么

Galatea 不是聊天机器人，也不是一个 Agent 框架。它是一个**认知个体的建造工程**：从最小世界（MW0）里的确定性生命开始，逐步长出感觉、情感、动机、记忆、语言与自我模型，最终走向物理具身。

项目的第一性纪律是 **D-10（可干预、可测量、可复算）**：

- **可干预**——每项能力都有对应的消融/注入面，"关掉它应该坏"是可机械检验的（E1 病灶电池、protection 保护集）；
- **可测量**——一切判据先于结果冻结（stat plan 运行前冻结 + sealed held-out 评价 + Holm 校正），禁事后挪门柱；
- **可复算**——给定权重的确定性：同种子重放逐位恒等（bit-exact），评价可被无关联的第三方独立复算（I1/I2/I3 纪律）。

2026-10-11 起，项目完成一次宪法级修订（[ADR-G-0029](adr/ADR-G-0029.md)）：验证手段不被当成架构教条——主线转向**预测脑 v2**（分层生成模型 + 预测误差最小化 + 主动推理），学习参数作为工件（digest 锚定）经 promotion 门入环，LLM/神经组件在留痕/消融/归属纪律下解禁；**安全包络全体不可让渡**。

## 2. 当前状态（2026-10-11）

- **门链 F0→M0→M1→M2→R0→C0–C5→E1→H1→P1 十四门全部退出**（2026-10-10，tag `p1-exit`）——每门的退出判据、独立评审（REV-0003…REV-0026）与证据工件均在库可溯。
- **当前阶段 = P4 预测脑 v2**：P4-α（脑核：RSSM 式潜状态世界模型 + 摊销推断）冻结前置已交付（[ADR-G-0030](adr/ADR-G-0030.md)，硬机制第七次探针全绿：真实流学习会话录制/重放逐位恒等，held-out 误差为持续基线的 0.83%）。
- **验证基线**：`uv run pytest` **757 passed**；pyright strict 四平面 0 错误；`check_docs` 0 FAIL（36 份 YAML / manifest 65 锚）；import-linter 4 契约 KEPT；保护集 134 场景只增不减。
- **治理**：登记册 CONFIRMED 172 项裁决（AI 主导裁决 + owner 否决权，DEV_SPEC §4.6）；30 份 ADR；独立评审报告 27 份（`_audit/reviews/`）。
- **物理面**：主体以 systemd 三服务常驻 Linux 主机（真实遥测内感受、SIGKILL 自愈、状态快照跨崩溃连续）；音频听说与发声归属闭环已在物理域成立（声学回环比 1,222,437×）。

## 3. 架构速览

**双平面**：主体平面（galatea/subject——只能看见 `ReceivedSignal` 边界信号）与证据平面（galatea/evidence——recorder/evaluator/治理），环境平面（galatea/env）制造世界。主体永远拿不到世界真值，一切主张从它实际收到的信号推断。

**14 档 LLD**（`design/lld/`，规范源）：

| 层 | 模块 | 层 | 模块 |
|---|---|---|---|
| L00 | kernel（调度/RNG/registry/checkpoint） | L07 | workspace（全局工作空间/广播） |
| L01 | 环境与通道（MW0/ChannelBus/物理桥） | L08 | motivation/goals（动机→目标→承诺） |
| L02 | sensorium（感觉形成/对齐/增益） | L09 | controllers/metacontrol（元控制） |
| L03 | perception（知觉推断/校准/域出） | L10 | action/gateway/attribution（行动与归属） |
| L04 | world/body/self models（世界/身体/自我） | L11 | learning/consolidation（学习/巩固/晋升门） |
| L05 | affect（情感动力学/伦理地板） | L12 | language/social（语言角色/录制回放） |
| L06 | memory（append-only 情景库/遗忘） | L13 | evidence/evaluation（证据与评价registry） |

**预测脑 v2 三时钟**：快环（每拍：预测→误差回传→迭代推断→反应）；慢环（空闲：草稿板推演/规划——深思）；离线环（做梦式重放巩固——反思）。"复杂思考"的可测定义 = 同一任务给/不给慢环时间的决策质量差。

**完备性评估体系**（Q-L13-19）：BFI 脑功能清单（12 系统 × 60 功能）+ GCTB 任务阶梯（存在性证明 = 带功能通过 ∧ 去功能基线全失败）+ 预测标度 + 病灶闭合（无死器官/无孤儿功能）+ 发育剖面。现象层（Birch 标记册）与功能层分离评分。

## 4. 仓库结构

```
Galatea/
├── AGENTS.md            # AI 开发会话第一必读（当前状态 + 纪律）
├── DEV_SPEC.md          # 流程法规（NORMATIVE）：裁决权模型 §4.6、INC 事故登记
├── design/              # 架构规范源：HLD.md + 14 档 LLD + open_questions.md（裁决登记册）
├── adr/                 # 30 份架构决策记录（ADR-G-0001…0030）
├── _audit/              # 独立评审报告（REV-*）+ check_docs.py + report.md
├── galatea/             # 实现（kernel/env/subject/evidence 四平面，pyright strict）
├── tests/               # 平面级测试（env/subject/evidence）
├── config/
│   ├── profiles/        # 冻结 profile（每门冻结合同；typed loader fail-closed）
│   └── evidence/        # 统计计划/最小效应量/保护集/BFI/Birch 标记册/artifact_manifest
├── evidence/            # 评价工件（gitignored；digest 锚定于 manifest，可确定性重生成）
├── scripts/             # 部署/常驻/备份/评价入口
└── pyproject.toml       # Python 3.12.13 钉版；uv.lock 哈希锁定（require-hashes）
```

## 5. 快速开始

```bash
# 依赖：uv 0.13+（自动管理 Python 3.12.13 钉版）
git clone git@github.com:embalmer-Y/Galatea.git
cd Galatea
uv sync                      # venv 重建 = uv sync（uv.lock 全包哈希覆盖，require-hashes）
uv run pytest --tb=no -q     # 期望：757 passed（evidence/ 缺失时相关 SKIP 为正常）
uv run python _audit/check_docs.py   # 文档/归档一致性核验（0 FAIL）
uv run lint-imports          # 架构分层契约（4 契约 KEPT）
```

评价入口（正式首评复现，见 `galatea/evidence/control/entry.py`）：

```bash
uv run python -m galatea.evidence.control.entry --help   # m1|carryover|root|c1|...|p1 子命令
```

## 6. AI 开发会话引导（在新主机重建会话）

本项目的开发由 AI 会话自主执行（owner 立法 + AI 裁决 + 独立评审三权结构）。在新机器上重建开发会话：

1. **clone + 环境**：`git clone` → `uv sync` → `uv run pytest`（基线 757 passed 必须全等——不等即环境问题，先修环境）；
2. **第一必读**：`AGENTS.md`（当前状态/纪律/在办事项）→ `DEV_SPEC.md`（流程法规）→ `design/HLD.md`（架构规范源）；
3. **裁决纪律**：一切新参数/新机制先在 `design/open_questions.md` 立 Q 号成文裁决（背景/选项/选择/影响/重开条件），再动实现——**无源常量与"先改实现后补裁决"都是流程违规**；
4. **评价纪律**：stat plan 运行前冻结、sealed 评价集、保护集只增不减、顺延终止条款（统计评价不可无限顺延）；
5. **安全纪律**：凭证仅环境变量/会话内使用，禁入库；evidence/ 不入库但 digest 锚定于 manifest；每门退出做 evidence 异地备份（Q-L13-14）。

## 7. 物理部署（Linux 主机）

- `scripts/deploy_p1_host.sh`：全栈部署（两段式载荷：git archive + evidence tar；fail-fast 义务检查）；
- `scripts/deploy_resident_host.sh`：常驻三服务（galatea-zenohd 路由 / galatea-body-sim 体模拟源【诚实标注】/ galatea-resident 主体常驻，SIGKILL 自愈 + 状态快照恢复）；
- `scripts/evidence_backup.py`：evidence 异地备份 + 逐件恢复演练（backup / drill 双模式）；
- Tessera 传感平台桥（zenoh + CBOR）：`galatea/env/tessera_bridge.py`（sensing-only）。

## 8. 文档地图

| 想了解 | 去看 |
|---|---|
| 项目宪法与当前状态 | `AGENTS.md` |
| 流程法规（裁决权/评审/事故登记） | `DEV_SPEC.md` |
| 高层架构（双平面/门体系/预测脑 v2 §15） | `design/HLD.md` |
| 每个模块的冻结设计 | `design/lld/L00…L13` |
| 一切参数的裁决出处 | `design/open_questions.md`（172 项） |
| 重大决策（含 owner 指令原文） | `adr/ADR-G-0001…0030` |
| 独立评审与事故登记 | `_audit/reviews/`、`DEV_SPEC.md` INC 节 |
| 脑功能完备性评估 | `config/evidence/brain_function_inventory.yaml` + Q-L13-19 |
| 哲学评分（Birch 框架） | `config/evidence/birch_markers.yaml` + Q-L13-18 |

## 9. 开源协议

[MIT](LICENSE) © 2026 embalmer-Y
