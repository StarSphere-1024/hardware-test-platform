#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-192.168.100.91}"
REMOTE_USER="${REMOTE_USER:-seeed}"
REMOTE_PASS="${REMOTE_PASS:-seeed}"
REMOTE_DIR="${REMOTE_DIR:-/home/seeed/hardware_test}"
OUTPUT_DIR="${1:-remote-artifacts/latest}"

if ! command -v sshpass >/dev/null 2>&1; then
  echo "[ERROR] sshpass 未安装"
  exit 2
fi

mkdir -p "$OUTPUT_DIR"
REMOTE_WORKSPACE="${REMOTE_DIR}/workspace"

for artifact in reports logs tmp; do
  echo "[INFO] 拉取 ${artifact}/"
  sshpass -p "$REMOTE_PASS" scp -o StrictHostKeyChecking=no -r \
    "$REMOTE_USER@$REMOTE_HOST:${REMOTE_WORKSPACE}/${artifact}" "$OUTPUT_DIR/" 2>/dev/null || true
done

echo "[INFO] 已回传到 ${OUTPUT_DIR}"