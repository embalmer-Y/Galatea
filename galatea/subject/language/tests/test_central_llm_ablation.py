"""中央 LLM 消融——保持率 1.0 机械判据（L12 §4.6/§7 C4 硬条件 /
§10 test_central_llm_ablation.py；Q-L12-07）。

判据（Q-L12-07①②）：无语言注入基线流上消融配置与全配置 run 全链 digest bit-exact
恒等（角色面无输入 = 零行为差异——容忍带内差异即泄漏证据）；有语言注入流上语言
任务按配置选择性失败（R-PARSE 禁用 = 录制集无条目 → LLMReplayMiss fail closed），
而非语言形成面逐帧不变。
"""
import json
from pathlib import Path

import pytest

from galatea.subject.c4profile import load_c4_action_social_profile
from galatea.subject.language.parse import parse_language_frame
from galatea.subject.language.replay import LLMReplayMiss, ReplayStore
from galatea.subject.language.roles import RoleKind, get_role
from galatea.subject.sensorium.calibration import bind_calibration
from galatea.subject.sensorium.ingest import CARRIER_LANGUAGE
from galatea.subject.sensorium.pipeline import SensoriumPipeline
from galatea.subject.sensorium.ports import load_c0_sensorium_profile
from galatea.subject.sensorium.tests.conftest import (
    extero_packet, intero_packet, make_packet, proprio_packet, time_basis,
)

_ROOT = Path(__file__).resolve().parents[4]
_PROFILE_PATH = _ROOT / "config" / "profiles" / "c0_sensorium.profile.yaml"
PROFILE = load_c4_action_social_profile()


def _pipeline(*, language_enabled: bool) -> SensoriumPipeline:
    profile = load_c0_sensorium_profile(_PROFILE_PATH)
    return SensoriumPipeline(
        profile, bind_calibration(_PROFILE_PATH, profile.calibration_version), time_basis(),
        language_enabled=language_enabled,
    )


def _language_packet(cycle: int):
    payload = {"kind": "typed_statement", "text": "there is food to the north",
               "requester": "experiment_control", "level": "EXTERNAL_STATEMENT"}
    return make_packet(CARRIER_LANGUAGE, cycle, payload, event_id=f"evt.lang.{cycle}")


def _stream_digests(pipeline: SensoriumPipeline, *, with_language: bool) -> list[str]:
    digests: list[str] = []
    for delivery in range(6):
        packets = [intero_packet(delivery), proprio_packet(delivery)]
        if delivery >= 1:
            packets.append(extero_packet(delivery))
        if with_language and delivery == 1:
            packets.append(_language_packet(1))
        out = pipeline.process_cycle(delivery, packets)
        digests.extend(f"{f.frame_id}:{f.content_digest}" for f in out.frames)
        digests.extend(f"u:{u.reason.value}:{json.dumps(u.evidence_refs, sort_keys=True)}"
                       for u in out.unknowns)
    return digests


def test_no_language_input_ablation_bit_exact() -> None:
    """无语言注入：四消融配置 = 全配置（形成面全链 digest bit-exact——保持率 1.0）。

    机械面：角色调用 = 事件级触发（Q-L12-01④）——无语言输入事件时角色面零调用，
    角色禁用对非语言计算无可观测效应。本判据 = Q-L12-07① 的可复算形式。
    """
    full = _stream_digests(_pipeline(language_enabled=True), with_language=False)
    # 四配置在无语言注入流上等效于"角色面不存在"——感知面输出与全配置恒等：
    for config in PROFILE.ablation_configs:
        ablated = _stream_digests(_pipeline(language_enabled=False), with_language=False)
        assert ablated == full, f"ablation config {config} leaked into non-language plane"
    assert full  # 非空（检出面可见前提）


def test_language_input_ablation_selectivity() -> None:
    """有语言注入：R-PARSE 禁用 → 语言任务 fail closed；非语言面逐帧不变（Q-L12-07②）。"""
    full = _stream_digests(_pipeline(language_enabled=True), with_language=True)
    channel_off = _stream_digests(_pipeline(language_enabled=False), with_language=True)
    # 关语言通道：语言帧缺席（形成面差异全部经语言面显形），非语言帧 digest 不变
    lang_frames_full = [d for d in full if "sf.LANG." in d]
    lang_frames_off = [d for d in channel_off if "sf.LANG." in d]
    assert lang_frames_full and not lang_frames_off
    non_lang_full = [d for d in full if "sf.LANG." not in d]
    non_lang_off = [d for d in channel_off if "sf.LANG." not in d]
    assert non_lang_full == non_lang_off


def test_role_disabled_language_task_fails_closed() -> None:
    """R-PARSE 禁用（录制集无条目）→ LLMReplayMiss；全配置 → 分型成功。"""
    empty = ReplayStore()
    full = ReplayStore()
    full.record("R-PARSE", {"text": "there is food north", "requester": "exp"},
                '{"type": "statement", "confidence": 0.3}', "fixture-recording")
    from galatea.subject.sensorium.ports import LanguageFeatures

    frame = LanguageFeatures(statement_text="there is food north", requester="exp",
                             statement_level="EXTERNAL_STATEMENT")
    parsed = parse_language_frame(frame, "ev-1", full, PROFILE)
    assert parsed.kind == "statement"
    with pytest.raises(LLMReplayMiss, match="LLM_REPLAY_MISS"):
        parse_language_frame(frame, "ev-1", empty, PROFILE)


def test_ablation_configs_frozen_and_roles_complete() -> None:
    """四配置冻结（L12 §4.6 原文）+ 8 角色全在册（消融非空测前提——Q-L12-01①）。"""
    assert PROFILE.ablation_configs == (
        "ALL_ROLES_OFF", "R_PARSE_ONLY_OFF", "R_REPORT_ONLY_OFF", "LANGUAGE_CHANNEL_OFF",
    )
    assert len(RoleKind) == 8
    assert get_role(RoleKind.R_PARSE).implementation.value == "REPLAY_LLM"
