"""canonical JSON 与 content digest（L00 §4.4；schema L00.digest.v1）。

纪律：digest 是一切完整性的根基——键排序、UTF-8、紧凑分隔、浮点 round-trip
（json.dumps 用 float.__repr__）、bytes 走 base64 标签、dataclass 转 dict；
非有限浮点 fail closed（不确定性必须走 typed unknown，禁止以 NaN/Inf 进 digest 链）。
"""
import base64
import dataclasses
import hashlib
import json
from typing import Any, cast

BytesTag = "__bytes_b64__"
UnknownTag = "__typed_unknown__"


def _transform(value: Any) -> Any:
    """规整为 JSON 可序列化结构（元组→列表；bytes→标签对象；拒绝其他类型）。"""
    if isinstance(value, bool) or value is None or isinstance(value, (int, str)):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError(f"non-finite float cannot enter digest chain: {value!r}")
        return value
    if isinstance(value, bytes):
        return {BytesTag: base64.b64encode(value).decode("ascii")}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _transform(dataclasses.asdict(value))
    if isinstance(value, dict):
        entries = cast("dict[Any, Any]", value)
        out: dict[str, Any] = {}
        for key, item in entries.items():
            if not isinstance(key, str):
                raise TypeError(f"canonical JSON keys must be str, got {type(key)!r}")
            out[key] = _transform(item)
        return out
    if isinstance(value, (list, tuple)):
        seq = cast("list[Any]", value)
        return [_transform(item) for item in seq]
    raise TypeError(f"type not canonicalizable: {type(value)!r}")


def canonical_json(obj: Any) -> bytes:
    """规整对象的 canonical JSON 字节（确定性：同对象同字节，与插入序/哈希序无关）。"""
    text = json.dumps(
        _transform(obj),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return text.encode("utf-8")


def content_digest(obj: Any) -> str:
    """sha256(canonical_json(obj))，十六进制。"""
    return hashlib.sha256(canonical_json(obj)).hexdigest()


def blob_digest(data: bytes) -> str:
    """裸字节 blob 的 sha256（payload 单独 digest，L00 §4.4）。"""
    return hashlib.sha256(data).hexdigest()
