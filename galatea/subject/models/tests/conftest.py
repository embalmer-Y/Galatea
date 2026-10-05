"""C1 模型面测试共用装置（复用知觉面流装置；三模型级联输入）。"""
from typing import Any

from galatea.subject.c1profile import C1Profile, load_c1_profile
from galatea.subject.perception.pipeline import PerceptionPipeline
from galatea.subject.perception.tests.conftest import frames_at, uniform_window


def profile() -> C1Profile:
    return load_c1_profile()


def perception_output(t: int = 7, center_value: float = 0.9) -> Any:
    """真实流 → 知觉输出（窗组 frames → PerceptionOutput）。"""
    pipeline = PerceptionPipeline()
    return pipeline.process_window(t, frames_at(uniform_window(center_value), t))


def world_with_observation(t: int = 7, center_value: float = 0.9):
    from galatea.subject.models.world import WorldModel

    prof = profile()
    model = WorldModel(prof, run_id="R")
    out = perception_output(t, center_value)
    belief = model.update(
        t, out.cells, move_receipts=(), forage_receipts=(), requested_moves=()
    )
    return prof, model, belief, out
