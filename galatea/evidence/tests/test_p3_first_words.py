"""P3 第一句话脚本结构测试（无网络/无硬件；冻结-回放命名与 fail-closed 语义）。"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from p3_first_words import (  # noqa: E402
    CORPUS_STATES,
    frozen_wav_path,
)


def test_corpus_states_schema_frozen() -> None:
    """语库 v1：14 冻结态、五字段 schema、值域=主体可表示域（Q-L12-09）。"""
    assert len(CORPUS_STATES) == 14
    for s in CORPUS_STATES:
        assert set(s) == {"energy", "energy_trend", "integrity", "current_goal", "valence"}
        assert 0.0 <= s["energy"] <= 1.0
        assert s["energy_trend"] in ("rising", "steady", "falling")
        assert 0.0 <= s["integrity"] <= 1.0
        assert isinstance(s["current_goal"], str)
        assert -1.0 <= s["valence"] <= 1.0


def test_frozen_wav_path_deterministic_naming(tmp_path: Path) -> None:
    """冻结命名 = utterance digest（同句同名——运行时查此文件；改名即 miss）。"""
    a = frozen_wav_path(tmp_path, "我的能量百分之七十五。")
    b = frozen_wav_path(tmp_path, "我的能量百分之七十五。")
    c = frozen_wav_path(tmp_path, "我的能量百分之五十。")
    assert a == b and a != c and a.name.startswith("u_")


def test_speak_requires_frozen_wav_fail_closed(tmp_path: Path) -> None:
    """运行时禁渲染：冻结件缺失 = fail-closed（Q-L10-17 行内补裁）。"""
    from p3_first_words import cmd_speak
    rec = tmp_path / "rreport_v1.json"
    entry_payload = dict(CORPUS_STATES[0])
    digest_payload = json.dumps(entry_payload, sort_keys=True, separators=(",", ":"))
    import hashlib
    rec.write_text(json.dumps({
        "session": {"provider": "x", "model_id": "m", "endpoint": "e", "discipline": "t"},
        "entries": [{
            "role": "R-REPORT", "input_payload": entry_payload,
            "input_digest": hashlib.sha256(digest_payload.encode()).hexdigest(),
            "output_text": json.dumps({"utterance": "测试句。"}, ensure_ascii=False),
            "model_id": "m",
        }]}, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(RuntimeError, match="frozen WAV missing"):
        cmd_speak(0, 2, tmp_path / "out", rec)    # wavs/ 未冻结 → 必拒


def test_r_report_contract_registered() -> None:
    """R-REPORT 合同在录制面注册（禁临时发明角色执法面覆盖语库角色）。"""
    from galatea.evidence.control.recording import build_role_prompt
    messages = build_role_prompt("R-REPORT", {"energy": 0.9})
    assert any("self-report" in m["content"] for m in messages)
    assert any("Chinese" in m["content"] for m in messages)
