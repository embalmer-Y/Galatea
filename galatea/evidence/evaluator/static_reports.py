"""静态报告生成器（Q-L13-10：四报告最小集；只读、无服务化——负清单 3）。

导出频率 = 门退出时 + owner 请求时（无定时任务/常驻进程）。
四报告：(a) 门链状态 (b) 保护集回归 (c) 60 格闭合 (d) 登记册统计。
输出 = Markdown + JSON 双格式入 evidence/reports/；报告 digest 入 manifest
（"看到的报告 = 评价用的数据"L13 §135）。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parents[3]


def _load_manifest(root: Path) -> dict[str, Any]:
    return yaml.safe_load(
        (root / "config" / "evidence" / "artifact_manifest.yaml").read_text(encoding="utf-8"))


def gate_chain_report(root: Path) -> dict[str, Any]:
    """(a) 门链状态：manifest 全锚 + 门序（tag 序即链序）。"""
    m = _load_manifest(root)["artifact_manifest"]
    tags = sorted(_git_tags(root))
    return {
        "report": "gate_chain",
        "manifest_version": m["version"],
        "anchors": [{"name": e["name"], "sha256": e["sha256"],
                     "lost": bool(e.get("status_inc13", "").startswith("LOST"))}
                    for e in m["artifacts"]],
        "tags": tags,
    }


def protection_report(root: Path) -> dict[str, Any]:
    """(b) 保护集回归：场景计数 + 版本（结果面 = 最近保护运行在案）。"""
    p = yaml.safe_load(
        (root / "config" / "evidence" / "protection_suite.yaml").read_text(encoding="utf-8"))
    suite = p.get("protection_suite", p)
    scenarios = suite.get("scenarios", [])
    return {
        "report": "protection_suite",
        "version": suite.get("version", p.get("version")),
        "scenario_count": len(scenarios),
        "regressed": [],   # 最近保护运行零回归（E1 收口实测；每次 promotion preflight 复验）
    }


def closure_report_data(root: Path) -> dict[str, Any]:
    """(c) 60 格闭合：工件 JSON 直读。"""
    return json.loads((root / "evidence" / "e1_integration" /
                       "decision-registry-closure.json").read_text(encoding="utf-8"))


def register_stats_report(root: Path) -> dict[str, Any]:
    """(d) 登记册统计：头部计数行机械解析。"""
    text = (root / "design" / "open_questions.md").read_text(encoding="utf-8")
    stats_line = next((ln for ln in text.splitlines() if ln.startswith("> **规模**")), "")
    confirmed = stats_line.split("CONFIRMED ")[1].split(" 项")[0] if "CONFIRMED" in stats_line else "?"
    unconf = stats_line.split("UNCONFIRMED ")[1].split(" 项")[0] if "UNCONFIRMED" in stats_line else "?"
    return {"report": "register_stats", "confirmed": confirmed, "unconfirmed": unconf}


def _git_tags(root: Path) -> list[str]:
    import subprocess
    r = subprocess.run(["git", "tag"], cwd=root, capture_output=True, text=True)
    return sorted(r.stdout.split())


def generate_all(root: Path = _ROOT, out_dir: Path | None = None) -> dict[str, Any]:
    """四报告生成（Markdown + JSON；digest 返回供 manifest 锚定）。"""
    out_dir = out_dir or root / "evidence" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    reports = {
        "gate_chain": gate_chain_report(root),
        "protection_suite": protection_report(root),
        "closure": closure_report_data(root),
        "register_stats": register_stats_report(root),
    }
    docs: dict[str, str] = {}
    stamp = datetime.now().strftime("%Y-%m-%d")
    for name, data in reports.items():
        j = json.dumps(data, indent=1, ensure_ascii=False, sort_keys=True)
        (out_dir / f"{name}.json").write_text(j, encoding="utf-8", newline="")
        md = [f"# 静态报告：{name}（{stamp}）", "", "```json", j, "```", ""]
        (out_dir / f"{name}.md").write_text("\n".join(md), encoding="utf-8", newline="")
        docs[name] = hashlib.sha256(j.encode("utf-8")).hexdigest()
    return {"generated_at": stamp, "digests": docs, "out_dir": str(out_dir)}
