"""环境平面泄漏静态探针（L01 §3/§10 test_leakage_env.py——F0 schema 层的命名空间隔离）。

主体平面（galatea/subject/**）禁止 import 环境真值命名空间（galatea.env.**）——
import-linter 的 CI 强制在 M0 落地；本测试是其在 F0 的静态等价物。
"""
from pathlib import Path

SUBJECT_ROOT = Path(__file__).resolve().parents[1] / "galatea" / "subject"


def test_subject_plane_never_imports_env_truth() -> None:
    violations: list[str] = []
    for path in sorted(SUBJECT_ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith(("import galatea.env", "from galatea.env")):
                violations.append(f"{path.relative_to(SUBJECT_ROOT)}:{line_no}: {stripped}")
    assert violations == []


def test_env_plane_declares_no_subject_imports() -> None:
    """反向确认：env 平面不 import 主体平面（单向依赖，L01 §3）。"""
    env_root = Path(__file__).resolve().parents[1] / "galatea" / "env"
    for path in sorted(env_root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            assert not stripped.startswith(("import galatea.subject", "from galatea.subject")), path.name
