#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-192.168.100.91}"
REMOTE_USER="${REMOTE_USER:-seeed}"
REMOTE_PASS="${REMOTE_PASS:-seeed}"
REMOTE_DIR="${REMOTE_DIR:-/home/seeed/hardware_test}"

if ! command -v sshpass >/dev/null 2>&1; then
  echo "[ERROR] sshpass 未安装"
  exit 2
fi

REMOTE_WORKSPACE="${REMOTE_DIR}/workspace"

sshpass -p "$REMOTE_PASS" ssh -o StrictHostKeyChecking=no "$REMOTE_USER@$REMOTE_HOST" <<EOF
set -e
echo "== whoami =="
whoami
echo
echo "== python =="
python3 --version
echo
echo "== disk =="
df -h '${REMOTE_DIR}' || df -h /
echo
echo "== workspace =="
ls -la '${REMOTE_WORKSPACE}' | head -n 20
echo
echo "== venv =="
test -x '${REMOTE_DIR}/venv/bin/python' && echo 'venv ready' || echo 'venv missing'
echo
echo "== latest reports =="
ls -1t '${REMOTE_WORKSPACE}/reports'/* 2>/dev/null | head -n 10 || true
EOF