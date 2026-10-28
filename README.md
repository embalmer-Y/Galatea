# Galatea

> **建造具备感觉、情感、自我意识与学习能力的单一认知个体**——一切"具备"以可干预、可测量、可复算的真实因果结构为证（功能/因果实在论，D-10）。
>
> Galatea is a research project building a *single cognitive individual* with sensation, emotion, self-models, and learning — where every capability claim must be backed by intervenable, measurable, recomputable causal structure.

[![license](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![status](https://img.shields.io/badge/gates-43%20frozen%2Fexited-brightgreen) ![tests](https://img.shields.io/badge/pytest-824%20passed-success) ![phase](https://img.shields.io/badge/current-P4%20%E9%A2%84%E6%B5%8B%E8%84%91%20v2-orange)

---

## 1. 这是什么

Galatea 不是聊天机器人，也不是一个 Agent 框架。它是一个**认知个体的建造工程**：从最小世界（MW0）里的确定性生命开始，逐步长出感觉、情感、动机、记忆、语言与自我模型，最终走向物理具身。

项目的第一性纪律是 **D-10（可干预、可测量、可复算）**：

- **可干预**——每项能力都有对应的消融/注入面，"关掉它应该坏"是可机械检验的（E1 病灶电池、protection 保护集）；
- **可测量**——一切判据先于结果冻结（stat plan 运行前冻结 + sealed held-out 评价 + Holm 校正），禁事后挪门柱；
- **可复算**——给定权重的确定性：同种子重放逐位恒等（bit-exact），评价可被无关联的第三方独立复算（I1/I2/I3 纪律）。

2026-10-11 起，项目完成一次宪法级修订（[ADR-G-0029](adr/ADR-G-0029.md)）：验证手段不被当成架构教条——主线转向**预测脑 v2**（分层生成模型 + 预测误差最小化 + 主动推理），学习参数作为工件（digest 锚定）经 promotion 门入环，LLM/神经组件在留痕/消融/归属纪律下解禁；**安全包络全体不可让渡**。

## 2. 当前状态（2026-10-28）

- **门链 43 门**：F0→M0→M1→M2→R0→C0–C5→E1→H1→P1 十四门退出后，预测脑 v2 主线推进——**P4-α（脑核）已退出**（[ADR-G-0032](adr/ADR-G-0032.md)，margin 0.043 < 0.1）、**P4-β（心智：草稿板/思维迭代/慢环 + GCTB）已退出**（[ADR-G-0034](adr/ADR-G-0034.md)）、**P4-γ（行动与学习：EFE/MPC/在线学习门/做梦巩固）已冻结**（[ADR-G-0035](adr/ADR-G-0035.md)）。每门判据、独立评审（REV-0003…0031）与证据工件均在库可溯。
- **验证基线**：`uv run pytest` **824 passed + 1 skipped**（INC-16 恢复战役终态，含重建器测试 3 件；GPU 层无 CUDA 时跳过）；pyright strict 四平面 0 错误；`check_docs` 0 FAIL（36 份 YAML / manifest v1.42 = 83 锚终态：52 匹配 + 31 lost【= 28 status_inc16 LOST + 3 status_inc13 LOST + 1 status_p2 SUPERSEDED，1 件双注记去重——REV-0032 R1 口径更正】+ 0 failed）；import-linter 4 契约 KEPT；保护集 142 场景只增不减。
- **治理**：登记册 CONFIRMED 189 项裁决（AI 主导裁决 + owner 否决权，DEV_SPEC §4.6）；35 份 ADR；独立评审报告 32 份（`_audit/reviews/`）。
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
├── adr/                 # 35 份架构决策记录（ADR-G-0001…0035）
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

## 5. 快速开始（从零重建）

**系统前置：只需 `git` 与 `uv`，其余全部由锁文件自动安装（全部为预编译 wheel，无需编译器/系统库）。**

```bash
# 1) 安装 uv（x86_64 与 aarch64 同一脚本；也可用 pipx install uv）
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"        # 非交互 shell 必需（uv 默认装在 ~/.local/bin）

# 2) clone + 依赖安装（uv 自动下载钉版 CPython 3.12.13——.python-version 与 requires-python 双重钉死）
git clone git@github.com:embalmer-Y/Galatea.git   # 需已配 GitHub SSH key；HTTPS clone 亦可
cd Galatea
uv sync --extra tessera --frozen    # --frozen = 锁外漂移即拒（uv.lock 全包哈希覆盖，require-hashes）；
                                    # tessera extra = zenoh/CBOR 部署面——缺它 pytest 收集即报错（环境缺陷显式暴露）
                                    # 系统依赖补齐（Debian/Ubuntu）：sudo apt install -y git

# 3) 验收基线（数字不等 = 环境问题，先修环境再继续）
uv run pytest --tb=no -q              # 期望：824 passed, 1 skipped（GPU 层，无 CUDA 机器跳过属正常）
uv run python _audit/check_docs.py    # 期望：0 FAIL；fresh clone 无 evidence/ → 4 项 SKIP 属正常（digest 锚已随 git 持久化）
uv run lint-imports                   # 期望：Contracts: 4 kept, 0 broken
```

评价入口（正式首评复现，见 `galatea/evidence/control/entry.py`）：

```bash
uv run python -m galatea.evidence.control.entry --help   # m1|carryover|root|c1..c5|p1|p4|p4beta 子命令
```

### 6.1 已知陷阱（历史实战沉淀，P1/拓扑迁移期实证）

| 陷阱 | 现象 | 处置 |
|---|---|---|
| **venv 移动后必须重建** | 目录迁移/拷贝后入口脚本 spawn ENOENT（shebang 携带旧绝对路径） | `rm -rf .venv && uv sync --extra tessera --frozen`（uv sync 校验通过但运行会炸——必须删掉重建） |
| **非交互 SSH 无 uv** | 部署脚本 fail-fast：uv 不在 PATH | `export PATH="$HOME/.local/bin:$PATH"`（deploy 脚本已内置该义务检查） |
| **主机缺 git** | static_reports 生成器 spawn git 失败 | `sudo apt install -y git`（deploy 脚本已内置该义务检查） |
| **fresh clone 的 SKIP** | check_docs 报 4 项 SKIP | 不是 FAIL——evidence/ 不入库（两段式载荷：git archive + evidence tar，见 §7）；digest 锚已随 git 持久化，逐件恢复用 `scripts/evidence_backup.py drill` |

## 6. 平台支持与多机重建

**平台矩阵**（uv.lock 为单锁多平台通用锁，全包哈希锁定）：

| 平台 | 状态 | 依据 |
|---|---|---|
| Linux x86_64 | **全链验证**（开发机 + 部署主机 757→824 基线逐版本全等） | 本机实测 |
| **Linux aarch64 (ARM)** | **整机验证**（2026-10-28 首台） | Radxa Cubie A7A（Allwinner，2×A76+6×A55，6GB RAM）实测：五步验收清单全过——824 passed+1 skip 与基线全等 / check_docs 0 FAIL（83 锚结算）/ 4 KEPT，含全部 P4 神经训练回归（aarch64 CPU bit-exact 成立）。全量 pytest ~3.4h ≈ x86 的 4–5 倍：开发/常驻运行可用，重型 claim 评价留 x86 机 |
| macOS (x64/Apple Silicon) | 锁级就绪（P4 脑面除外），未验证 | 锁含 darwin 分辨标记与 arm64 wheel；注意：P4 神经模块版本合同钉 `2.14.1+cpu`（Linux 轮子），macOS 装到 `2.14.1` 无 +cpu 后缀，P4 profile loader 会 fail-closed——非 P4 面（kernel/env/subject 基础面）不受影响 |
| Windows | 锁级就绪，未验证 | 锁含 win 轮子 |

**ARM/Linux 多机实测**：首个整机验证已完成（2026-10-28，Radxa Cubie A7A，见平台矩阵；uv.lock aarch64 轮子覆盖 2026-10-17 锁级核验经实装证实）——后续新机型仍按下述验收清单执行，测后同步矩阵状态。

**重建验收清单（每台新机器跑一遍，任何一步不等即回报环境问题）**：

1. `uv sync --extra tessera --frozen` 零报错（ARM 上若报 no matching wheel = 锁覆盖缺口，如实回报）；
2. `uv run pytest --tb=no -q` = **824 passed, 1 skipped**（与开发机全等）；
3. `uv run python _audit/check_docs.py` = 0 FAIL；
4. `uv run lint-imports` = 4 KEPT；
5. `uv run python -m galatea.evidence.control.entry`（无参数）正常输出子命令表。

**可选件（均不在验收基线内）**：GPU 隔离 venv（CUDA 确定性认证——`scripts/p4beta_gpu_cert.py`，当前认证于 x86 + RTX 5060 Ti / torch 2.14.1+cu130）；音频/P2/P3 物理脚本（`scripts/audio_*.py`、`p3_*.py` 需真实声卡/Tessera 硬件，不进 pytest 基线）。

## 7. AI 开发会话引导（在新主机重建会话）

本项目的开发由 AI 会话自主执行（owner 立法 + AI 裁决 + 独立评审三权结构）。在新机器上重建开发会话：

1. **clone + 环境**：按 §5 快速开始；基线 824 passed 必须全等——不等即环境问题，先修环境；
2. **第一必读**：`AGENTS.md`（当前状态/纪律/在办事项）→ `DEV_SPEC.md`（流程法规）→ `design/HLD.md`（架构规范源）；
3. **裁决纪律**：一切新参数/新机制先在 `design/open_questions.md` 立 Q 号成文裁决（背景/选项/选择/影响/重开条件），再动实现——**无源常量与"先改实现后补裁决"都是流程违规**；
4. **评价纪律**：stat plan 运行前冻结、sealed 评价集、保护集只增不减、顺延终止条款（统计评价不可无限顺延）；
5. **安全纪律**：凭证仅环境变量/会话内使用，禁入库；evidence/ 不入库但 digest 锚定于 manifest；每门退出做 evidence 异地备份（Q-L13-14）。

## 8. 物理部署（Linux 主机）

- `scripts/deploy_p1_host.sh`：全栈部署（两段式载荷：git archive + evidence tar；fail-fast 义务检查）；
- `scripts/deploy_resident_host.sh`：常驻三服务（galatea-zenohd 路由 / galatea-body-sim 体模拟源【诚实标注】/ galatea-resident 主体常驻，SIGKILL 自愈 + 状态快照恢复）；
- `scripts/evidence_backup.py`：evidence 异地备份 + 逐件恢复演练（backup / drill 双模式）；
- Tessera 传感平台桥（zenoh + CBOR）：`galatea/env/tessera_bridge.py`（sensing-only）。

## 9. 文档地图

| 想了解 | 去看 |
|---|---|
| 项目宪法与当前状态 | `AGENTS.md` |
| 流程法规（裁决权/评审/事故登记） | `DEV_SPEC.md` |
| 高层架构（双平面/门体系/预测脑 v2 §15） | `design/HLD.md` |
| 每个模块的冻结设计 | `design/lld/L00…L13` |
| 一切参数的裁决出处 | `design/open_questions.md`（189 项） |
| 重大决策（含 owner 指令原文） | `adr/ADR-G-0001…0035` |
| 独立评审与事故登记 | `_audit/reviews/`、`DEV_SPEC.md` INC 节 |
| 脑功能完备性评估 | `config/evidence/brain_function_inventory.yaml` + Q-L13-19 |
| 哲学评分（Birch 框架） | `config/evidence/birch_markers.yaml` + Q-L13-18 |

## 10. 开源协议

[MIT](LICENSE) © 2026 embalmer-Y
