#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-}"
REMOTE_USER="${REMOTE_USER:-}"
REMOTE_PASS="${REMOTE_PASS:-}"
REMOTE_DIR="${REMOTE_DIR:-}"

usage() {
  echo "Usage: $0 [--host H] [--user U] [--password P] [--remote-dir D]"
  echo "Example:"
  echo "  $0 --host 192.168.100.119 --user seeed --password seeed --remote-dir /home/seeed/hardware_test_platform"
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
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "[ERROR] Unexpected argument: $1"
      usage
      exit 1 ;;
  esac
done

if [[ -z "$REMOTE_HOST" || -z "$REMOTE_USER" || -z "$REMOTE_PASS" || -z "$REMOTE_DIR" ]]; then
  echo "[ERROR] 请先设置 REMOTE_HOST / REMOTE_USER / REMOTE_PASS / REMOTE_DIR，或通过参数显式传入"
  exit 2
fi

REMOTE_PROJECT_ROOT="${REMOTE_DIR}"

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
echo "== project root =="
ls -la '${REMOTE_PROJECT_ROOT}' | head -n 20
echo
echo "== venv =="
test -x '${REMOTE_DIR}/venv/bin/python' && echo 'venv ready' || echo 'venv missing'
echo
echo "== latest reports =="
ls -1t '${REMOTE_PROJECT_ROOT}/reports'/* 2>/dev/null | head -n 10 || true
EOF