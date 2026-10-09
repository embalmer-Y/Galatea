"""静态报告生成器测试（Q-L13-10：四报告最小集 + 只读无服务化 + digest 可复算）。"""
import json

from galatea.evidence.evaluator.static_reports import generate_all

from pathlib import Path as _P

_ROOT = _P(__file__).resolve().parents[2]


def test_four_reports_generated_with_stable_digests(tmp_path) -> None:
    out = generate_all(_ROOT, tmp_path)
    assert set(out["digests"]) == {"gate_chain", "protection_suite", "closure", "register_stats"}
    # digest 可复算（同输入同 digest——报告 = 数据的确定性投影）
    out2 = generate_all(_ROOT, tmp_path)
    assert out2["digests"] == out["digests"]
    # 双格式落盘
    for name in out["digests"]:
        assert (tmp_path / f"{name}.json").is_file()
        assert (tmp_path / f"{name}.md").is_file()
    # JSON 文件内容 = digest 源
    j = json.loads((tmp_path / "register_stats.json").read_text(encoding="utf-8"))
    assert j["report"] == "register_stats"
