# L00 横切基础：时钟、调度、状态、RNG、Packet、Registry 核心、typed unknown

> LLD: L00/14 · v1.0 · 2026-09-12（v1.0.1 头部补齐 2026-09-13） · 状态：WORKING（F0 冻结前）
> 上游：`HLD.md` §3.4/§4/§7/§9/§11/§12 · `open_questions.md` C 区
> 下游消费者：**全 13 档**——L01（时钟/包/registry 写入）、L02–L09（`CognitivePacket` 传输、RNG 流、`virtual_time`、typed unknown、checkpoint）、L10（digest 谱系/分支校验）、L11（`registry.put` 候选工件与父 digest）、L12（同步阻塞禁止/预算记账）、L13（manifest digest、I1 重放接口、谱系治理）
> 引入门槛：**F0**（工程合同期即须成立）
> 本档定义整个系统的确定性骨架。其他 13 份 LLD 全部构建在本档契约之上。

## 1. 目标与范围

**目标**：为认知主体平面与科学平面提供六项横切能力——多速率虚拟时钟、确定性协作调度、单写者状态存储、counter-based RNG、跨模块消息协议（CognitivePacket）、content-addressed registry 核心，以及类型化不确定性（typed unknown）。

**范围内**：
- 逻辑时钟与 T0–T6 调度器（自研，见 Q-T04 裁决）；
- CognitivePacket envelope/payload 分层与 schema 版本管理；
- 三库分离协议（subject_state / subject_memory / registry）与 checkpoint 谱系；
- RNG 流派生与隔离；
- content-addressed registry 的存取核心（治理与 promotion 在 L13）；
- typed unknown 的统一类型体系；
- canonical JSON 与 content_digest 规范。

**范围外**：任何认知语义（感觉、知觉、目标、情感）——本档只见 envelope 不见 payload 语义；recorder 证据格式（L13）；promotion 治理（L13）。

**成功判据**：同一 (profile, seed, artifact digest) 下任意运行可 bit-exact 重放；调度决策可在不读取 payload 的情况下复现；三库边界经权限测试验证不可穿透。

## 2. Ports（输入输出契约）

L00 是提供方，不消费认知内容。对外暴露三类接口：

### 2.1 PortIn（被调用）

| 端口 | 调用方 | 数据 | 表示层级 | schema |
|---|---|---|---|---|
| `clock.now()` | 全体模块 | `VirtualTime(cycle_id, virtual_time_ns)` | —（基础设施） | L00.clock.v1 |
| `scheduler.register(module_id, t_level, handler)` | 全体认知模块 | `Registration(module_id: str, t_level: int[0..6], period_cycles: int)` | — | L00.sched.register.v1 |
| `scheduler.submit(packet)` | 全体模块 | `CognitivePacket`（只读 envelope） | envelope 携带其声明层级 | L00.packet.v1 |
| `rng.stream(run_seed, branch_id, module_id, stream_name)` | 全体模块 | 派生 counter-based 流句柄 | — | L00.rng.v1 |
| `state.open_writer(store, table)` / `state.read(store, query)` | 唯一写者模块 / 任意读者 | 行级读写 | — | L00.state.v1 |
| `state.checkpoint(branch_id, parent_checkpoint_id?)` | 内核/实验控制 | `CheckpointRecord` | — | L00.state.ckpt.v1 |
| `registry.put(blob, kind) → ArtifactRef` | 各平面 | 字节流 + kind（model/profile/dataset/evidence/code） | — | L00.reg.v1 |
| `registry.get(artifact_ref)` | 各平面 | 按 digest 取回 | — | L00.reg.v1 |

### 2.2 PortOut（发布）

| 端口 | 读者 | 数据 | 保证 |
|---|---|---|---|
| `dispatch.next_due()` | 调度循环 | 下一到期模块 + 待投递 packets | 只读 envelope 元数据 |
| `state.committed(checkpoint_id)` | recorder（L13） | 提交事件 + causal trace digest | 提交后不可变 |
| `registry.digest_event` | recorder（L13） | 每次 put/get 的审计事件 | append-only |

### 2.3 CognitivePacket 规范

