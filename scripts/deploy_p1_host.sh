#!/usr/bin/env bash
# Galatea P1 主机部署脚本（ADR-G-0025 §5；H1 移交"可复现发布"兑现面）。
# 用法（主机 192.168.2.91 上执行）：
#   1) 开发机推送两段式载荷（缺一即 evidence 依赖测试失败——INC/探针发现①）：
#        git archive --format=tar.gz -o /tmp/galatea-head.tar.gz HEAD
#        tar -czf /tmp/galatea-evidence.tar.gz evidence
#        scp /tmp/galatea-head.tar.gz /tmp/galatea-evidence.tar.gz emb@192.168.2.91:/tmp/
#   2) 主机执行：bash scripts/deploy_p1_host.sh [--skip-tests]
# 义务面（探针①三项供应发现）：
#   - PATH：uv 须在 PATH（非交互 SSH 无 ~/.local/bin——测试子进程 spawn uv 依赖）
#   - git：static_reports 生成器 spawn git（apt install git）
#   - evidence 数据面：本脚本强校验（缺失即退出非 0）
set -euo pipefail

STAGING="${STAGING:-/tmp}"
TARGET="${TARGET:-$HOME/galatea}"
SKIP_TESTS=false
[[ "${1:-}" == "--skip-tests" ]] && SKIP_TESTS=true

need() { command -v "$1" >/dev/null 2>&1 || { echo "DEPLOY_FAIL: missing '$1' ($2)" >&2; exit 1; }; }

echo "== P1 部署开始（target=$TARGET staging=$STAGING）"

# ① 供应义务核查（fail fast）
need uv  "PATH 义务：export PATH=\$HOME/.local/bin:\$PATH（探针发现②）"
need git "主机 git 缺失：sudo apt install -y git（探针发现③——static_reports spawn git）"

# ② 载荷核查（两段式缺一不可）
for artifact in galatea-head.tar.gz galatea-evidence.tar.gz; do
  [[ -f "$STAGING/$artifact" ]] || { echo "DEPLOY_FAIL: $STAGING/$artifact 缺失（两段式载荷义务）" >&2; exit 1; }
done

# ③ 提取（代码 + evidence 数据面）
mkdir -p "$TARGET"
tar -xzf "$STAGING/galatea-head.tar.gz" -C "$TARGET"
tar -xzf "$STAGING/galatea-evidence.tar.gz" -C "$TARGET"
[[ -d "$TARGET/evidence" ]] || { echo "DEPLOY_FAIL: evidence 数据面未就位" >&2; exit 1; }
echo "载荷就位：$(find "$TARGET/evidence" -type f | wc -l) 个 evidence 文件"

# ④ 环境同步（Python 3.12.13 钉版由 uv 托管）
(cd "$TARGET" && uv sync --frozen)   # require-hashes 强化（Q-L13-15⑤）：仅按锁安装，漂移即拒
echo "venv 就绪：$("$TARGET/.venv/bin/python" --version)"

# ⑤ 基线判据（部署就绪 = pytest 全绿；ADR-G-0025 §5）
if $SKIP_TESTS; then
  echo "跳过基线（--skip-tests）——部署不完整，禁用于评价运行"
else
  (cd "$TARGET" && uv run pytest -p no:cacheprovider 2>&1 | tail -1)
fi
echo "== P1 部署完成"
