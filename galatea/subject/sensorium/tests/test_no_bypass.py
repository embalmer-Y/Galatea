"""raw-to-perception 旁路保护（L02 §7/§8/§10 test_no_bypass.py；权限测试）。

断言：非 RECEIVED 层级包拒绝；被排除载体（action_outcome）拒绝；import 图双检——
sensorium 不 import env 世界真值、知觉域不拿原始通道句柄（perception → raw channel
反向路径由 leakage P07 承载，此处检 sensorium 自身的旁路面）。
"""
from pathlib import Path

import pytest

from galatea.kernel.packet import RepresentationLevel
from galatea.subject.sensorium.ingest import ingest
from galatea.subject.sensorium.ports import (
    C0SensoriumProfile,
    SchemaViolation,
    load_c0_sensorium_profile,
)
from galatea.subject.sensorium.tests.conftest import extero_packet, make_packet, outcome_packet

_ROOT = Path(__file__).resolve().parents[4]
_PROFILE_PATH = _ROOT / "config" / "profiles" / "c0_sensorium.profile.yaml"


def _profile() -> C0SensoriumProfile:
    return load_c0_sensorium_profile(_PROFILE_PATH)


def test_non_received_level_rejected() -> None:
    """PERCEIVED/PREDICTED 层级包不是合法入口（唯一入口 = RECEIVED）。"""
    packet, text = make_packet(
        "channel.exteroceptive.received.v1", 0, {"kind": "observation_window", "window": [[0.5] * 5] * 5},
        level=RepresentationLevel.PERCEIVED,
    )
    with pytest.raises(SchemaViolation):
        ingest(packet, text, _profile())


def test_excluded_carrier_rejected() -> None:
    """action_outcome 归 L10 归属域（Q-G00-12①）——感觉形成拒绝。"""
    packet, text = outcome_packet(0)
    with pytest.raises(SchemaViolation, match="excluded"):
        ingest(packet, text, _profile())


def test_world_truth_object_rejected() -> None:
    """世界真值对象（非 RECEIVED 包）不可旁路进入形成（telemetry/直填面）。"""
    with pytest.raises((SchemaViolation, AttributeError, TypeError)):
        truth_like = {"kind": "world_state", "grid": [[0] * 16] * 16}
        packet, _text = extero_packet(0)
        ingest(packet, str(truth_like), _profile())   # 真值字符串当载荷 → schema 拒


def test_sensorium_import_graph_no_world_truth() -> None:
    """静态探针：sensorium 域不 import env 世界真值/通道对象（INC-08：探针可失败双面）。"""
    sensorium_dir = Path(__file__).resolve().parents[1]
    sources = {p.name: p.read_text(encoding="utf-8") for p in sensorium_dir.glob("*.py")}
    for name, text in sources.items():
        assert "from galatea.env" not in text, f"{name}: sensorium must not import env plane"
        assert "import galatea.env" not in text, f"{name}: sensorium must not import env plane"


def test_language_carrier_rejected_at_c0() -> None:
    """language 通道 C0 不在模态集（Q-G00-12① 四类）→ 拒绝。"""
    packet, text = make_packet("channel.language.received.v1", 0, {"kind": "typed_statement"})
    with pytest.raises(SchemaViolation):
        ingest(packet, text, _profile())
