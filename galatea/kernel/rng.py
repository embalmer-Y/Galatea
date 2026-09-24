"""counter-based RNG 流派生（L00 §4.3；Q-T11 CONFIRMED：禁全局 RNG）。

合同：
- 子种子派生 = HKDF-SHA256(ikm=run_seed, salt=固定域串, info=branch|module|stream)；
- 流内递增 counter 产生块序列；块函数（算法本体）为**显式注入**；
- **正式后端 = chacha8_block**（Q-L00-04 CONFIRMED 2026-09-25，RFC 7539 §2.3 状态
  布局、8 轮、nonce=0——每流独立 HKDF 键已保证隔离，无需 nonce）；威胁模型 =
  确定性模拟可复算，非对抗密码学（纯 Python 无常量时间保证）；
- `reference_block_blake2s` 仅为测试与合同演示提供，**禁止**作为生产默认；
- checkpoint 序列化 = (key_hex, counter, offset)，恢复后序列 bit-exact 连续。
"""
import hashlib
import hmac
import struct
from collections.abc import Callable
from dataclasses import dataclass

_HKDF_SALT = b"galatea/kernel/rng/v1"

BlockFn = Callable[[bytes, int], bytes]

_CHACHA_CONST_WORDS = (0x61707865, 0x3320646E, 0x79622D32, 0x6B206574)
_MASK32 = 0xFFFFFFFF


def hkdf_sha256(ikm: bytes, salt: bytes, info: bytes, length: int = 32) -> bytes:
    """RFC 5869 HKDF（extract + expand），SHA-256。"""
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    okm = bytearray()
    prior = b""
    counter = 1
    while len(okm) < length:
        prior = hmac.new(prk, prior + info + bytes([counter]), hashlib.sha256).digest()
        okm.extend(prior)
        counter += 1
    return bytes(okm[:length])


def _rotl32(v: int, n: int) -> int:
    return ((v << n) | (v >> (32 - n))) & _MASK32


def _quarter_round(s: list[int], a: int, b: int, c: int, d: int) -> None:
    """RFC 7539 §2.1.1 quarter round（旋转量 16/12/8/7）。"""
    s[a] = (s[a] + s[b]) & _MASK32
    s[d] = _rotl32(s[d] ^ s[a], 16)
    s[c] = (s[c] + s[d]) & _MASK32
    s[b] = _rotl32(s[b] ^ s[c], 12)
    s[a] = (s[a] + s[b]) & _MASK32
    s[d] = _rotl32(s[d] ^ s[a], 8)
    s[c] = (s[c] + s[d]) & _MASK32
    s[b] = _rotl32(s[b] ^ s[c], 7)


