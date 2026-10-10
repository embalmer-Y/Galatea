"""hwmon 传感器解析（REV-0025 R6：按 name 锚定，禁裸索引）。

Linux /sys/class/hwmon 枚举序跨重启不保证稳定——裸索引（hwmon2）只是快照。
本解析器扫描 name 文件建立 {name: 路径} 映射；缺失 = typed 异常（调用方转
MISSING_SIGNAL，禁静默错读——错源比缺源更危险：INTERO 语义失真无类型化报错面）。
"""
from __future__ import annotations

from pathlib import Path

_HWMON_ROOT = Path("/sys/class/hwmon")


class HwmonResolutionError(RuntimeError):
    """hwmon name 锚解析失败（fail-closed——禁静默错读，R6）。"""


class HwmonResolver:
    """name → hwmon 目录解析器（root 可注入——测试零 /sys 依赖）。"""

    def __init__(self, root: Path = _HWMON_ROOT) -> None:
        self._root = root

    def resolve(self, name: str) -> Path:
        """按 name（如 coretemp）唯一解析 hwmon 目录；重复/缺失/不可读即拒。"""
        hits: list[Path] = []
        if self._root.is_dir():
            for entry in sorted(self._root.iterdir()):
                name_file = entry / "name"
                if name_file.is_file():
                    try:
                        if name_file.read_text(encoding="utf-8").strip() == name:
                            hits.append(entry)
                    except OSError as broken:
                        raise HwmonResolutionError(f"hwmon name file unreadable: {name_file}") from broken
        if not hits:
            raise HwmonResolutionError(f"hwmon name anchor not found: {name} (root={self._root})")
        if len(hits) > 1:
            raise HwmonResolutionError(f"hwmon name anchor ambiguous: {name} -> {[str(h) for h in hits]}")
        return hits[0]

    def read_temps_millicelsius(self, name: str) -> dict[str, int]:
        """读取该 hwmon 下全部 temp*_input（毫开尔文/毫摄氏度原值——量化归调用方）。"""
        base = self.resolve(name)
        out: dict[str, int] = {}
        for temp_file in sorted(base.glob("temp*_input")):
            try:
                out[temp_file.name.removesuffix("_input")] = int(temp_file.read_text(encoding="utf-8").strip())
            except (OSError, ValueError) as broken:
                raise HwmonResolutionError(f"temp read failed: {temp_file}") from broken
        if not out:
            raise HwmonResolutionError(f"hwmon {name} exposes no temp*_input")
        return out
