"""LeakageProbe：payload 不可见性（L00 §7——调度决策与 payload 互信息=0）。"""
from pathlib import Path

from galatea.kernel.tests.test_replay import run_world

SCHEDULER_SRC = (
    (Path(__file__).resolve().parents[1] / "scheduler.py").read_text(encoding="utf-8")
)


def test_payload_mutation_does_not_change_scheduling(tmp_path: Path) -> None:
    """payload 内容分歧（不同 blob）→ envelope digest 分歧，但调度序/拓扑/事件 id 全同。"""
    a = run_world(b"seed-A", tmp_path / "a", payload_byte=-1)   # payload 来自流
    b = run_world(b"seed-A", tmp_path / "b", payload_byte=0x5A)  # payload 恒定字节
    # 调度序（cycle, module）与事件 id 序列 bit-exact：
    assert [(c, m) for c, m, _ in a.id_log] == [(c, m) for c, m, _ in b.id_log]
    assert [ids for _, _, ids in a.id_log] == [ids for _, _, ids in b.id_log]
    assert len(a.out_digests) == len(b.out_digests)
    # 而 envelope digest 确实因 payload_ref 不同而分歧（证明两世界 payload 已分叉）：
    assert a.out_digests != b.out_digests
    assert a.registry_digest != b.registry_digest


def test_scheduler_static_never_touches_registry() -> None:
    """静态探针：调度器不 import registry（payload 只经目标模块自取）。"""
    assert "kernel.registry" not in SCHEDULER_SRC
    assert "registry.get" not in SCHEDULER_SRC
    assert "Registry" not in SCHEDULER_SRC.replace("Registration", "")
