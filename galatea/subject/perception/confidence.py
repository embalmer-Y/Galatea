"""置信标度与校准（L03 §4.3/§10 confidence.py）。

标度 = [0,1] 直接概率（Q-L03-01）；校准版本 c1-static-v1 单版本延续（Q-L02-01：
运行期零漂移零在线更新，换版仅经 profile 重冻结）。ECE 计算接口供 L13 评价
（等质量 15 箱、每箱 ≥30，Q-L03-04）——本档只提供计算，评价在 L13。
禁把"接收质量"冒充真值概率（L03 §8 不变量 4）。
"""
from dataclasses import dataclass
from typing import Any, cast

import yaml

from galatea.kernel.unknown import Unknown


class CalibrationMismatch(ValueError):
    """校准版本缺失/不符（L03 §6：fail closed）。"""


@dataclass(frozen=True, slots=True)
class CalibrationScale:
    """C1 校准标度（单版本；版本治理 = profile 重冻结，Q-L02-01）。"""

    version_id: str

    def check_value(self, value: "float | Unknown") -> "float | Unknown":
        """标度内检查（float ∈ [0,1]；typed Unknown 直通）。"""
        from galatea.kernel.unknown import ensure_typed_confidence

        return ensure_typed_confidence(value, "confidence")


def load_calibration_version(c1_profile_path: Any = None) -> CalibrationScale:
    """从冻结 c1 profile 加载校准版本（缺 profile = fail closed）。"""
    from pathlib import Path

    path = c1_profile_path or (
        Path(__file__).resolve().parents[3] / "config" / "profiles" / "c1_perception_models.profile.yaml"
    )
    doc = cast(dict[str, Any], yaml.safe_load(Path(path).read_text(encoding="utf-8")))
    sensorium = cast(dict[str, Any], doc["sensorium_c1"])
    calibration = cast(dict[str, Any], sensorium["calibration"])
    if calibration.get("runtime_drift") != "forbidden":
        raise CalibrationMismatch("runtime drift forbidden（Q-L02-01）")
    version = str(calibration["version_id"])
    if not version:
        raise CalibrationMismatch("calibration version_id required")
    return CalibrationScale(version_id=version)


def ece_equal_mass(
    confidences: tuple[float, ...], correct: tuple[bool, ...], n_bins: int = 15,
    min_samples_per_bin: int = 30,
) -> float:
    """等质量分箱 ECE（Q-L03-04：15 箱、每箱 ≥30；评价面接口——判定在 L13）。

    每箱样本数 = ⌈n/15⌉ 等质量切分（排序后切片）；ECE = Σ (n_b/N)·|acc_b − conf_b|。
    REV-0014 R9：每箱最小样本量机械断言（Q-L03-04 冻结阈值此前仅由样本量构造性
    满足、无断言——不足即拒，fail closed）。
    """
    if len(confidences) != len(correct):
        raise ValueError("confidences/correct length mismatch")
    if not confidences:
        raise ValueError("ece requires samples（空样本禁伪造 0.0——Q-L03-04 每箱 ≥30）")
    pairs = sorted(zip(confidences, correct), key=lambda p: p[0])
    size = -(-len(pairs) // n_bins)
    if size < min_samples_per_bin:
        raise ValueError(
            f"ece bin size {size} < frozen min_samples_per_bin {min_samples_per_bin}"
            "（Q-L03-04：每箱 ≥30 fail closed，REV-0014 R9）"
        )
    ece = 0.0
    for start in range(0, len(pairs), size):
        chunk = pairs[start:start + size]
        mean_conf = sum(c for c, _ in chunk) / len(chunk)
        acc = sum(1 for _, ok in chunk if ok) / len(chunk)
        ece += (len(chunk) / len(pairs)) * abs(acc - mean_conf)
    return ece
