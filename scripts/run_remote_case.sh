#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-192.168.100.91}"
REMOTE_USER="${REMOTE_USER:-seeed}"
REMOTE_PASS="${REMOTE_PASS:-seeed}"
REMOTE_DIR="${REMOTE_DIR:-/home/seeed/hardware_test}"
BOARD_PROFILE="${BOARD_PROFILE:-${REMOTE_BOARD_PROFILE:-rk3576}}"

usage() {
  echo "Usage: $0 [--host H] [--user U] [--password P] [--remote-dir D] [--board-profile B] <case-name|case-path>"
  echo "Examples:"
  echo "  $0 gpio_case"
  echo "  $0 cases/linux_host_pc/eth_case.json"
}

if ! command -v sshpass >/dev/null 2>&1; then
  echo "[ERROR] sshpass 未安装"
  exit 2
fi

CASE_INPUT=""
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
    --board-profile)
      BOARD_PROFILE="$2"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      if [[ -z "$CASE_INPUT" ]]; then
        CASE_INPUT="$1"
        shift
      else
        echo "[ERROR] Unexpected argument: $1"
        usage
        exit 1
      fi
      ;;
  esac
done

if [[ -z "$CASE_INPUT" ]]; then
  usage
  exit 1
fi

if [[ "$CASE_INPUT" == *.json || "$CASE_INPUT" == cases/* ]]; then
  CASE_PATH="$CASE_INPUT"
else
  if [[ -f "cases/${CASE_INPUT}.json" ]]; then
    CASE_PATH="cases/${CASE_INPUT}.json"
  elif [[ -f "cases/${BOARD_PROFILE}/${CASE_INPUT}.json" ]]; then
    CASE_PATH="cases/${BOARD_PROFILE}/${CASE_INPUT}.json"
  else
    CASE_PATH="cases/${CASE_INPUT}.json"
  fi
fi

REMOTE_WORKSPACE="${REMOTE_DIR}/workspace"
REMOTE_COMMAND="cd '${REMOTE_WORKSPACE}' && '${REMOTE_DIR}/venv/bin/python' -m framework.cli.run_case --workspace-root '${REMOTE_WORKSPACE}' --artifacts-root '${REMOTE_WORKSPACE}' --board-profile '${BOARD_PROFILE}' --config '${CASE_PATH}'"

echo "[INFO] 远程执行 case: ${CASE_PATH}"
sshpass -p "$REMOTE_PASS" ssh -o StrictHostKeyChecking=no "$REMOTE_USER@$REMOTE_HOST" "$REMOTE_COMMAND"

echo "[INFO] 最近报告文件:"
sshpass -p "$REMOTE_PASS" ssh -o StrictHostKeyChecking=no "$REMOTE_USER@$REMOTE_HOST" "cd '${REMOTE_WORKSPACE}' && ls -1t reports/* 2>/dev/null | head -n 10 || true"