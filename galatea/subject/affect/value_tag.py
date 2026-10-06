"""AffectiveValueTag 提案（L05 §2.2/§10 value_tag.py，C2 实现期）。

合同（L05 §3）：**L06 是唯一写者，L05 只提供标签提案**——本模块不写主体记忆
（无 store 调用、无 db 面）；标签 = 情感对记忆的标注接口（L06 affective_value
子系统写侧来源）。C2 次单元 L06 扩展消费本提案（c2_memory.profile §affective_write）。
"""
from dataclasses import dataclass

__all__ = ["AffectiveValueTag", "propose_value_tag"]


@dataclass(frozen=True, slots=True)
class AffectiveValueTag:
    """价值标注提案（L05 §2.2：memory_ref + valence/arousal/persistence）。"""

    memory_ref: str                   # 目标记忆条目引用（episodic encode 侧 id）
    valence: float
    arousal: float
    persistence: float
    proposed_at: int

    def __post_init__(self) -> None:
        if not -1.0 <= self.valence <= 1.0:
            raise ValueError(f"valence out of [−1,1]: {self.valence!r}")
        for name in ("arousal", "persistence"):
            v = getattr(self, name)
            if not 0.0 <= v <= 1.0:
                raise ValueError(f"{name} out of [0,1]: {v!r}")


def propose_value_tag(memory_ref: str, valence: float, arousal: float,
                      persistence: float, at: int) -> AffectiveValueTag:
    """确定性构造（提案面——落盘由 L06 唯一写者执行）。"""
    return AffectiveValueTag(
        memory_ref=memory_ref, valence=valence, arousal=arousal,
        persistence=persistence, proposed_at=at,
    )
