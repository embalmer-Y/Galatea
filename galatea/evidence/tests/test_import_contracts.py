"""import-linter 契约测试（REV-0012 R7 / Q-L13-05 C0 期义务：静态禁写路径机械化）。

四契约（pyproject [tool.importlinter]）：P04 主体禁读证据、P06/P14 环境禁读主体、
P09 sensorium 禁触行动/目标/知觉、kernel 独立性。lint-imports 违约 = 测试失败。
"""
import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]


def test_import_linter_contracts_kept() -> None:
    result = subprocess.run(
        ["uv", "run", "lint-imports"],
        cwd=_ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, (
        f"import contracts broken:\n{result.stdout[-2000:]}\n{result.stderr[-500:]}"
    )
    assert "0 broken" in result.stdout


def test_all_four_contracts_declared() -> None:
    pyproject = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for needle in ("[\"galatea.subject\"]", "[\"galatea.env\"]", "[\"galatea.subject.sensorium\"]", "[\"galatea.kernel\"]"):
        assert needle in pyproject
    assert pyproject.count("[[tool.importlinter.contracts]]") == 4
