"""RunManifest：manifest 分区行（L13 §4.2/§10 recorder/manifest.py）。

墙钟**只**在 manifest 分区出现（Q-T12 CONFIRMED）；profile/seed/branch/统计计划/
sealed 分割 digest 绑定于此——EvidenceResult 的绑定物（HLD §10.3）由此承载。
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True, slots=True)
class RunManifest:
    """claim-relevant 运行的 manifest 行（四分区之 manifest 分区，每 run 恰一行）。"""

    run_id: str
    master_seed_hex: str
    branch_id: str
    profile_digests: tuple[tuple[str, str], ...]   # (profile id, content digest)
    stat_plan_digest: str
    split_digest: str | None                       # 引用 sealed 分割身份（未用 sealed 的 run 为 None）
    wall_clock_utc: str                            # Q-T12：墙钟唯一出现位

    @classmethod
    def create(
        cls,
        run_id: str,
        master_seed_hex: str,
        branch_id: str,
        profile_digests: tuple[tuple[str, str], ...],
        stat_plan_digest: str,
        split_digest: str | None,
    ) -> "RunManifest":
        wall_clock = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        return cls(
            run_id=run_id,
            master_seed_hex=master_seed_hex,
            branch_id=branch_id,
            profile_digests=profile_digests,
            stat_plan_digest=stat_plan_digest,
            split_digest=split_digest,
            wall_clock_utc=wall_clock,
        )

    def to_row(self) -> dict[str, Any]:
        """分区行（嵌套结构 JSON 序列化——Parquet 列为标量）。"""
        return {
            "run_id": self.run_id,
            "master_seed_hex": self.master_seed_hex,
            "branch_id": self.branch_id,
            "profile_digests": _json(self.profile_digests),
            "stat_plan_digest": self.stat_plan_digest,
            "split_digest": self.split_digest if self.split_digest is not None else "",
            "wall_clock_utc": self.wall_clock_utc,
        }


def _json(value: Any) -> str:
    import json

    return json.dumps(value, sort_keys=True, separators=(",", ":"))
