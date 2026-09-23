"""RNG 流隔离 + 全库静态纪律 lint（L00 §4.3/§8；Q-T11/Q-T12/Q-T01）。"""
import re
from pathlib import Path

import pytest

from galatea.kernel.rng import CounterStream, RngDirectory, reference_block_blake2s

KERNEL_DIR = Path(__file__).resolve().parents[1]

_BANNED_IMPORT = re.compile(
    r"^\s*(import|from)\s+(random|threading|asyncio|datetime|time|torch|numpy)\b", re.MULTILINE
)


def test_same_key_same_sequence() -> None:
    a = RngDirectory(b"seed-alpha", reference_block_blake2s)
    b = RngDirectory(b"seed-alpha", reference_block_blake2s)
    seq_a = [a.stream("B", "m", "s").next_uint64() for _ in range(8)]
    seq_b = [b.stream("B", "m", "s").next_uint64() for _ in range(8)]
    assert seq_a == seq_b


def test_streams_isolated_by_module_and_name() -> None:
    d = RngDirectory(b"seed", reference_block_blake2s)
    xs = d.stream("B", "m1", "s").next_uint64()
    ys = d.stream("B", "m2", "s").next_uint64()
    zs = d.stream("B", "m1", "other").next_uint64()
    assert len({xs, ys, zs}) == 3


def test_branch_isolation() -> None:
    d = RngDirectory(b"seed", reference_block_blake2s)
    a = d.stream("branch-A", "m", "s").next_bytes(16)
    b = d.stream("branch-B", "m", "s").next_bytes(16)
    assert a != b


def test_cached_stream_is_continuous() -> None:
    d = RngDirectory(b"seed", reference_block_blake2s)
    s1 = d.stream("B", "m", "s")
    first = s1.next_uint64()
    s2 = d.stream("B", "m", "s")
    second = s2.next_uint64()
    assert first != second  # 同一条流：计数器连续，而非重新开始


def test_snapshot_restore_bit_exact() -> None:
    d = RngDirectory(b"seed", reference_block_blake2s)
    s = d.stream("B", "m", "s")
    for _ in range(3):
        s.next_uint64()
    key_hex, counter, offset = s.snapshot()
    expect = [s.next_uint64() for _ in range(4)]
    restored = CounterStream.restore(key_hex, counter, offset, reference_block_blake2s)
    assert [restored.next_uint64() for _ in range(4)] == expect


def test_directory_snapshot_sorted_deterministic() -> None:
    d = RngDirectory(b"seed", reference_block_blake2s)
    d.stream("B", "z", "s").next_uint64()
    d.stream("B", "a", "s").next_uint64()
    snap = d.snapshot()
    assert snap == tuple(sorted(snap, key=lambda row: (row[0], row[1], row[2])))


def test_kernel_static_discipline() -> None:
    """机械 lint：主体平面禁全局 RNG/线程/墙钟/asyncio（军规 5/Q-T01/T11/T12）。"""
    violations: list[str] = []
    for path in sorted(KERNEL_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for match in _BANNED_IMPORT.finditer(text):
            violations.append(f"{path.name}: {match.group(0).strip()}")
    assert violations == []
