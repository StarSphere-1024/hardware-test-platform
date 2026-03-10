#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-}"
REMOTE_USER="${REMOTE_USER:-}"
REMOTE_PASS="${REMOTE_PASS:-}"
REMOTE_DIR="${REMOTE_DIR:-}"

usage() {
  echo "Usage: $0 [--host H] [--user U] [--password P] [--remote-dir D] <case-name|case-path>"
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

if [[ -z "$REMOTE_HOST" || -z "$REMOTE_USER" || -z "$REMOTE_PASS" || -z "$REMOTE_DIR" ]]; then
  echo "[ERROR] 请先设置 REMOTE_HOST / REMOTE_USER / REMOTE_PASS / REMOTE_DIR，或通过参数显式传入"
  exit 2
fi

if [[ -z "$CASE_INPUT" ]]; then
  usage
  exit 1
fi

if [[ "$CASE_INPUT" == *.json || "$CASE_INPUT" == cases/* ]]; then
  CASE_PATH="$CASE_INPUT"
else
  if [[ -f "cases/${CASE_INPUT}.json" ]]; then
    CASE_PATH="cases/${CASE_INPUT}.json"
  else
    mapfile -t CASE_MATCHES < <(find cases -type f -name "${CASE_INPUT}.json" | sort)
    if [[ ${#CASE_MATCHES[@]} -eq 1 ]]; then
      CASE_PATH="${CASE_MATCHES[0]}"
    elif [[ ${#CASE_MATCHES[@]} -gt 1 ]]; then
      echo "[ERROR] case 名称不唯一，请使用完整路径: ${CASE_INPUT}"
      printf '  %s\n' "${CASE_MATCHES[@]}"
      exit 1
    else
      CASE_PATH="cases/${CASE_INPUT}.json"
    fi
  fi
fi

REMOTE_PROJECT_ROOT="${REMOTE_DIR}"
REMOTE_COMMAND="cd '${REMOTE_PROJECT_ROOT}' && '${REMOTE_DIR}/venv/bin/python' -m framework.cli.run_case --workspace-root '${REMOTE_PROJECT_ROOT}' --artifacts-root '${REMOTE_PROJECT_ROOT}' --config '${CASE_PATH}'"

echo "[INFO] 远程执行 case: ${CASE_PATH}"
sshpass -p "$REMOTE_PASS" ssh -o StrictHostKeyChecking=no "$REMOTE_USER@$REMOTE_HOST" "$REMOTE_COMMAND"

echo "[INFO] 最近报告文件:"
sshpass -p "$REMOTE_PASS" ssh -o StrictHostKeyChecking=no "$REMOTE_USER@$REMOTE_HOST" "cd '${REMOTE_PROJECT_ROOT}' && ls -1t reports/* 2>/dev/null | head -n 10 || true"