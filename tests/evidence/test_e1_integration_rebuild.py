"""E1 integration 重建器测试（INC-16 恢复单元——重建确定性 + 判据值钉死）。"""
import hashlib
import json
from pathlib import Path

from galatea.evidence.control.e1_integration_rebuild import (
    rebuild_all,
    rebuild_closure_report,
    rebuild_i2_report,
)

_ROOT = Path(__file__).resolve().parents[2]


def test_i2_rebuild_matches_original() -> None:
    """行为面：重建 I2 报告 match=True 且判据值与历史锚定值逐位恒等。"""
    out = rebuild_i2_report(_ROOT)
    assert out["match"] is True
    assert out["n_domain_trials"] == 43
    assert out["independent"]["d"] == 2.031346147382602   # 历史 d 逐位（manifest/REV-0023 记录）
    assert out["independent"]["p"] == 0.0
    assert {"match", "n_domain_trials", "independent"} <= set(out)


def test_closure_rebuild_closed() -> None:
    """60 格闭合：coverage 60/60 + unresolved 空 + gate CLOSED + report digest 在位。"""
    out = rebuild_closure_report(_ROOT)
    assert out["gate"] == "CLOSED"
    assert out["coverage_filled"] == 60
    assert out["denominator"] == 60
    assert out["unresolved_paths"] == []
    assert out["denominator_closed"] is True
    assert isinstance(out["report_digest"], str) and len(out["report_digest"]) == 64


def test_rebuild_double_run_byte_identical(tmp_path: Path) -> None:
    """确定性：双跑落盘逐字节相同（sort_keys 规范化 + 纯函数输入全在库）。"""
    d1 = rebuild_all(out_dir=tmp_path / "a", root=_ROOT)
    d2 = rebuild_all(out_dir=tmp_path / "b", root=_ROOT)
    assert d1 == d2
    for name in d1:
        blob_a = (tmp_path / "a" / name).read_bytes()
        blob_b = (tmp_path / "b" / name).read_bytes()
        assert blob_a == blob_b
        assert hashlib.sha256(blob_a).hexdigest() == d1[name]
        json.loads(blob_a)   # 合法 JSON（e1_closure_entry/static_reports 读方面）