```text
CognitivePacket(
  event_id: str,                 # ULID，单调可排序
  subject_candidate_id: str,     # D-14：单实例
  run_id: str, branch_id: str,   # 谱系寻址（branch = 谱系引用非物理复制）
  activity_window_id: str, cycle_id: int,
  virtual_time: int,             # ns，单调不减，只来自 clock
  source_module: str,            # 禁止匿名（None/"" 即拒绝）
  content_type: str,             # 版本化注册名，如 "sensory_frame.formation.v1"
  representation_level: enum,    # RECEIVED/SENSORY_FORMED/PERCEIVED/PREDICTED/IMAGINED/RECALLED/EXTERNAL_STATEMENT
  schema_version: str, payload_ref: ArtifactRef,   # 大对象只读引用 + digest
  confidence: float|Unknown,     # Unknown 必须 typed（§6），禁裸 None/字符串
  provenance: Provenance(source_events, channel_ref, calibration_version, gain_receipt?),
  causal_parent_ids: list[event_id],
  access_scope: enum,            # PUBLIC_BROADCAST/MODULE_LOCAL/EVIDENCE_ONLY…
  content_digest: str            # canonical JSON sha256
)
```

**纪律**：envelope 提交后不可变；修正以新事件引用旧事件（revision）；消费方必须记录 `accepted/rejected/ignored/deferred` + 理由码；`causal_parent_ids` 构成因果 DAG，任何包不得无父（根事件除外，由 L01 边界端产生）。

## 3. 状态所有权与单写者

| 状态 | 唯一写入者 | 存储 | 读者 |
|---|---|---|---|
| 时钟/周期计数 | 内核（scheduler 推进） | subject_state | 全体（只读） |
| 调度注册表 | 内核（启动期） | subject_state | 内核 |
| RNG 流计数器 | rng.stream 持有模块 | 内存 + checkpoint | 内核（checkpoint 时序列化） |
| checkpoint 谱系表 | 内核（state.checkpoint） | subject_state | recorder、实验控制 |
| registry blob/索引 | registry builder（外部） | registry.db + 文件系统 | 全体（只读 get） |
| typed unknown 登记册 | 各产生模块（经统一类型） | subject_state.unknowns | 元认知（L09）、审计 |

**三库物理分离（Q-T05 CONFIRMED）**：`subject_state.db` / `subject_memory.db`（L06 独占写） / `registry.db`。连接层禁止跨库事务；CI 权限测试验证主体记忆库对 orchestrator 只读（禁止写入路径 `orchestrator → subject memory`）。

**checkpoint 协议**：`CheckpointRecord(checkpoint_id, parent_checkpoint_id, branch_id, virtual_time, digest_state, digest_memory, digest_registry_view, rng_snapshot, profile_ref, artifact_refs)`。谱系形成 DAG；`clone ≠ identity`（D-12）由谱系表机械表达——分支仅用于实验对照，身份延续只存在于主干谱系。

## 4. 算法与数据结构

### 4.1 确定性协作调度器（自研，Q-T04 CONFIRMED）

- **就绪队列**：`heapq`，排序键 `(effective_due_time, t_level, module_id, seq)`；`seq` 为包序数，保证 tie-break 全序、跨平台稳定。
- **调度环**：取下一到期模块 → 按 `causal_parent_ids` 拓扑序投递其入队包 → 调用 handler（协作式：handler 不得阻塞、不得启线程；超时由 watchdog 注入 TimeoutEvent 类型化）→ 收集出包 → `commit()` 原子提交状态 + causal trace → `advance clock` 至下一到期点。
- **payload 不可见性**：调度器只解析 envelope 字段；payload 仅经 `payload_ref` 由目标模块自行从 registry 取回。机械保证"调度决定时间、不决定认知内容"。
- **T0 反射优先**：T0 模块的 due 事件可抢占低级别模块的**下一个**处理片（协作点），不被中断当前片——保证确定性。

### 4.2 多速率虚拟时钟

- 单一单调 `virtual_time_ns`，按 cycle 推进；各 T 级以 `period_cycles` 表达频率（frozen profile 给定；N2–N5 初值已裁决 CONFIRMED，Q-L00-01，2026-09-23，M0 实测复核）。
- 墙钟只允许出现在 recorder manifest 的独立字段（Q-T12）；主体平面模块调用 `time.time()`/`datetime.now()` 由 lint 规则禁止。

### 4.3 counter-based RNG

- 算法：ChaCha8/Philox 类 counter-based 流；`stream(run_seed, branch_id, module_id, stream_name)` 以 HKDF 派生独立子种子 → 流内 counter 递增。
- **禁止**：`random`/`np.random`/`torch` 全局 RNG 状态（lint + 运行时钩子双重禁止）；任何采样必须持有显式 stream 句柄。
- **分支隔离**：不同 `branch_id` 派生天然独立流，保证 M2 随机分支 intent-to-treat 无污染。
- checkpoint 时序列化 `(stream_key, counter)`。

### 4.4 canonical JSON 与 content_digest

- 规范：键排序、UTF-8、无尾随空白、2 空格缩进可选（digest 用紧凑形式）、浮点固定 `repr`（round-trip 精度）；bytes → base64；`sha256(canonical_json(envelope_without_digest))`。
- payload blob 单独 digest：`sha256(bytes)`。

