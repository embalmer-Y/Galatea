"""H1 平台硬化门判据测试（L13 §9 H1 行；ADR-G-0024 冻结前置）。

含 INC-13 防回归钉死：test_no_repo_root_cleanup——本模块源禁 rmtree(Path("."))/
仓库根字面量清理（事故根因）。
"""
import hashlib
from pathlib import Path

from galatea.evidence.control.h1_hardening import (
    fault_injection_and_recovery,
    i3_independent_reproduction,
    long_run_stability,
    supply_chain_audit,
)

_ROOT = Path(__file__).resolve().parents[3]
_RECORDING = _ROOT / "evidence" / "c4_recording" / "recording_v1.json"


def test_no_repo_root_cleanup() -> None:
    """INC-13 防回归：硬化源零仓库根/相对路径 rmtree（仅 mkdtemp 路径清理）。"""
    src = (_ROOT / "galatea" / "evidence" / "control" / "h1_hardening.py").read_text(
        encoding="utf-8")
    allowed_targets = ("tmp", "runner._tmp")   # mkdtemp 具体路径族
    for ln in src.splitlines():
        if "rmtree" in ln and not ln.strip().startswith("#"):
            assert any(a in ln for a in allowed_targets) or "INC-13" in ln, (
                f"unsafe cleanup: {ln.strip()}"
            )


def test_long_run_stability_256_cycles() -> None:
    """判据 1：256 cycles（4× 最长此前场景）全程完成 + 容量治理面在案。"""
    out = long_run_stability(hashlib.sha256(b"h1-long-run").digest())
    assert out["stable"], out
    assert out["cycles_completed"] == 256


def test_fault_injection_and_recovery() -> None:
    """判据 2：fault 注入 + store 关闭重开 digest 不失。"""
    out = fault_injection_and_recovery(hashlib.sha256(b"h1-fault").digest())
    assert out["stable"], out
    assert out["recovery_index_unchanged"]


def test_supply_chain_audit_full_manifest() -> None:
    """判据 3：manifest 全锚 sha256 比对（零 fail；LOST/SUPERSEDED 单列）。"""
    out = supply_chain_audit(_ROOT)
    assert out["stable"], out["failed"]
    assert out["manifest_total"] == 69   # v1.30（P4-α 首评四锚——只增不减）
    assert not out["failed"]
    # lost 名单随演进增长（INC-13 三件 + P2 服务化演进 SUPERSEDED 件——锚与状态注记均保留可溯）
    assert out["lost_inc13"] == ["EXP-R0-001", "R-c5-v1-0-composite-INCONCLUSIVE",
                                 "R-c5-v1-0-gain-INCONCLUSIVE", "resident-longrun-verify"]


def test_i3_independent_reproduction_new_seeds() -> None:
    """判据 4（Q-L13-08②）：新 seed 集同派生式——效应方向一致 ∧ d ≥ 0.5。"""
    out = i3_independent_reproduction(_ROOT, _RECORDING, n=8)
    assert out["direction_consistent"], out
    assert out["meets_min_effect"], out
    assert out["stable"], out