def chacha_block(key: bytes, counter: int, rounds: int = 8, nonce: bytes = b"\x00" * 12) -> bytes:
    """ChaCha 块函数（RFC 7539 §2.3 布局：4 常量 + 8 键 + 1 counter + 3 nonce）。

    nonce 默认 0：流隔离经 HKDF 每流独立键（Q-T11），nonce 仅供标准向量校验用。
    """
    if len(key) != 32:
        raise ValueError("chacha key must be 32 bytes")
    if len(nonce) != 12:
        raise ValueError("chacha nonce must be 12 bytes")
    working: list[int] = [
        *_CHACHA_CONST_WORDS,
        *struct.unpack("<8I", key),
        counter & _MASK32,
        *struct.unpack("<3I", nonce),
    ]
    initial = working.copy()
    for _ in range(rounds // 2):
        _quarter_round(working, 0, 4, 8, 12)
        _quarter_round(working, 1, 5, 9, 13)
        _quarter_round(working, 2, 6, 10, 14)
        _quarter_round(working, 3, 7, 11, 15)
        _quarter_round(working, 0, 5, 10, 15)
        _quarter_round(working, 1, 6, 11, 12)
        _quarter_round(working, 2, 7, 8, 13)
        _quarter_round(working, 3, 4, 9, 14)
    out = [(working[i] + initial[i]) & _MASK32 for i in range(16)]
    return struct.pack("<16I", *out)


def chacha8_block(key: bytes, counter: int) -> bytes:
    """正式后端（Q-L00-04 CONFIRMED 2026-09-25）：ChaCha8，64 字节块。"""
    return chacha_block(key, counter, 8)


def reference_block_blake2s(key: bytes, counter: int) -> bytes:
    """参考块函数（仅测试/演示；禁作生产默认——见模块 docstring）。"""
    return hashlib.blake2s(
        counter.to_bytes(16, "big"), key=key[:64] if key else b"\x00" * 32, digest_size=32
    ).digest()


@dataclass(frozen=True, slots=True)
class StreamKey:
    """流的身份四元组（(seed 指纹) 由 RngDirectory 持有，不进 key）。"""

    branch_id: str
    module_id: str
    stream_name: str


class StreamNotFound(KeyError):
    """未注册/未创建的流被引用（L00 §6.2：禁回退全局 RNG）。"""


class CounterStream:
    """单条计数器流：确定性、可快照恢复、无全局状态。"""

    def __init__(self, key: bytes, block_fn: BlockFn) -> None:
        self._key = key
        self._block_fn = block_fn
        self._counter = 0
        self._buffer = b""
        self._offset = 0

    @property
    def key_hex(self) -> str:
        return self._key.hex()

    @property
    def counter(self) -> int:
        """已生成的块数（快照用）。"""
        return self._counter

    @property
    def offset(self) -> int:
        """当前块内已消费偏移（快照用）。"""
        return self._offset

    def next_bytes(self, n: int) -> bytes:
        if n < 0:
            raise ValueError("n must be non-negative")
        out = bytearray()
        while len(out) < n:
            if self._offset >= len(self._buffer):
                self._buffer = self._block_fn(self._key, self._counter)
                self._counter += 1
                self._offset = 0
            take = min(n - len(out), len(self._buffer) - self._offset)
            out.extend(self._buffer[self._offset : self._offset + take])
            self._offset += take
        return bytes(out)

    def next_uint64(self) -> int:
        return int.from_bytes(self.next_bytes(8), "big")

    def next_float01(self) -> float:
        """[0,1) 均匀；53-bit 有效位（Q-T10 数值纪律）。"""
        return (self.next_uint64() >> 11) / float(1 << 53)

    def snapshot(self) -> "tuple[str, int, int]":
        """checkpoint 序列化：(key_hex, 块计数, 块内偏移)——偏移必载，恢复后序列 bit-exact。"""
        return (self.key_hex, self.counter, self.offset)

    @classmethod
    def restore(cls, key_hex: str, counter: int, offset: int, block_fn: BlockFn) -> "CounterStream":
        stream = cls(bytes.fromhex(key_hex), block_fn)
        stream._counter = counter
        stream._offset = offset
        if offset > 0:
            # 确定性重建当前块（块函数是纯函数：同 (key, counter) 同块）
            stream._buffer = block_fn(bytes.fromhex(key_hex), counter - 1)
        return stream


class RngDirectory:
    """流工厂与台账：同 key 复用同流（状态连续）；创建记录可整体快照。"""

    def __init__(self, run_seed: bytes, block_fn: BlockFn) -> None:
        self._run_seed = run_seed
        self._block_fn = block_fn
        self._streams: dict[StreamKey, CounterStream] = {}

    def stream(self, branch_id: str, module_id: str, stream_name: str) -> CounterStream:
        key = StreamKey(branch_id=branch_id, module_id=module_id, stream_name=stream_name)
        existing = self._streams.get(key)
        if existing is not None:
            return existing
        subseed = hkdf_sha256(
            ikm=self._run_seed,
            salt=_HKDF_SALT,
            info=f"{branch_id}|{module_id}|{stream_name}".encode("utf-8"),
        )
        stream = CounterStream(subseed, self._block_fn)
        self._streams[key] = stream
        return stream

    def snapshot(self) -> tuple[tuple[str, str, str, str, int, int], ...]:
        """全部流的 (branch, module, name, key_hex, counter, offset)，按 key 排序保证确定性。"""
        return tuple(
            (k.branch_id, k.module_id, k.stream_name, s.key_hex, s.counter, s.offset)
            for k, s in sorted(self._streams.items(), key=lambda kv: (kv[0].branch_id, kv[0].module_id, kv[0].stream_name))
        )
