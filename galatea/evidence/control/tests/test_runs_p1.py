"""runs_p1 runner 回归测试（INC-08/REV-0014 R1：runner 路径必须有端到端覆盖）。

合成 mini 语料（tmp_path 注入 hwmon 假根）走全臂——不依赖 evidence/（gitignored，
fresh clone 必缺）。含首评实现错位教训的回归锚：signal 配对必须按 effective_time。
"""
import json
from pathlib import Path

from galatea.env.physio.bridge import PhysioBridge, TelemetryRecord
from galatea.env.physio.ports import load_p1_physio_profile
from galatea.evidence.control.runs_p1 import (
    SealedCorpus,
    run_fidelity,
    run_safety,
    run_signal_carriage,
)

_PROFILE = load_p1_physio_profile()


def _synthetic_corpus(tmp_path: Path, cycles: int = 12) -> SealedCorpus:
    """busy 值摆动的确定性合成语料（剂量-响应可检出——非平坦）。"""
    hwmon = tmp_path / "sys"
    hwmon.mkdir()
    for name in ("coretemp", "nvme", "acpitz_0"):
        base = hwmon / f"hwmon_{name}"
        base.mkdir()
        (base / "name").write_text(name, encoding="utf-8")
        (base / "temp1_input").write_text("36000", encoding="utf-8")
    (tmp_path / "loadavg").write_text("0.1 0.1 0.1 1/2 3\n", encoding="utf-8")
    (tmp_path / "meminfo").write_text("MemAvailable:  1000 kB\n", encoding="utf-8")
    (tmp_path / "netdev").write_text(
        "Inter:\n  face |bytes packets\nlo: 1 1 0 0 0 0 0 0 1 1 0 0 0 0 0 0\n"
        "enp3s0: 1 1 0 0 0 0 0 0 1 1 0 0 0 0 0 0\n", encoding="utf-8")
    busy_pattern = [0.0, 0.05, 0.1, 0.05, 0.0, 0.2, 0.3, 0.2, 0.1, 0.05, 0.0, 0.15]
    bridge = PhysioBridge(_PROFILE, resolver=_FakeResolver(hwmon),
                          proc_stat_path=tmp_path / "stat",
                          loadavg_path=tmp_path / "loadavg",
                          meminfo_path=tmp_path / "meminfo",
                          netdev_path=tmp_path / "netdev",
                          monotonic_fn=lambda: 0.5, epoch_fn=lambda: 100.0)
    records: list[TelemetryRecord] = []
    busies: list[float | None] = []
    digests: list[str] = []
    prev_record = None
    prev_busy: float | None = None
    for cycle in range(cycles):
        busy = busy_pattern[cycle % len(busy_pattern)]
        # busy=0.05 → idle 增量比例冻结：total 每拍 +1000，idle 增 = 1000×(1−busy)
        (tmp_path / "stat").write_text(
            f"cpu  {int(1000 * busy)} 0 0 {1000 * (cycle + 1) - int(1000 * busy)} 0 0 0 0 0 0\n",
            encoding="utf-8")
        record = bridge.sample(cycle)
        delivery = bridge.build_delivery(record, prev_record)
        records.append(record)
        busies.append(delivery.busy_rate)
        digests.append(delivery.evidence_payload_digest)
        prev_record = record
        prev_busy = busy
    header = {"records": cycles, "stream_sha256": "0" * 64}
    return SealedCorpus(header=header, records=tuple(records), busy_rates=tuple(busies),
                        payload_digests=tuple(digests), stream_sha256_verified=False)


class _FakeResolver:
    """零 /sys 依赖的假解析器（bridge 仅需 read_temps_millicelsius）。"""

    def __init__(self, root: Path) -> None:
        self._root = root

    def read_temps_millicelsius(self, name: str) -> dict[str, int]:
        return {"temp1": 36000}


def test_fidelity_arm_end_to_end(tmp_path: Path) -> None:
    corpus = _synthetic_corpus(tmp_path)
    short = run_fidelity(corpus, _PROFILE)
    assert short["corpus_verified"] is False                  # digest 短路分支（REV-0026 R8）
    assert short["replay_bit_exact"] is False
    # 用 verified 语料重走：
    corpus_true = SealedCorpus(header=corpus.header, records=corpus.records,
                               busy_rates=corpus.busy_rates,
                               payload_digests=corpus.payload_digests,
                               stream_sha256_verified=True)
    result = run_fidelity(corpus_true, _PROFILE)
    assert result["corpus_verified"] is True
    assert result["derive_recompute_ok"] is True
    assert result["replay_bit_exact"] is True
    w_align = 4
    n = len(corpus.records)
    due = n - w_align
    assert result["due_windows"] == due
    assert result["due_window_formation_rate"] == 1.0
    assert result["channel_source_invariance"] is True


def test_safety_arm_all_scenarios() -> None:
    result = run_safety()
    assert result["all_passed"] is True
    assert result["scenario_count"] == 8
    assert all(s["passed"] for s in result["scenarios"])


def test_signal_arm_saturated_for_synthetic_swing(tmp_path: Path) -> None:
    """合成 busy 摆动 → energy_rate = −Δbusy 恒等派生 → r 应饱和（配对按 effective_time）。"""
    corpus = _synthetic_corpus(tmp_path)
    result = run_signal_carriage(corpus, _PROFILE)
    assert result["verdict_inputs_complete"] is True
    assert result["n_windows"] >= 3
    assert result["pearson_r"] == 1.0            # 首版投递序错位回归锚（r 会掉到 ≈0）
