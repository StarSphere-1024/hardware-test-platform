#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-}"
REMOTE_USER="${REMOTE_USER:-}"
REMOTE_PASS="${REMOTE_PASS:-}"
REMOTE_DIR="${REMOTE_DIR:-}"
OUTPUT_DIR="remote-artifacts/latest"

usage() {
  echo "Usage: $0 [--host H] [--user U] [--password P] [--remote-dir D] [--output-dir O]"
  echo "Examples:"
  echo "  $0"
  echo "  $0 --host 192.168.100.119 --user seeed --password seeed --remote-dir /home/seeed/hardware_test_platform"
  echo "  $0 --output-dir remote-artifacts/rk3576_smoke_01"
}

if ! command -v sshpass >/dev/null 2>&1; then
  echo "[ERROR] sshpass 未安装"
  exit 2
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      REMOTE_HOST="$2"; shift 2 ;;
    --user)
      REMOTE_USER="$2"; shift 2 ;;
    --password|--pass)
      REMOTE_PASS="$2"; shift 2 ;;
    --remote-dir)
      REMOTE_DIR="$2"; shift 2 ;;
    --output-dir)
      OUTPUT_DIR="$2"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      OUTPUT_DIR="$1"; shift ;;
  esac
done

if [[ -z "$REMOTE_HOST" || -z "$REMOTE_USER" || -z "$REMOTE_PASS" || -z "$REMOTE_DIR" ]]; then
  echo "[ERROR] 请先设置 REMOTE_HOST / REMOTE_USER / REMOTE_PASS / REMOTE_DIR，或通过参数显式传入"
  exit 2
fi

mkdir -p "$OUTPUT_DIR"
REMOTE_PROJECT_ROOT="${REMOTE_DIR}"

for artifact in reports logs tmp; do
  echo "[INFO] 拉取 ${artifact}/"
  sshpass -p "$REMOTE_PASS" scp -o StrictHostKeyChecking=no -r \
    "$REMOTE_USER@$REMOTE_HOST:${REMOTE_PROJECT_ROOT}/${artifact}" "$OUTPUT_DIR/" 2>/dev/null || true
done

echo "[INFO] 已回传到 ${OUTPUT_DIR}"