### 4.5 content-addressed registry 核心（~500 行，Q-T09 CONFIRMED）

- 布局：`registry/<sha256[:2]>/<sha256>/`（`manifest.json` + `blob`）；索引 `registry.db(artifact_ref, kind, digest, created_cycle, parent_digests, size)`。
- `put` 幂等（同 digest 同内容）；`get` 只读；**拒**：网络源、MLflow/W&B/DVC（见 HLD 负清单）。外部包仓库（PyPI/OCI）仅作依赖源且 `uv lock --require-hashes`（Q-T08 CONFIRMED）。
- Promotion 治理、保留策略、sealed evaluation 隔离在 L13，本档只提供存取与 digest 完整性。

## 5. 时间尺度与调度挂点

L00 自身运行在**每个 cycle 的边界**：调度环每 cycle 执行一次 `dispatch.next_due()`；checkpoint 在 `commit` 点原子触发。T0–T6 各级频率（Q-L00-01 CONFIRMED 2026-09-23：初值如下，M0 实测复核；2 的幂梯保证 T3–T6 在 64-cycle 公倍点对齐）：

| 级 | 建议默认频率 | 说明 |
|---|---|---|
| T0 | 每 cycle | containment/保护反射 |
| T1 | 每 cycle | 接收/感觉形成 |
| T2 | 每 cycle | 知觉/appraisal/affect |
| T3 | 每 N2 cycles（默认 N2=2） | 工作空间竞争/广播 |
| T4 | 每 N3 cycles（默认 N3=4） | 目标/规划/元控制 |
| T5 | 每 N4 cycles（默认 N4=16） | 重放/学习提案 |
| T6 | 每 N5 cycles（默认 N5=64） | 巩固/promotion/保护集 |

## 6. 失败模式与 typed unknown

### 6.1 typed unknown 类型体系

```text
Unknown(reason: UnknownReason, evidence_refs: list[event_id], detail: str?,
        detected_by: module_id, virtual_time: int)
UnknownReason ∈ {MISSING_SIGNAL, CALIBRATION_UNCERTAIN, SOURCE_AMBIGUOUS, OOD,
  CONFLICTING_EVIDENCE, INSUFFICIENT_OBSERVATION, CAPABILITY_LIMIT,
  ATTRIBUTION_UNRESOLVED, DECISION_PATH_UNRESOLVED, ...}  # 冻结清单在 F0 profile
```

**禁止**：裸 `None`、空字符串、字符串 `"unknown"` 充当不确定性；CI 静态规则 + schema 校验双重拒绝。任何"静默忽略"必须转为 `Unknown(DECISION_PATH_UNRESOLVED, …)` 并进入 `state.unknowns`（呼应 HLD §6.2"未闭合路径"）。

### 6.2 失败类型化（呼应 HLD §11.3）

| 失败 | 类型化事件 | 行为 |
|---|---|---|
| 模块超时 | `TimeoutEvent(module_id, deadline, virtual_time)` | 注入包队列；调度继续；计数入指标 |
| schema 不匹配 | `SchemaViolation(packet_ref, expected, actual)` | 拒绝投递；reason=SCHEMA |
| digest 校验失败 | `IntegrityViolation(artifact_ref)` | 立即 fail closed；S1 缺陷 |
| checkpoint 写失败 | `CheckpointFailure(parent_id, cause)` | 停止 claim-relevant 运行（recorder 失败同理） |
| RNG 流缺失 | `StreamNotFound(key)` | 注入 Unknown(STREAM_MISSING)；禁回退全局 RNG |
| registry put 冲突（同 digest 异内容） | `RegistryCollision(digest)` | fail closed；S0 缺陷 |

**纪律**：任何异常不得自动改写为"主体选择不行动"或"主体感觉正常"——失败必须类型化并可审计。

## 7. 可测性（指标 / 对照 / 消融 / 保护集）

| 层 | 测试 | 断言 |
|---|---|---|
| unit | 调度 tie-break、RNG 流派生、canonical JSON 稳定性 | 确定性 |
| contract | envelope 不可变、匿名来源拒绝、裸 unknown 拒绝 | schema 强制 |
| invariant | **任意 packet 序列下 representation_level 不得被广播/缓存/存储提升**（Hypothesis property test） | 认识链 |
| deterministic replay（ReplayTest） | 同 (profile, seed, digests) 两次运行 commit 序列 bit-exact | M0/E1 核心 |
| integration | 三库分离、跨库事务禁止、orchestrator 写 subject_memory 被拒 | 禁止写入路径 |
| leakage（LeakageProbe） | 调度器在只读 envelope 时无法从 payload 推断决策；注入 payload 突变不改变调度顺序 | payload 不可见性 |
| protection suite | 重放 digest、RNG 隔离、checkpoint 谱系完整性 | M2/E1 不退化 |

