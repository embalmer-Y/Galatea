import io

def patch(path, pairs):
    s = io.open(path, encoding="utf-8", newline="").read()
    for old, new in pairs:
        assert s.count(old) == 1, (path, old[:60], s.count(old))
        s = s.replace(old, new)
    io.open(path, "w", encoding="utf-8", newline="").write(s)
    print("patched", path, len(pairs))

# ---- 登记册：Q-L01-09 + 计数 54/81/1 ----
patch("design/open_questions.md", [
    ("> **规模**：CONFIRMED 53 项；UNCONFIRMED 82 项（G 2 + L00 3 + L01 1 + L02–L13 76）；CLOSED 1 项（Q-L00-03，编号不复用）。",
     "> **规模**：CONFIRMED 54 项；UNCONFIRMED 81 项（G 2 + L00 3 + L01 1 + L02–L13 76）；CLOSED 1 项（Q-L00-03，编号不复用）。"),
    ("| Q-G00-08 | M0 三份 profile（m0_mw0 / m0_gateway / m0_interventions）初值集（世界力学/通道噪声与延迟/gateway deadline/干预 signature 参数——纯 profile 参数，不含认知参数） | **AI-v2：初值集成文采纳**（数值见三份 profile 文件，均标注\"初值\"）。定值原则：2 的幂对齐（与频率梯一致）、单看无行为意义仅作可复算锚点、全部带 M0 数据复核点。重开条件：M0 统计计划功效分析或首轮数据显示任一初值致盲区/饱和 → 经新 Q 重标定（改值 = profile 新版本） | 2026-09-25 |",
     """| Q-G00-08 | M0 三份 profile（m0_mw0 / m0_gateway / m0_interventions）初值集（世界力学/通道噪声与延迟/gateway deadline/干预 signature 参数——纯 profile 参数，不含认知参数） | **AI-v2：初值集成文采纳**（数值见三份 profile 文件，均标注"初值"）。定值原则：2 的幂对齐（与频率梯一致）、单看无行为意义仅作可复算锚点、全部带 M0 数据复核点。重开条件：M0 统计计划功效分析或首轮数据显示任一初值致盲区/饱和 → 经新 Q 重标定（改值 = profile 新版本） | 2026-09-25 |
| Q-L01-09 | MW0 动力学表补充参数与边界语义（REV-0004 R2/R3/R4/R6 补裁：冻结前钉死可操作性语义，防实现期无源常量） | **AI-v2：**① storm_rate_per_cycle = **全局语义**（每 grid 每 cycle 风暴命中期望次数；abundance/scarcity 0.005 → 约 1.3 次/256 驻留，volatile 0.030 → 约 7.7 次 ≈ 0.77 integrity 损耗/驻留）；② storm_band_drift = volatile 期每 64 cycles 沿随机方向漂移 1 格（dynamics 流）；③ resource_density = resource patch **目标覆盖率**（respawn 仅当覆盖率低于目标时进行，regime 切换即时生效）；④ 觅食链 = resource patch 上 forage → patch 储量 −1、储存食物 +1（非资源 patch effective=none）；eat 前置 = 储存 ≥1（消耗 1 → energy +0.15），储存上限 5；⑤ floor 语义 = energy/integrity 下限 0 截断，energy 首次触 0 记 energy_depleted 事件（Interoceptive），**M0 无死亡/重生/自然回复语义**（episode 终止仅经实验控制），integrity M0 无再生；⑥ load ≡ 0（load_max 为 schema 占位，carry 机制 C0+），观测噪声固定 σ 不随 load 调制（显式简化留痕，防静默降级）；⑦ 通道 loss_rate = 0.0（无自发丢失，丢失仅经 fault 干预注入）。全部为 M0 初值，M0 数据复核。重开条件：M0 显示觅食链/floor 语义产生非预期行为学（如能量枯竭支配一切行为）→ 经新 Q 重裁 | 2026-09-25 |"""),
])

# ---- L01：§4.3 blocked 措辞（R5）+ §11 两行（R1①、Q-L01-09 席位）----
patch("design/lld/L01_environment_channels.md", [
    ("| blocked | gateway 拒绝，ExecutionFact=拒绝 | 意图≠执行；拒绝类型化 |",
     "| blocked | gateway 拒绝；拒绝显形于 AuthorizationDecision(REJECTED) + ActionChainReceipt，命令不经 world.apply、无 ExecutionFact（m0_interventions 为权威源，2026-09-25 取齐） | 意图≠执行；拒绝类型化 |"),
    ("| Q-L01-08 | energy/integrity viability 阈值与损伤事件定义（联动 L05 驱力） | M0/L05 | UNCONFIRMED |",
     "| Q-L01-08 | energy/integrity viability 阈值与损伤事件定义（联动 L05 驱力） | M0/L05 | CONFIRMED（AI-v2 2026-09-25，M0 部分：损伤事件定义 + 力学初值；viability 阈值归 L05/C2，见 A 区） |\n| Q-L01-09 | MW0 动力学表补充参数与边界语义（风暴率语义/觅食链/floor/load 简化/loss） | M0 | CONFIRMED（AI-v2 2026-09-25：REV-0004 R2–R4/R6 补裁，见 A 区） |"),
])
print("PART1 OK")
