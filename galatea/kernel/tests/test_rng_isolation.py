"""RNG 流隔离 + 全库静态纪律 lint（L00 §4.3/§8；Q-T11/Q-T12/Q-T01）。"""
import re
from pathlib import Path

import pytest

from galatea.kernel.rng import (
    CounterStream,
    RngDirectory,
    chacha8_block,
    chacha_block,
    reference_block_blake2s,
)

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


def test_chacha_block_rfc7539_layout_and_avalanche() -> None:
    """ChaCha 核心结构校验：雪崩特性（单键位翻转 → 输出近半位翻转）。

    注：仓库内无权威已知答案向量可引用（禁臆造标准向量——项目认识纪律）；
    正确性主张 = RFC 7539 §2.3 状态布局实现 + 雪崩特性 + 确定性/隔离性（本项目
    消费的实质需求）。Q-L00-04（2026-09-25）。
    """
    key = bytes(32)
    base = chacha_block(key, 0, rounds=20)
    flipped = chacha_block(bytes([1]) + bytes(31), 0, rounds=20)
    diff_bits = sum(bin(a ^ b).count("1") for a, b in zip(base, flipped))
    assert 192 <= diff_bits <= 320  # 64B 块 = 512 位输出，随机化期望 256±阈值

    assert chacha_block(key, 0, 8) != chacha_block(key, 1, 8)  # counter 敏感
    assert chacha_block(key, 0, 8) != chacha_block(key, 0, 20)  # 轮数敏感


def test_chacha8_production_backend_isolated_and_deterministic() -> None:
    """正式后端（Q-L00-04）：确定性 + 流隔离 + 与参考后端可区分（注入真实生效）。"""
    d1 = RngDirectory(b"seed", chacha8_block)
    d2 = RngDirectory(b"seed", chacha8_block)
    assert [d1.stream("B", "m", "s").next_uint64() for _ in range(4)] == [
        d2.stream("B", "m", "s").next_uint64() for _ in range(4)
    ]
    d3 = RngDirectory(b"seed", reference_block_blake2s)
    assert d1.stream("B", "m", "s").next_uint64() != d3.stream("B", "m", "s").next_uint64()
    assert d1.stream("B", "m", "s").next_uint64() != d1.stream("B", "m2", "s").next_uint64()


def test_kernel_static_discipline() -> None:
    """机械 lint：主体平面禁全局 RNG/线程/墙钟/asyncio（军规 5/Q-T01/T11/T12）。"""
    violations: list[str] = []
    for path in sorted(KERNEL_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for match in _BANNED_IMPORT.finditer(text):
            violations.append(f"{path.name}: {match.group(0).strip()}")
    assert violations == []
