"""P4-α 探针报告生成器回归（REV-0027 R5：生成器并入训练会话录制器——正式 runner 面）。

重算规格 = ADR-G-0030 §2（种子/脚本/窗口/超参/digest 式全成文）。
判据全部可失败：训练损失下降 / held-out 比 < 冻结阈 0.1 / 部署双跑 bit-exact /
录制重放末权重逐位恒等 / 消融偏移可检出 / 流 digest 锚命中（Q-G00-15②）。

诚实注记（跨机漂移实证，2026-10-11 主机迁移后首跑）：流 digest 与 profile 锚
逐位恒等（MW0+sensorium 纯 Python 管线跨机确定）；torch 训练尾值在末 6–7 位
有效数字随 CPU 内核选择漂移（同机双跑 bit-exact 不受影响——Q-L13-20③ 合同
语义 = 同部署双跑，非跨机逐位）。归档 evidence/p4_alpha_probe/probe_report.json
= 冻结时点开发机工件（manifest v1.29 锚），本测试不断言与其字节恒等。
"""
from __future__ import annotations

import json
from pathlib import Path

from galatea.evidence.control.probe_report import (
    generate_probe_report,
    verify_probe_stream_anchor,
)
from galatea.subject.p4profile import load_p4_alpha_profile

_ROOT = Path(__file__).resolve().parents[2]
_PARAMS = load_p4_alpha_profile(_ROOT / "config" / "profiles" / "p4_alpha_brain.profile.yaml")


def test_probe_stream_anchor_hit() -> None:
    """流 digest 锚命中（数据身份锚跨会话/跨机恒定——Q-G00-15②）。"""
    assert verify_probe_stream_anchor(_PARAMS) is True


def test_probe_report_all_gates_pass(tmp_path: Path) -> None:
    """报告生成全判据（PASS 仅当损失下降 + ratio<0.1 + 双跑 + 重放 + 消融偏移）。"""
    report = generate_probe_report(_PARAMS, tmp_path / "probe_report.json")
    assert report["verdict"] == "PASS"
    assert report["stream_digest"] == _PARAMS.probe_stream_digest
    ratio = float(report["ratio"])  # type: ignore[arg-type]
    assert ratio < _PARAMS.heldout_margin_vs_persistence, f"ratio={ratio}"
    assert float(report["loss_last"]) < float(report["loss_first"])  # type: ignore[arg-type]
    assert report["weights_after"] != report["weights_before"]       # type: ignore[arg-type]
    written = json.loads((tmp_path / "probe_report.json").read_text(encoding="utf-8"))
    assert written == report
