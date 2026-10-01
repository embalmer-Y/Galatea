"""recorder 可用性探测（L13 §4.2/§10 recorder/heartbeat.py）。

纪律：recorder 故障即停——claim-relevant 运行前置断言探测失败 = RecorderUnavailable
（S1，停止运行而非静默继续，HLD §5.1）。探测 = 探针文件写/读/删全链路。
"""
from pathlib import Path

__all__ = ["RecorderUnavailable", "probe_recorder"]

_PROBE_NAME = ".recorder_heartbeat"


class RecorderUnavailable(RuntimeError):
    """recorder 不可用仍启动 claim-relevant 运行（L13 §6：S1，强制停止）。"""


def probe_recorder(run_dir: Path) -> None:
    """运行前置探测：run 目录可创建、可写、可读、可清理；任一失败 → RecorderUnavailable。"""
    probe = run_dir / _PROBE_NAME
    try:
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_bytes(b"hb")
        if probe.read_bytes() != b"hb":
            raise OSError("heartbeat readback mismatch")
        probe.unlink()
    except OSError as exc:
        raise RecorderUnavailable(
            f"recorder unavailable at {run_dir}: {exc}——claim-relevant 运行必须停止（L13 §4.2）"
        ) from exc
