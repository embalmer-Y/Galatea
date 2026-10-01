"""recorder 故障即停（L13 §4.2/§7：heartbeat 前置断言 → claim-relevant 运行停止）。"""
from pathlib import Path

import pytest

from galatea.evidence.recorder.heartbeat import RecorderUnavailable, probe_recorder


def test_probe_passes_on_writable_dir(tmp_path: Path) -> None:
    probe_recorder(tmp_path / "run")          # 可创建/写/读/清 → 通过
    assert not (tmp_path / "run" / ".recorder_heartbeat").exists()   # 探针自清理


def test_probe_fails_on_unwritable_dir(tmp_path: Path) -> None:
    """目录不可写（路径被文件占用）→ RecorderUnavailable。"""
    blocker = tmp_path / "run"
    blocker.write_bytes(b"occupied")          # 同名文件存在 → mkdir 失败
    with pytest.raises(RecorderUnavailable):
        probe_recorder(blocker)


def test_probe_propagates_as_stop_not_silence(tmp_path: Path) -> None:
    """探测失败必须显式停机（禁静默继续）——异常类型可被运行编排捕获后中止。"""
    blocker = tmp_path / "blocked"
    blocker.write_bytes(b"x")
    stopped = False
    try:
        probe_recorder(blocker)
    except RecorderUnavailable:
        stopped = True
    assert stopped, "claim-relevant run must stop when recorder is unavailable"
