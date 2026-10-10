"""Sensorium ports 与 C0 冻结 profile 加载（L02 §2/§10 ports.py；Q-G00-12/Q-L02-03/-05）。

纪律：SensoryFrame 表示层级恒 SENSORY_FORMED（构造期守卫，禁提升）；本档不产出
信念/事实/目标/意图/归属（L02 §8 不变量 2）；typed loader fail-closed（INC-11 纪律）。
"""
import enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import yaml

from galatea.kernel.packet import RepresentationLevel
from galatea.kernel.unknown import Unknown


class SensoryModality(enum.StrEnum):
    """C0 模态集四类（Q-G00-12①）+ C4 LANGUAGE 扩展（c4_action_social.profile
    sensorium_c4.modality_set_extension；扩展 = profile 新版本 + 模态枚举升级，L02 §9 C5 行同律）。

    LANGUAGE 帧形成 = L12 §4.3 唯一合法路径（ReceivedSignal(EXTERNAL_STATEMENT) →
    SensoryFrame(modality=LANGUAGE)）；层级恒 EXTERNAL_STATEMENT 源、永不提升。
    """

    EXT_LOCAL_OBS = "EXT_LOCAL_OBS"
    EXT_EVENT = "EXT_EVENT"
    INTERO = "INTERO"
    PROPRIO = "PROPRIO"
    LANGUAGE = "LANGUAGE"


class SchemaViolation(ValueError):
    """输入包 schema/provenance/层级不合法（L02 §6：拒绝形成，禁空帧占位）。"""


class RepresentationEscalation(RuntimeError):
    """表示层级被下游篡改/提升（L02 §6：S0——立即停止 + 废止证据）。"""


class ModulationRejected(ValueError):
    """C0 期增益调制入口不存在（Q-G00-12③：gain_max/GainReceipt 调制面归 C2）。"""


class CalibrationMismatch(ValueError):
    """校准版本与冻结 profile 不符（L02 §6：fail closed，停止 claim-relevant 运行）。"""


@dataclass(frozen=True, slots=True)
class C0SensoriumProfile:
    """c0_sensorium.profile.yaml 的 typed 视图（全部数值溯源 Q-L02-03/-05/Q-G00-12）。"""

    modalities: tuple[SensoryModality, ...]
    excluded_carriers: tuple[str, ...]
    w_align_cycles: int
    late_revision_lookback_windows: int
    intero_sensations: tuple[str, ...]
    calibration_version: str
    gain_form: str


def load_c0_sensorium_profile(path: Path | None = None) -> C0SensoriumProfile:
    """加载并校验 C0 冻结 profile（缺键/越界 fail-closed；结构验证 = 冻结前已过）。"""
    if path is None:
        path = Path(__file__).resolve().parents[3] / "config" / "profiles" / "c0_sensorium.profile.yaml"
    raw = cast(dict[str, Any], yaml.safe_load(path.read_text(encoding="utf-8")))
    header = cast(dict[str, Any], raw["profile"])
    if header["id"] != "c0_sensorium":
        raise ValueError(f"not a c0_sensorium profile: {header['id']}")
    sensorium = cast(dict[str, Any], raw["sensorium"])
    modalities = tuple(SensoryModality(m["id"]) for m in sensorium["modalities"])
    extero_count = sum(1 for m in sensorium["modalities"] if m["exteroceptive"])
    if extero_count < 2 or extero_count == len(sensorium["modalities"]):
        raise ValueError("C0 gate requires >=2 exteroceptive and >=1 interoceptive modality（L02 §9）")
    alignment = cast(dict[str, Any], sensorium["alignment"])
    gain = cast(dict[str, Any], sensorium["gain"])
    determinism = cast(dict[str, Any], sensorium["determinism"])
    if gain["c0_form"] != "identity_1.0":
        raise ValueError("C0 gain form must be identity_1.0（Q-G00-12③；调制面归 C2）")
    if determinism["rng_operators"] != "none_c0":
        raise ValueError("C0 formation operators must be RNG-free（Q-G00-12 伞式 + 流纪律 Q-G00-10：无算子不注册死流）")
    return C0SensoriumProfile(
        modalities=modalities,
        excluded_carriers=tuple(str(c) for c in sensorium["excluded_carriers"]),
        w_align_cycles=int(alignment["w_align_cycles"]),
        late_revision_lookback_windows=int(alignment["late_revision_lookback_windows"]),
        intero_sensations=tuple(str(s) for s in sensorium["intero_sensations"]),
        calibration_version=str(cast(dict[str, Any], sensorium["calibration"])["version_id"]),
        gain_form=str(gain["c0_form"]),
    )


@dataclass(frozen=True, slots=True)
class GainState:
    """帧级增益态（L02 §4.1 gain 节；C0 = 恒等、PROFILE 来源、无调制）。"""

    applied_factor: float
    source: str            # "PROFILE"（C0）；"MODULATION" 归 C2


@dataclass(frozen=True, slots=True)
class QualityMetrics:
    """质量度量纲（Q-G00-12④ C0 面：completeness + corruption_flags）。"""

    completeness: float    # [0,1]
    corruption_flags: tuple[str, ...]

    def __post_init__(self) -> None:
        if not 0.0 <= self.completeness <= 1.0:
            raise ValueError(f"completeness out of [0,1]: {self.completeness}")


