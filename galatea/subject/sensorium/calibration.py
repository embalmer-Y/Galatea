"""校准版本绑定与漂移统计（L02 §2.1 calibration_load / §4.2 / §10 calibration.py）。

C0 = 单版本冻结 `c0-static-v1`（Q-G00-12②，运行期只读）；漂移策略 Q-L01…Q-L02-01
归 C1。版本不符 fail closed（CalibrationMismatch，L02 §6）。
"""
import hashlib
from dataclasses import dataclass
from pathlib import Path

from galatea.subject.sensorium.ports import CalibrationMismatch


@dataclass(frozen=True, slots=True)
class CalibrationVersion:
    """校准版本（L02 §2.1：id + params digest + 有效域）。"""

    version_id: str
    params_digest: str
    valid_scope: str       # "c0-mw0"（MW0 模态面）

    def check(self, claimed: str) -> None:
        """帧声明版本与绑定版本比对：不符即 fail closed。"""
        if claimed != self.version_id:
            raise CalibrationMismatch(f"expected {self.version_id!r}, frame claims {claimed!r}")


def bind_calibration(profile_path: Path, profile_version_id: str) -> CalibrationVersion:
    """绑定冻结 profile 的校准版本（params digest = profile 文件内容 sha256）。"""
    digest = hashlib.sha256(profile_path.read_bytes()).hexdigest()
    return CalibrationVersion(
        version_id=profile_version_id, params_digest=digest, valid_scope="c0-mw0"
    )


def drift_statistics(claimed_versions: tuple[str, ...], bound: CalibrationVersion) -> dict[str, int]:
    """T6 长程汇总（L02 §5）：各声明版本帧计数；C0 单版本 → 漂移 = 非 bound 版本计数。"""
    stats: dict[str, int] = {}
    for claimed in claimed_versions:
        stats[claimed] = stats.get(claimed, 0) + 1
    drift = sum(count for version, count in stats.items() if version != bound.version_id)
    stats["__drift__"] = drift   # C0 期望恒 0（单版本）；C1 随 Q-L02-01 治理
    return stats
