"""桥确定性 + hwmon name 锚定 + 合同 payload 三键测试（探针形态的生产化回归）。"""
import json
from pathlib import Path

import pytest

from galatea.env.physio.bridge import PhysioBridge, _read_proc_stat
from galatea.env.physio.hwmon import HwmonResolutionError, HwmonResolver
from galatea.env.physio.ports import ProfileViolation, load_p1_physio_profile
from galatea.kernel.packet import RepresentationLevel

_PROFILE = load_p1_physio_profile()


def _make_hwmon_root(tmp_path: Path, name: str, temps: dict[str, int]) -> Path:
    base = tmp_path / f"hwmon_{name}"
    base.mkdir(parents=True)
    (base / "name").write_text(name, encoding="utf-8")
    for temp_name, value in temps.items():
        (base / f"{temp_name}_input").write_text(str(value), encoding="utf-8")
    return base


def test_busy_rate_frozen_formula_and_bit_exact_delivery(tmp_path: Path) -> None:
    hwmon_root = tmp_path / "sys"
    hwmon_root.mkdir()
    for name, temps in (("coretemp", {"temp1": 36000, "temp2": 30000}),
                        ("nvme", {"temp1": 41000}),
                        ("acpitz", {"temp1": 27800})):
        _make_hwmon_root(hwmon_root, name, temps)
    stat = tmp_path / "stat"
    (tmp_path / "loadavg").write_text("0.00 0.00 0.02 2/813 1\n", encoding="utf-8")
    (tmp_path / "meminfo").write_text("MemAvailable:  27123456 kB\n", encoding="utf-8")
    (tmp_path / "netdev").write_text(
        "Inter:   Received   Transmit\n  face |bytes    packets\n"
        "    lo: 1 1 0 0 0 0 0 0 1 1 0 0 0 0 0 0\n"
        "enp3s0: 5 4 0 0 0 0 0 0 6 5 0 0 0 0 0 0\n",
        encoding="utf-8",
    )
    # /proc/stat 是活快照（每次读单行）——测试在 cycle 间重写（行 = user nice system idle…）
    # 快照0: idle=1000 total=1000 → 1: idle=1950 total=2000（Δidle=950, Δtotal=1000）
    #       → 2: idle=2850 total=3000（Δidle=900, Δtotal=1000）
    snapshots = ["cpu  0 0 0 1000 0 0 0 0 0 0\n",
                 "cpu  50 0 0 1950 0 0 0 0 0 0\n",
                 "cpu  150 0 0 2850 0 0 0 0 0 0\n"]

    def build() -> tuple[list[str], list[float | None]]:
        stat.write_text(snapshots[0], encoding="utf-8")
        bridge = PhysioBridge(
            _PROFILE, resolver=HwmonResolver(hwmon_root),
            proc_stat_path=stat, loadavg_path=tmp_path / "loadavg",
            meminfo_path=tmp_path / "meminfo", netdev_path=tmp_path / "netdev",
            monotonic_fn=lambda: 1.5, epoch_fn=lambda: 1760000000.0,
            net_iface="enp3s0",
        )
        digests: list[str] = []
        busy_values: list[float | None] = []
        prev = None
        for cycle in range(3):
            record = bridge.sample(cycle)
            delivery = bridge.build_delivery(record, prev)
            payload = json.loads(delivery.payload_text)
            assert sorted(payload) == ["energy", "events", "integrity", "kind"]   # 合同三键+kind 判别（R5）
            assert payload["integrity"] == 1.0 and payload["events"] == []
            assert delivery.packet.representation_level is RepresentationLevel.RECEIVED
            digests.append(delivery.evidence_payload_digest)
            busy_values.append(delivery.busy_rate)
            prev = record
            if cycle < 2:
                stat.write_text(snapshots[cycle + 1], encoding="utf-8")
        return digests, busy_values

    digests1, busy1 = build()
    digests2, busy2 = build()
    assert digests1 == digests2                     # 同输入 bit-exact（记录-重放核心）
    assert busy1 == busy2
    assert busy1[0] is None                         # 首 cycle 无差分
    assert busy1[1] == 0.05                         # 1 − 950/1000（ADR §7 派生式手算锚）
    assert busy1[2] == 0.1                          # 1 − 900/1000


def test_hwmon_name_anchor_resolution_and_ambiguity(tmp_path: Path) -> None:
    _make_hwmon_root(tmp_path, "coretemp", {"temp1": 36000})
    resolver = HwmonResolver(tmp_path)
    assert resolver.resolve("coretemp") == tmp_path / "hwmon_coretemp"
    assert resolver.read_temps_millicelsius("coretemp") == {"temp1": 36000}
    with pytest.raises(HwmonResolutionError, match="not found"):
        resolver.resolve("nvme")
    amb_root = tmp_path / "amb"
    amb_root.mkdir()
    for dup in ("x", "y"):                          # 同级两目录、name 文件同内容
        dup_dir = amb_root / dup
        dup_dir.mkdir()
        (dup_dir / "name").write_text("coretemp", encoding="utf-8")
    with pytest.raises(HwmonResolutionError, match="ambiguous"):
        HwmonResolver(amb_root).resolve("coretemp")


def test_proc_stat_format_drift_fail_closed(tmp_path: Path) -> None:
    bad = tmp_path / "stat"
    bad.write_text("cpuX  1 2 3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="format drift"):
        _read_proc_stat(bad)


def test_profile_loader_fail_closed_missing_key(tmp_path: Path) -> None:
    import yaml

    raw = yaml.safe_load(Path("config/profiles/p1_physio.profile.yaml").read_text(encoding="utf-8"))
    del raw["sampling"]["period_ms"]
    broken = tmp_path / "broken.yaml"
    broken.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ProfileViolation, match="period_ms"):
        load_p1_physio_profile(broken)


def test_profile_contract_keys_must_be_mw0_trio(tmp_path: Path) -> None:
    import yaml

    raw = yaml.safe_load(Path("config/profiles/p1_physio.profile.yaml").read_text(encoding="utf-8"))
    raw["channel"]["field_semantics"]["thermal"] = "raw_temp"   # 污染合同成员
    broken = tmp_path / "broken.yaml"
    broken.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ProfileViolation, match="trio"):
        load_p1_physio_profile(broken)