**指标**：bit-exact 重放率=100%（硬门槛）；调度决策与 payload 互信息=0（抽样探测）；三库穿透尝试拦截率=100%；checkpoint 谱系无环。

**消融**：移除 RNG 流派生（退化全局 RNG）→ M2 随机分支对照污染应可检出；移除调度 tie-break → 跨平台重放 digest 应发散。

## 8. 不变量与禁止写入路径

**本档专属不变量**：
1. 调度器不读 payload（机械保证，非约定）；
2. 同一 (profile, seed, artifact digests) ⇒ bit-exact 重放；
3. 全局 RNG / 墙钟 / 容器迭代顺序依赖在主体平面为零（lint + 运行时钩子）；
4. checkpoint 谱系无环、分支不复制身份（D-12）；
5. typed unknown 全覆盖：无裸 None/空串/字符串 unknown。

**禁止写入路径（本档强制）**：`orchestrator → subject memory`｜`scheduler → payload`｜`global RNG → 任何采样`｜`wall clock → packet/subject state`｜`registry → 网络`（除依赖源 hash 锁）。

## 9. 引入门槛

- **F0**：envelope schema、typed unknown 清单、三库分离协议、canonical JSON/digest 规范冻结（进 frozen profile，门后不改 M0）。
- **M0**：调度器 + 时钟 + RNG + checkpoint 谱系全部实现并经 ReplayTest/LeakageProbe；registry 核心可用。
- **M2**：checkpoint 谱系支撑随机分支 intent-to-treat；RNG 分支隔离验证。
- **C0**：多速率 T0–T6、tensor payload_ref、完整 checkpoint 接入认知模块。

## 10. 实现清单（文件级）

```text
galatea/kernel/                  # strict 类型
  clock.py            VirtualTime, CycleClock
  scheduler.py        Scheduler, Registration, dispatch 环, tie-break
  packet.py           CognitivePacket(envelope), Provenance, AccessScope, 冻结构造
  payload.py          PayloadRef, schema_version 注册表接口
  unknown.py          Unknown, UnknownReason, unknowns 登记表
  rng.py              CounterStream, stream 派生(HKDF), checkpoint 序列化, chacha8_block 正式后端（Q-L00-04，2026-09-25）
  state.py            三库连接协议, single-writer 断言, CheckpointRecord, 谱系 DAG
  digest.py           canonical_json, content_digest, blob digest
  registry.py         content-addressed put/get, manifest, 索引
  watchdog.py         TimeoutEvent 注入, 协作点抢占
galatea/kernel/tests/
  test_tiebreak.py test_rng_isolation.py test_canonical_json.py test_registry_core.py  # registry 核心合同（2026-09-25 补录清单席位，承 REV-0003 R6 先例）
  test_replay.py(ReplayTest) test_leakage.py(LeakageProbe)
  test_state_separation.py test_checkpoint_lineage.py test_unknown_coverage.py
config/profiles/
  f0_l00.profile.yaml   频率/UnknownReason 冻结清单/digest 规范版本
```

## 11. 未决问题（→ open_questions.md）

| Q 号 | 问题 | 依赖 | 状态 |
|---|---|---|---|
| Q-L00-01 | T3/T4/T5/T6 频率比 N2/N3/N4/N5 默认值 | F0 冻结 profile | CONFIRMED（AI-v2 2026-09-23：2/4/16/64 初值 + M0 复核，见 open_questions A 区） |
| Q-L00-02 | UnknownReason 冻结清单是否需增删 | F0 | CONFIRMED（AI-v2 2026-09-23：9 项 + STREAM_MISSING 共 10 项冻结，增删走 schema 版本） |
| ~~Q-L00-03~~ | ~~float64 统一数值纪律~~ **已废弃**：被 Q-T10 CONFIRMED 裁决取代（模型 float32、证据/统计 float64），不再悬置 | — | CLOSED（归并入 Q-T10） |
| Q-L00-04 | RNG 算法 ChaCha8 vs Philox（性能与确定性权衡） | M0 前 | CONFIRMED（AI-v2 2026-09-25：ChaCha8 正式后端 chacha8_block，见 A 区） |
| Q-L00-05 | checkpoint 频率策略（每 cycle / 每 T6 / 事件触发）与存储成本 | M2 | UNCONFIRMED |
| Q-L00-06 | registry blob 去重阈值与大 artifact（模型权重）的分片策略 | C0 | UNCONFIRMED |
| Q-L00-07 | Hypothesis property test 的 packet 序列生成分布（均匀/对抗/谱系感知） | M0 | UNCONFIRMED |
