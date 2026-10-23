"""E1 integration 工件重建器（INC-16 恢复单元交付）。

历史背景：I2-c5-gain-001.json 与 decision-registry-closure.json 的原始写入者
系 E1 收尾会话临时脚本（出库未入库——INC-16 如实登记的缺陷面）。本模块将其
重建逻辑永久入库：全部输入取自在库工件（c5 评价分区 / i2_independent /
decision_registry_data），重建为确定性纯函数——双跑逐字节相同由
tests/evidence/test_e1_integration_rebuild.py 钉死。

重建语义（INC-16 披露）：统计值与历史锚定工件恒等（d=2.031346147382602、
n_domain_trials=43、coverage 60/60、gate CLOSED）；JSON 字节与历史件不可比
（原格式不可考）——manifest 对应锚随本单元重锚 + 状态注记。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[3]

_I2_REPORT = "I2-c5-gain-001.json"
_CLOSURE_REPORT = "decision-registry-closure.json"


def rebuild_i2_report(root: Path = _ROOT) -> dict[str, Any]:
    """I2 独立复算报告（同数据 Wald 配对独立统计 + 结构面 attestation）。"""
    from galatea.evidence.evaluator.i2_independent import i2_recompute_c5_gain

    out = i2_recompute_c5_gain(
        root / "evidence/c5_continued_learning_first_evaluation/run/registry",
        root / "evidence/c5_continued_learning_first_evaluation/R-c5-gain-001.json",
        root / "config/evidence/stat_plans/c5_continued_learning.yaml")
    return {
        "report": "I2-c5-gain-001",
        "mode": "I2",
        "n_domain_trials": out["n_domain_trials"],
        "independent": out["independent"],
        "original": out["original"],
        "verdict_ok": out["verdict_ok"],
        "d_ok": out["d_ok"],
        "p_ok": out["p_ok"],
        "mean_in_ci": out["mean_in_ci"],
        "match": out["match"],
        "inputs_digest": out["inputs_digest"],
        "independence": "source-zero-import structural face（Q-L13-08①）"
                        "+ 同数据 Wald 配对独立统计",
    }


def rebuild_closure_report(root: Path = _ROOT) -> dict[str, Any]:
    """60 格闭合报告（coverage/unresolved/denominator_closed + 门语义 + report digest）。"""
    from galatea.evidence.decision_registry_data import e1_closure_report

    report, gate = e1_closure_report()
    return {
        "coverage_filled": report.coverage_filled,
        "denominator": report.denominator,
        "unresolved_paths": list(report.unresolved_paths),
        "denominator_closed": report.denominator_closed,
        "gate": gate.value,
        "report_digest": report.digest(),
    }


def rebuild_all(out_dir: Path | None = None,
                root: Path = _ROOT) -> dict[str, str]:
    """两件工件落盘（indent=1 + sort_keys 规范化；返回 {文件名: 字节 sha256}）。"""
    import hashlib

    out_dir = out_dir or root / "evidence" / "e1_integration"
    out_dir.mkdir(parents=True, exist_ok=True)
    payloads = {
        _I2_REPORT: rebuild_i2_report(root),
        _CLOSURE_REPORT: rebuild_closure_report(root),
    }
    digests: dict[str, str] = {}
    for name, data in payloads.items():
        blob = json.dumps(data, indent=1, ensure_ascii=False, sort_keys=True)
        (out_dir / name).write_text(blob, encoding="utf-8", newline="")
        digests[name] = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    return digests


def main() -> int:
    digests = rebuild_all()
    for name, digest in sorted(digests.items()):
        print(f"rebuilt: evidence/e1_integration/{name} sha256={digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
