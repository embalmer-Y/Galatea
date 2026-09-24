"""环境平面泄漏静态探针（L01 §3/§10 test_leakage_env.py——F0 schema 层的命名空间隔离）。

主体平面（galatea/subject/**）禁止 import 环境真值命名空间（galatea.env.**）——
import-linter 的 CI 强制在 M0 落地；本测试是其在 F0 的静态等价物。

探针自检纪律（INC-08 教训，REV-0003 R1）：静态探针必须先证明"对被检对象可见、
且能报红"——test_probe_self_check 用注入违规样本验证扫描函数可失败；
防再次空转。
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]  # tests/env/<file> → tests → 仓库根（INC-08：parents[1] 曾指向不存在的 tests/galatea/...）
SUBJECT_ROOT = REPO_ROOT / "galatea" / "subject"
ENV_ROOT = REPO_ROOT / "galatea" / "env"


def _scan_for_env_imports(root: Path) -> list[str]:
    """扫描目录下全部 .py 的 `import galatea.env` / `from galatea.env`。"""
    violations: list[str] = []
    for path in sorted(root.rglob("*.py")):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith(("import galatea.env", "from galatea.env")):
                violations.append(f"{path}: {line_no}: {stripped}")
    return violations


def test_subject_root_exists_and_is_scanned() -> None:
    """可见性前置断言：扫描目标必须存在且非空（空转防护第一层）。"""
    assert SUBJECT_ROOT.is_dir(), f"subject root missing: {SUBJECT_ROOT}"
    scanned = list(SUBJECT_ROOT.rglob("*.py"))
    assert scanned, "no python files under subject root — probe would be a no-op"


def test_probe_can_fail_on_injected_violation(tmp_path: Path) -> None:
    """自检：注入违规样本 → 探针必须报红（空转防护第二层，INC-08）。"""
    fixture = tmp_path / "subject" / "fake_module.py"
    fixture.parent.mkdir(parents=True)
    fixture.write_text("import galatea.env.world.truth  # violating fixture\n", encoding="utf-8")
    violations = _scan_for_env_imports(tmp_path / "subject")
    assert len(violations) == 1 and "fake_module.py" in violations[0]


def test_subject_plane_never_imports_env_truth() -> None:
    assert _scan_for_env_imports(SUBJECT_ROOT) == []


def test_env_plane_declares_no_subject_imports() -> None:
    """反向确认：env 平面不 import 主体平面（单向依赖，L01 §3）。"""
    assert ENV_ROOT.is_dir()
    violations: list[str] = []
    for path in sorted(ENV_ROOT.rglob("*.py")):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith(("import galatea.subject", "from galatea.subject")):
                violations.append(f"{path}: {stripped}")
    assert violations == []
