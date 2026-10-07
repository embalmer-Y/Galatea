"""录制回放确定性（L12 §10 test_recorded_replay_determinism.py；Q-L12-03）。"""
import pytest

from galatea.subject.language.replay import LLMReplayMiss, ReplayStore, canonical_input_digest


def test_replay_hit_bit_exact_twice() -> None:
    store = ReplayStore()
    store.record("R-PARSE", {"text": "hello", "requester": "exp"},
                 '{"type": "request", "confidence": 0.8}', "glm-4.7")
    o1 = store.invoke("R-PARSE", {"text": "hello", "requester": "exp"})
    o2 = store.invoke("R-PARSE", {"text": "hello", "requester": "exp"})
    assert o1 is o2
    assert o1.output_text == '{"type": "request", "confidence": 0.8}'
    assert o1.model_id == "glm-4.7"      # 模型标识随条目走（EvidenceResult 元数据来源）


def test_replay_miss_fail_closed_no_online_path() -> None:
    """miss = fail closed；本模块无任何在线调用路径（结构排除事后选择）。"""
    store = ReplayStore()
    with pytest.raises(LLMReplayMiss, match="LLM_REPLAY_MISS"):
        store.invoke("R-PARSE", {"text": "unrecorded", "requester": "exp"})
    assert not hasattr(store, "call_online")
    assert not hasattr(store, "invoke_online")


def test_canonical_digest_order_insensitive() -> None:
    """键序无关（规范化 = 排序键 JSON——同输入同 digest）。"""
    a = canonical_input_digest({"text": "x", "requester": "r"})
    b = canonical_input_digest({"requester": "r", "text": "x"})
    assert a == b


def test_different_input_different_key() -> None:
    a = canonical_input_digest({"text": "x", "requester": "r"})
    b = canonical_input_digest({"text": "y", "requester": "r"})
    assert a != b
