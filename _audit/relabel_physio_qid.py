"""_audit/relabel_physio_qid.py — Q-ID-01…06 physio 标签分域改标（一次性，2026-09-17 owner 裁决执行 = DEV_SPEC ACT-03）

裁决内容（见 DEV_SPEC §13 / physio 各文档）：
  Q-ID-01  D1/D2/D3        → DYN-1/DYN-2/DYN-3      （动态编程三层，避让裁决域 D-10…14 与历史验收 D1–D7）
  Q-ID-02  L1…L5           → COM-L1…COM-L5          （通信五层，避让 LLD 档号 L01–L05）
  Q-ID-03  M0…M5           → PIO-M0…PIO-M5          （physio 里程碑，避让门体系 M0–M2；V2 不变）
  Q-ID-04  S1…S12          → SP-1…SP-12             （spike 必测项，避让缺陷等级 S0–S4）
  Q-ID-05  N2-a/b/c        → NL2-a/b/c              （负清单第 2 条变体，避让频率参数 N2）
  Q-ID-06  ADR-000n        → ADR-PIO-000n           （分域前缀；含草案引用的 ADR-0003/0004；根文件同步）

纪律：
  - 纯标签替换，不改任何实质内容（physio owner-review 冻结区的选项/论证原样保留）；
  - 显式 UTF-8 编解码、newline='' 字节级保真（行尾不变）——承 DEV_SPEC §8.1 / HLD 附录 A.6 教训；
  - 幂等（lookbehind 阻止对已改标结果的二次命中），可重复运行；
  - 逐文件逐规则打印计数，作为审计证据。
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PHYSIO = ROOT / "physio"

RULES_PHYSIO = [
    ("Q-ID-01 D[123]->DYN-n",      re.compile(r"(?<!DYN-)\bD([123])\b"),                r"DYN-\1"),
    ("Q-ID-02 L[1-5]->COM-Ln",     re.compile(r"(?<!COM-)\bL([1-5])\b"),                r"COM-L\1"),
    ("Q-ID-03 M[0-5]->PIO-Mn",     re.compile(r"(?<!PIO-)\bM([0-5])\b"),                r"PIO-M\1"),
    ("Q-ID-04 S[1-12]->SP-n",      re.compile(r"(?<!SP-)\bS([1-9]|1[0-2])\b"),          r"SP-\1"),
    ("Q-ID-05 N2-[abc]->NL2-x",    re.compile(r"\bN2-([abc])\b"),                       r"NL2-\1"),
    ("Q-ID-06 ADR-000n->ADR-PIO",  re.compile(r"(?<!ADR-PIO-)ADR-(\d{4})"),             r"ADR-PIO-\1"),
]

RULE_ADR_ONLY = [RULES_PHYSIO[-1]]
ROOT_FILES = [ROOT / "DEV_SPEC.md", ROOT / "AGENTS.md", ROOT / "_audit" / "incidents.md"]


def collect_physio_files() -> list[Path]:
    files: set[Path] = set()
    for pattern in ("**/*.md", "**/*.yml", "**/*.yaml"):
        for p in PHYSIO.glob(pattern):
            if p.is_file():
                files.add(p)
    return sorted(files)


def apply(path: Path, rules) -> list[tuple[str, int]]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    out = src
    counts = []
    for name, rx, rep in rules:
        out, n = rx.subn(rep, out)
        counts.append((name, n))
    if out != src:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(out)
    return counts


def main() -> int:
    total = 0
    print("== physio/ 全量 ==")
    for p in collect_physio_files():
        counts = apply(p, RULES_PHYSIO)
        hit = [(n, c) for n, c in counts if c]
        if hit:
            print(f"{p.relative_to(ROOT)}: " + ", ".join(f"{n}×{c}" for n, c in hit))
            total += sum(c for _, c in hit)
    print("== 根文件（仅 ADR 规则）==")
    for p in ROOT_FILES:
        counts = apply(p, RULE_ADR_ONLY)
        hit = [(n, c) for n, c in counts if c]
        if hit:
            print(f"{p.relative_to(ROOT)}: " + ", ".join(f"{n}×{c}" for n, c in hit))
            total += sum(c for _, c in hit)
    print(f"TOTAL replacements: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