@dataclass(frozen=True, slots=True)
class ExtLocalObsFeatures:
    """外感受·局部观测特征（observation_window 载荷 → 5×5 归一窗）。"""

    window: tuple[tuple[float, ...], ...]


@dataclass(frozen=True, slots=True)
class ExtEventFeatures:
    """外感受·事件观测特征（interoceptive_state.events 威胁观测面，Q-G00-12①）。"""

    events: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InteroSensations:
    """内感受四 sensation + 派生差分（Q-L02-05；energy_rate 首帧 = typed Unknown）。"""

    energy_level: float
    integrity_level: float
    damage_event: bool
    energy_depleted: bool
    energy_rate: "float | Unknown"


@dataclass(frozen=True, slots=True)
class ProprioFeatures:
    """本体感受特征（proprioceptive_state 载荷：朝向；位置 M0 不下发，Q-L01-09⑥）。"""

    orientation: str


@dataclass(frozen=True, slots=True)
class LanguageFeatures:
    """语言模态特征（L12 §4.3：typed statement 原文引用 + 分型原始面；零后验权重，
    Q-L12-06①——本帧只供 R-PARSE 与验证行为触发，不入知觉融合）。"""

    statement_text: str
    requester: str
    statement_level: str      # EXTERNAL_STATEMENT（层级永不提升，L12 §4.1）


@dataclass(frozen=True, slots=True)
class AudioFeatures:
    """音频感觉特征（Q-L01-11/Q-L02-08，P2）：桥侧帧特征的忠实变换面——
    loudness = min(1, rms/audio_ref_rms)（冻结归一常数，零新阈值纪律：不设
    \"什么算声音\"的感觉阈）；原始 PCM 永不进帧（只入桥证据侧 log）。"""

    loudness: float           # [0,1] 归一响度（忠实变换）
    rms: float                # 原始帧 RMS（int 采样域）
    zcr: float                # 过零率（0..1）
    peak: int                 # 峰值采样幅值
    duration_ms: int          # 帧时长（冻结 100ms）


@dataclass(frozen=True, slots=True)
class TesseraActFeatures:
    """Tessera 执行器状态特征（Q-L01-12②，P2）：自身执行器（LED/PWM）状态 = 本体感受。
    忠实变换面（值域原样承载，零新阈值）；原始遥测只入桥证据侧 log。"""

    dev: int                  # 设备号（板侧枚举）
    value_u: int              # 原始值域（板侧标度——禁主体侧换算）


FrameFeatures = ExtLocalObsFeatures | ExtEventFeatures | InteroSensations | ProprioFeatures | LanguageFeatures | AudioFeatures | TesseraActFeatures


@dataclass(frozen=True, slots=True)
class SensoryFrame:
    """感觉帧（L02 §4.1）：五元属性齐全；层级恒 SENSORY_FORMED（构造期守卫）。"""

    frame_id: str
    modality: SensoryModality
    source_received_ids: tuple[str, ...]
    effective_time: int
    formed_time: int
    alignment_offset: int
    alignment_confidence: "float | Unknown"
    calibration_version: str
    features: FrameFeatures
    quality: QualityMetrics
    gain: GainState
    uncertainty: tuple[Unknown, ...] = field(default=())
    revision_of: str | None = None      # 迟到 revision 引用旧帧（envelope 不可变，Q-L02-03）
    representation_level: RepresentationLevel = RepresentationLevel.SENSORY_FORMED
    content_digest: str = ""

    def __post_init__(self) -> None:
        if self.representation_level is not RepresentationLevel.SENSORY_FORMED:
            raise RepresentationEscalation(
                f"frame {self.frame_id}: representation_level must be SENSORY_FORMED,"
                f" got {self.representation_level}（L02 §2.2 纪律：永不 PERCEIVED）"
            )
        if not self.source_received_ids:
            raise SchemaViolation(f"frame {self.frame_id}: 禁匿名形成（L02 §8 不变量 3）")
        if not self.calibration_version:
            raise CalibrationMismatch(f"frame {self.frame_id}: calibration_version required")
        computed = _frame_digest(self)
        if self.content_digest and self.content_digest != computed:
            # 防篡改构造面：dataclasses.replace 复制陈旧 digest → 构造期即拒（S0，L02 §6）
            raise RepresentationEscalation(
                f"frame {self.frame_id}: content_digest mismatch（帧内容与声明 digest 不符——改写检出）"
            )
        object.__setattr__(self, "content_digest", computed)


def _frame_digest(frame: "SensoryFrame") -> str:
    """帧内容 digest（canonical JSON sha256；构造期自动计算，身份完整性）。

    asdict 递归展开 features/quality/uncertainty（Unknown 为 dataclass → dict；
    StrEnum 为 str 子类 → JSON 可序列化）。
    """
    from dataclasses import asdict

    from galatea.kernel.digest import content_digest

    payload = asdict(frame)
    payload.pop("content_digest", None)
    return content_digest(payload)


@dataclass(frozen=True, slots=True)
class GainReceipt:
    """增益回执（L02 §2.2/§4.4；C0 = 恒等回执，调制面 C2）。"""

    frame_id: str
    requested_gain: float
    applied_gain: float
    bound_check: str      # "IDENTITY_C0"（C0）；"CLIPPED" 归 C2
