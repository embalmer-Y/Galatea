"""Tessera 桥测试（Q-L10-16；确定性解码/映射/合同包——不需要 zenoh/网络）。"""
import cbor2
import pytest

from galatea.env.tessera_bridge import (
    map_suffix_to_carrier,
    parse_topic,
    sample_from_wire,
)


def _wire(obj: dict) -> bytes:
    return cbor2.dumps(obj)


def test_parse_topic_and_mapping() -> None:
    assert parse_topic("tessera/dav/dvc/sys/power") == ("dav", "dvc", "sys/power")
    assert parse_topic("other/x/y/z") is None
    assert map_suffix_to_carrier("sys/power") == (
        "channel.interoceptive.received.v1", "physio.tessera_power.v1")
    assert map_suffix_to_carrier("dbpwm/telemetry")[0] == "channel.proprioceptive.received.v1"
    assert map_suffix_to_carrier("unknown/x") is None          # 禁猜——未映射显式 None


def test_power_sample_maps_to_intero() -> None:
    raw = _wire({"ver": 1, "kind": 97, "budget_ma": 500, "used_ma": 12, "peak_ma": 30,
                 "wall_ms": 0})
    s = sample_from_wire("tessera/dav/dvc/sys/power", raw, 1)
    assert s.carrier == "channel.interoceptive.received.v1"    # 电源 = 体资源（内感受）
    assert '"budget_ma":500' in s.payload_text
    assert '"node":"dav"' in s.payload_text
    assert s.payload_digest == sample_from_wire("tessera/dav/dvc/sys/power", raw, 1).payload_digest


def test_actuator_sample_maps_to_proprio() -> None:
    raw = _wire({"ver": 1, "kind": 96, "dev": 2, "value_u": 655360, "wall_ms": 0})
    s = sample_from_wire("tessera/dav/dvc/dbpwm/telemetry", raw, 3)
    assert s.carrier == "channel.proprioceptive.received.v1"   # 执行器状态 = 本体感受
    assert '"value_u":655360' in s.payload_text
    assert s.raw_digest                                        # 原始字节 digest 绑定在案


def test_unmapped_suffix_rejected_not_guessed() -> None:
    with pytest.raises(ValueError, match="unmapped suffix"):
        sample_from_wire("tessera/dav/dvc/future/thing", _wire({"a": 1}), 1)
    with pytest.raises(ValueError, match="not a tessera key"):
        sample_from_wire("other/space/x", _wire({"a": 1}), 1)
