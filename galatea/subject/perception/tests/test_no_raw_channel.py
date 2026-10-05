"""禁 raw 通道旁路测试（L03 §7 no_raw_channel 行 + §8 禁写路径）。"""
import sys
from pathlib import Path

_FORBIDDEN_MODULES = (
    "galatea.env",                       # 世界实现/真值（L03 §8 不变量 2）
    "galatea.subject.action",            # 行动面（禁写路径）
    "galatea.subject.goals",             # 目标面（禁写路径）
    "galatea.subject.models",            # L04 在知觉下游——层级单向（L03 §2.1）
)


def test_perception_imports_no_env_or_downstream_module():
    """知觉面 import 图零 env / 行动 / 目标 / 下游模型依赖（静态面）。"""
    perception_dir = Path(galatea_pkg_root())
    for path in sorted(perception_dir.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        for bad in _FORBIDDEN_MODULES:
            assert bad not in source, f"{path.name} imports {bad}（禁写路径/旁路面）"


def galatea_pkg_root() -> str:
    import galatea.subject.perception.pipeline as mod

    return str(Path(mod.__file__).resolve().parent)


def test_loaded_modules_clean():
    """动态面：干净子进程 import 知觉面 → 无 env 模块被加载（进程隔离，禁同进程误判）。"""
    import subprocess
    import sys as _sys

    code = (
        "import sys; import galatea.subject.perception.pipeline; "
        "bad = [m for m in sys.modules if m.startswith('galatea.env')]; "
        "print('ENV_LOADED' if bad else 'CLEAN')"
    )
    result = subprocess.run(
        [_sys.executable, "-c", code], capture_output=True, text=True, timeout=120,
        cwd=str(Path(galatea_pkg_root()).parents[2]),
    )
    assert "CLEAN" in result.stdout, f"perception plane loaded env modules: {result.stdout}"


def test_cue_never_becomes_content():
    """记忆线索只记引用，不得注入信念内容（L03 §8 不变量 6）。"""
    from galatea.subject.perception.pipeline import PerceptionPipeline
    from galatea.subject.perception.tests.conftest import frames_at, uniform_window

    pipeline = PerceptionPipeline()
    out = pipeline.process_window(
        7, frames_at(uniform_window(0.9), 7), cues=("cue.treasure_at_100_100",)
    )
    assert out.beliefs
    for belief in out.beliefs:
        assert "cue." not in belief.belief_id
        for name, _fids in belief.modality_support:
            assert "cue" not in name
    assert any("cue.treasure_at_100_100" in r.cues for r in out.receipts)
