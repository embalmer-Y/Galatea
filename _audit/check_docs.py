"""Read-only corpus validator for design/*.md (strict UTF-8, Q-number closure,
cross-references, terminology drift). Writes a UTF-8 report; never mutates corpus.

Usage: python _audit/check_docs.py
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "design"
OUT = Path(__file__).resolve().parent / "report.md"

STRICT = "utf-8"
BOM = "\ufeff"
FFFD = "\ufffd"

Q_DECL_RE = re.compile(r"^\|\s*~{0,2}(Q-[A-Z0-9]+(?:-\d+)?)~{0,2}\s*\|", re.M)
# 允许尾随字母后缀，以捕获悬空引用如 Q-T08b / Q-T04b（登记册不存在后缀形式）
Q_TOKEN_RE = re.compile(r"Q-(?:[TCN]\d+[a-z]?|G00-\d+[a-z]?|L\d\d-\d+[a-z]?)")
SIX_LAYER_RE = re.compile(r"(?<![A-Za-z])S[56](?![A-Za-z0-9])|S1–S6|S1-S6")


def files() -> list[Path]:
    return sorted(p for p in ROOT.rglob("*.md"))


def main() -> None:
    lines: list[str] = []
    add = lines.append
    add("# 文档机器校验报告（只读）")
    add("")
    add(f"根目录：`{ROOT}`")
    add("")

    all_files = files()
    add(f"扫描 `.md` 文件数：**{len(all_files)}**")
    add("")

    # ---- 1. encoding ----
    add("## 1. 严格 UTF-8 解码")
    add("")
    enc_fail = []
    texts: dict[Path, str] = {}
    for p in all_files:
        raw = p.read_bytes()
        try:
            t = raw.decode(STRICT, errors="strict")
        except UnicodeDecodeError as e:  # noqa: PERF203
            enc_fail.append((p, str(e)))
            continue
        texts[p] = t
        notes = []
        if t.startswith(BOM):
            notes.append("**BOM**")
        if FFFD in t:
            notes.append(f"**U+FFFD x{t.count(FFFD)}**")
        if "?" * 3 in t:
            notes.append("suspicious ??? run")
        if notes:
            enc_fail.append((p, "; ".join(notes)))
    if enc_fail:
        for p, msg in enc_fail:
            add(f"- FAIL `{p.relative_to(ROOT)}`: {msg}")
    else:
        add(f"- OK：{len(texts)}/{len(all_files)} 全部严格 UTF-8 解码通过，无 BOM、无 U+FFFD")
    add("")

    # ---- 2. Q closure ----
    add("## 2. Q 编号闭合（声明 vs 引用）")
    add("")
    declared: dict[str, str] = {}
    dup_decl: list[str] = []
    oq = ROOT / "open_questions.md"
    uses: dict[str, Counter[str]] = defaultdict(Counter)
    status: Counter[str] = Counter()
    section = "?"
    for t_line in texts[oq].splitlines():
        if t_line.startswith("## "):
            section = t_line[3:].split(".")[0].strip()
        m = Q_DECL_RE.match(t_line)
        if not m:
            continue
        q = m.group(1)
        if q in declared:
            dup_decl.append(q)
        declared[q] = section
        # A 区 = 已裁决存档；行内显式 CLOSED 优先；其余 UNCONFIRMED
        if "**CLOSED**" in t_line or "~~" in t_line:
            status["CLOSED"] += 1
        elif section == "A":
            status["CONFIRMED"] += 1
        else:
            status["UNCONFIRMED"] += 1
    for p, t in texts.items():
        rel = p.relative_to(ROOT).as_posix()
        for q in set(Q_TOKEN_RE.findall(t)):
            uses[q][rel] += 1

    add(f"- 登记册声明 Q 号：**{len(declared)}**")
    for k in ("CONFIRMED", "UNCONFIRMED", "CLOSED"):
        add(f"  - {k}: {status[k]}")
    add(f"  - 分区分佈：{dict(Counter(declared.values()))}")
    add("")
    if dup_decl:
        add(f"- FAIL 重复声明：{sorted(set(dup_decl))}")
    else:
        add("- OK：无重复声明")

    undeclared = sorted(q for q in uses if q not in declared)
    add("")
    if undeclared:
        add(f"- **WARNING 被引用但登记册未声明（{len(undeclared)}）**：")
        for q in undeclared:
            add(f"  - `{q}` → {', '.join(sorted(uses[q]))}")
    else:
        add("- OK：所有被引用的 Q 号均在登记册声明")

    unused = sorted(q for q in declared if q not in uses or len(uses[q]) == 1)
    add("")
    add(f"- 仅在登记册出现（未被任何 LLD/HLD 引用）的 Q 号数：{len([q for q in declared if q not in uses])}")
    orphan = [q for q in declared if q not in uses]
    if orphan:
        add(f"  - {', '.join(orphan)}")
    add("")

    # per-file declared ranges
    add("### 各 LLD 自声明 Q 号数（§11 表）")
    add("")
    for p, t in sorted(texts.items()):
        rel = p.relative_to(ROOT).as_posix()
        if not rel.startswith("lld/"):
            continue
        ids = sorted({m.group(1) for m in Q_DECL_RE.finditer(t)})
        add(f"- `{rel}`: {len(ids)} → {', '.join(ids) if ids else '（无）'}")
    add("")

    # ---- 3. cross-file references ----
    add("## 3. 交叉引用：被引用的 LLD 文件名是否存在")
    add("")
    existing = {p.name for p in all_files}
    ref_re = re.compile(r"`?(L\d\d_[A-Za-z0-9_]+\.md)`?")
    missing_refs: dict[str, set[str]] = defaultdict(set)
    for p, t in texts.items():
        for m in ref_re.finditer(t):
            name = m.group(1)
            if name not in existing:
                missing_refs[name].add(p.relative_to(ROOT).as_posix())
    if missing_refs:
        for name, srcs in sorted(missing_refs.items()):
            add(f"- FAIL `{name}` 不存在，被引用于：{', '.join(sorted(srcs))}")
    else:
        add("- OK：所有 `Lxx_*.md` 引用均指向存在文件")
    add("")
    # lld/ wildcard references
    wild = [(p.relative_to(ROOT).as_posix(), m) for p, t in texts.items() for m in re.findall(r"lld/L\d\d_\*|L02_\* … L13_\*", t)]
    add(f"- 残留通配符引用（`L02_* … L13_*`）：{len(wild)}" + ("" if not wild else f" → {wild}"))
    add("")

    # ---- 4. terminology drift ----
    add("## 4. 术语漂移")
    add("")
    helios = [(p.relative_to(ROOT).as_posix(), t.count("Helios")) for p, t in texts.items() if "Helios" in t]
    add(f"- 含 `Helios` 的文件（应仅作曾用名注记）：{helios if helios else '无'}")
    hio_re = re.compile(r"(?<![A-Za-z])HIO(?![A-Za-z])")
    hio_files = defaultdict(int)
    ctx_bad = []
    for p, t in texts.items():
        rel = p.relative_to(ROOT).as_posix()
        for m in hio_re.finditer(t):
            hio_files[rel] += 1
            lo = max(0, m.start() - 60)
            ctx = t[lo:m.end() + 60].replace("\n", " ")
            if not any(k in ctx for k in ("曾用名", "更名", "已废弃", "Helios I/O", "PhysIO")):
                ctx_bad.append((rel, ctx))
    add(f"- 独立 `HIO` 令牌计数：{sum(hio_files.values())}（{dict(hio_files)}）")
    if ctx_bad:
        add(f"- **FAIL 非注记语境的 HIO（{len(ctx_bad)}）**：")
        for rel, ctx in ctx_bad:
            add(f"  - `{rel}`: …{ctx}…")
    else:
        add("- OK：全部位于曾用名/更名注记语境")
    s16 = [(p.relative_to(ROOT).as_posix(), len(SIX_LAYER_RE.findall(t))) for p, t in texts.items()]
    s16 = [(r, n) for r, n in s16 if n]
    add(f"- 旧六层叙事残留（`S5`/`S6`/`S1–S6`；已排除缺陷等级 S0–S4 与切片 MW0-SCx）：{s16}")
    eight = [(p.relative_to(ROOT).as_posix(), re.findall(r"[8八]\s*层[测金]?[试塔字]*金字塔|金字塔[^。\n]{0,12}[8八]\s*层", t)) for p, t in texts.items()]
    eight = [(r, n) for r, n in eight if n]
    add(f"- “8 层金字塔”残留：{eight if eight else '无'}")
    add("")

    # ---- 5. LLD structural conformance ----
    add("## 5. LLD 11 节模板符合度")
    add("")
    need = [
        "目标与范围", "Ports", "状态所有权与单写者", "算法与数据结构", "时间尺度",
        "失败模式", "可测性", "不变量", "引入门槛", "实现清单", "未决问题",
    ]
    for p, t in sorted(texts.items()):
        rel = p.relative_to(ROOT).as_posix()
        if not rel.startswith("lld/"):
            continue
        missing = [k for k in need if k not in t]
        head = t.splitlines()[0] if t else ""
        verdict = "OK" if not missing else f"缺节: {missing}"
        add(f"- `{rel}`: {len(t.splitlines())} 行 · 标题「{head[:60]}」 · {verdict}")
    add("")

    # ---- 6. header convention ----
    add("## 6. LLD 头部规范（版本/日期/状态/上游/下游/门槛）")
    add("")
    for p, t in sorted(texts.items()):
        rel = p.relative_to(ROOT).as_posix()
        if not rel.startswith("lld/"):
            continue
        head = "\n".join(t.splitlines()[:6])
        keys = ["LLD:", "v1.0", "2026-09-", "状态：", "上游", "下游", "引入门槛"]
        miss = [k for k in keys if k not in head]
        add(f"- `{rel}`: {'OK' if not miss else '缺 ' + ','.join(miss)}")
    add("")

    OUT.write_text("\n".join(lines), encoding=STRICT, newline="\n")
    print(f"report written: {OUT}")


if __name__ == "__main__":
    main()
