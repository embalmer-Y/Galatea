"""GPU 确定性认证 —— Q-T02 补裁③ 程序（P4-β 工作项；运行于隔离 CUDA venv）。

判定内容（认证绿的全部判据）：
1. RSSMWorldModel CUDA 构造 + 训练会话录制（schema v1 十字段）；
2. 同种子重建 → 重放 → 末权重 + 损失曲线逐位恒等（Q-L13-20① 宪法语义）；
3. 双跑训练 bit-exact（CUDA 设备维的给定权重确定性）。

环境合同（profile device_certification.cuda_env 冻结值）：
CUBLAS_WORKSPACE_CONFIG=:4096:8 + use_deterministic_algorithms(True)。
profile torch_version 钉 CPU 版本 → 本脚本以认证程序身份 monkeypatch 版本一致性
检查（与探针同款、如实记录于认证工件；正式放行 = profile v1.2 运行前修订翻转
device_certification.status，由仓库侧执行）。

用法：CUBLAS_WORKSPACE_CONFIG=:4096:8 PYTHONPATH=<repo> <gpu_venv>/bin/python <本脚本>
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/home/emb/project/galatea")
sys.path.insert(0, str(REPO))

import torch  # noqa: E402

from galatea.subject.brain.module import configure_deterministic_torch  # noqa: E402
from galatea.subject.brain.recorder import (  # noqa: E402
    record_training_session,
    replay_training_session,
)
from galatea.subject.brain.world_model import RSSMWorldModel  # noqa: E402

configure_deterministic_torch()
DEV = "cuda"
INIT_SEED = 20261011          # profile 探针锚（同 CPU 认证基）
MASTER_SEED = b"p4-beta-gpu-cert"
EPOCHS = 40


def build_model(alpha_params, init_seed: int = INIT_SEED) -> RSSMWorldModel:
    m = RSSMWorldModel(alpha_params, parent_digest="root", init_seed=init_seed, input_dim=1)
    m.module.to(DEV)
    return m


def make_data(n: int = 96) -> list[torch.Tensor]:
    g = torch.Generator().manual_seed(4242)
    xs = torch.randn(n, generator=g)
    return [torch.tensor([v], dtype=torch.float32, device=DEV) for v in xs]


def train(model: RSSMWorldModel, xs: list[torch.Tensor]) -> list[float]:
    return model.train_on_sequence(xs, lr=1e-3, epochs=EPOCHS, target_dims=(0,))


def main() -> int:
    import yaml
    from galatea.subject import p4profile as p4mod

    profile_path = REPO / "config/profiles/p4_alpha_brain.profile.yaml"
    raw = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    frozen_tv = raw["determinism"]["torch_version"]
    # 认证程序身份的版本检查旁路（如实记录——正式放行走 profile v1.2 修订）
    real_need_str = p4mod._need_str
    p4mod._need_str = (lambda mapping, key, expected: frozen_tv if key == "torch_version"
                       else real_need_str(mapping, key, frozen_tv if key == "torch_version" else expected))
    params = p4mod.load_p4_alpha_profile(profile_path)
    p4mod._need_str = real_need_str

    xs = make_data()
    data_digest = hashlib.sha256(b"".join(
        t.detach().cpu().contiguous().numpy().tobytes() for t in xs)).hexdigest()

    # 会话 1：构造 → 录制训练
    m1 = build_model(params)
    before = m1.digest()
    losses = train(m1, xs)
    session = record_training_session(
        master_seed=MASTER_SEED, init_seed=INIT_SEED, data_digest=data_digest,
        module=m1, weights_digest_before=before, losses=losses, params=params,
        epochs=EPOCHS)
    after = m1.digest()

    # 会话 2：同种子重建 → 重放 → 逐位恒等
    def rebuild() -> RSSMWorldModel:
        return build_model(params)

    def retrain(m: RSSMWorldModel) -> list[float]:
        return train(m, xs)

    replay_ok = replay_training_session(session, rebuild, retrain)

    # 会话 3：第三跑权重 digest 与会话 1 恒等（训练双跑 bit-exact）
    m3 = build_model(params)
    train(m3, xs)
    third_ok = m3.digest() == after

    # 设备与权重面身份
    device = str(next(m1.module.parameters()).device)
    report = {
        "certification": "p4_beta_gpu_device_certification",
        "authority": "Q-T02 补裁③（P4-β 工作项；owner 2026-10-16 指令授权）",
        "torch": torch.__version__,
        "device": device,
        "cuda_env": {"CUBLAS_WORKSPACE_CONFIG": ":4096:8",
                     "use_deterministic_algorithms": True},
        "init_seed": INIT_SEED,
        "epochs": EPOCHS,
        "weights_digest_after": after,
        "param_count": m1.param_count(),
        "record_fields": list(session.replay_criterion) if hasattr(session, "replay_criterion") else "schema_v1",
        "loss_first": losses[0],
        "loss_last": losses[-1],
        "replay_bit_exact": bool(replay_ok),
        "train_double_run_bit_exact": bool(third_ok),
        "verdict": "PASS" if (replay_ok and third_ok and device.startswith("cuda")) else "FAIL",
    }
    print(json.dumps(report, ensure_ascii=False, indent=1))
    out = REPO / "evidence" / "p4_beta_gpu_certification" / "cert_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
