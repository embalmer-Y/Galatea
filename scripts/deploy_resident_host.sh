#!/usr/bin/env bash
# Galatea 常驻融合服务部署（P2 产品化；Q-L13-16；目标主机 192.168.2.91）。
# 用法（开发机执行）：
#   bash scripts/deploy_resident_host.sh
# 前置：scripts/deploy_p1_host.sh 已完成基础部署（uv/git/evidence 面）；
#       本脚本追加：zenohd 二进制 + 三服务单元（zenohd/body-sim/resident）+ enable。
# 服务拓扑：galatea-zenohd(7447) ← galatea-body-sim(gbridge 体模拟源) ← galatea-resident(主体常驻)。
set -euo pipefail

HOST="${HOST:-emb@192.168.2.91}"
SSH="ssh -o BatchMode=yes $HOST"
SCP="scp -q"

echo "== ① 推送部署树（git archive HEAD + config/scripts 同步）"
git archive --format=tar.gz -o /tmp/galatea-head.tar.gz HEAD
$SCP /tmp/galatea-head.tar.gz "$HOST:/tmp/"
$SSH 'mkdir -p ~/project/galatea-service && tar -xzf /tmp/galatea-head.tar.gz -C ~/project/galatea-service'

echo "== ② zenohd 二进制（WSL tools → 主机）"
wsl.exe -e bash -lc 'cp ~/project/tools/zenohd /mnt/c/Users/y1985/AppData/Local/Temp/zenohd && echo ZENOHD_STAGED'
$SCP "C:/Users/y1985/AppData/Local/Temp/zenohd" "$HOST:/tmp/zenohd"
$SSH 'mkdir -p ~/project/tools && mv /tmp/zenohd ~/project/tools/zenohd && chmod +x ~/project/tools/zenohd && ~/project/tools/zenohd --version 2>&1 | head -1 || echo "zenohd missing（body-sim/resident 将连不上路由——检查②）"'

echo "== ③ venv（tessera extra：zenoh+cbor2）"
$SSH 'cd ~/project/galatea-service && export PATH=$HOME/.local/bin:$PATH && uv sync --extra tessera 2>&1 | tail -1'

echo "== ④ 服务单元安装 + enable"
$SCP scripts/deploy/galatea-zenohd.service scripts/deploy/galatea-body-sim.service scripts/deploy/galatea-resident.service "$HOST:/tmp/"
$SSH 'echo "'"${SUDO_PW:-root}"'" | sudo -S cp /tmp/galatea-*.service /etc/systemd/system/ 2>/dev/null | cat; echo "'"${SUDO_PW:-root}"'" | sudo -S systemctl daemon-reload; echo "'"${SUDO_PW:-root}"'" | sudo -S systemctl enable --now galatea-zenohd.service galatea-body-sim.service galatea-resident.service 2>&1 | tail -3'

echo "== ⑤ 状态核验"
sleep 3
$SSH 'systemctl is-active galatea-zenohd galatea-body-sim galatea-resident; systemctl is-enabled galatea-zenohd galatea-body-sim galatea-resident'
echo "== 部署完成"
