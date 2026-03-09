#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-192.168.100.91}"
REMOTE_USER="${REMOTE_USER:-seeed}"
REMOTE_PASS="${REMOTE_PASS:-seeed}"
REMOTE_DIR="${REMOTE_DIR:-/home/seeed/hardware_test}"
REQUEST_ID="req-remote-$(date +%s)-$RANDOM"

usage() {
  echo "Usage: $0 [--host H] [--user U] [--password P] [--remote-dir D] [fixture-name|fixture-path]"
  echo "Examples:"
  echo "  $0 rk3576_smoke"
  echo "  $0 fixtures/rk3576_smoke.json"
}

if ! command -v sshpass >/dev/null 2>&1; then
  echo "[ERROR] sshpass 未安装"
  exit 2
fi

FIXTURE_INPUT="rk3576_smoke"
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
      FIXTURE_INPUT="$1"; shift ;;
  esac
done

if [[ "$FIXTURE_INPUT" == *.json || "$FIXTURE_INPUT" == fixtures/* ]]; then
  FIXTURE_PATH="$FIXTURE_INPUT"
else
  FIXTURE_PATH="fixtures/${FIXTURE_INPUT}.json"
fi

REMOTE_WORKSPACE="${REMOTE_DIR}/workspace"
REMOTE_EVENT_PATH="${REMOTE_WORKSPACE}/logs/events/${REQUEST_ID}.jsonl"
REMOTE_SNAPSHOT_PATH="${REMOTE_WORKSPACE}/tmp/${REQUEST_ID}_snapshot.json"
REMOTE_STDOUT_PATH="${REMOTE_WORKSPACE}/tmp/${REQUEST_ID}_stdout.log"

echo "[INFO] 远程执行 fixture: ${FIXTURE_PATH}"
echo "[INFO] request_id: ${REQUEST_ID}"
sshpass -p "$REMOTE_PASS" ssh -o StrictHostKeyChecking=no "$REMOTE_USER@$REMOTE_HOST" <<EOF
set -u
cd '${REMOTE_WORKSPACE}'
mkdir -p logs/events tmp reports
rm -f '${REMOTE_EVENT_PATH}' '${REMOTE_SNAPSHOT_PATH}' '${REMOTE_STDOUT_PATH}'
PYTHONUNBUFFERED=1 '${REMOTE_DIR}/venv/bin/python' -m framework.cli.run_fixture \
  --request-id '${REQUEST_ID}' \
  --workspace-root '${REMOTE_WORKSPACE}' \
  --artifacts-root '${REMOTE_WORKSPACE}' \
  --config '${FIXTURE_PATH}' \
  --dashboard > '${REMOTE_STDOUT_PATH}' 2>&1 &
fixture_pid=\$!
last_event_line=0
last_heartbeat_ts=0
last_heartbeat_key=""

cleanup_fixture() {
  if kill -0 "\$fixture_pid" 2>/dev/null; then
    kill "\$fixture_pid" 2>/dev/null || true
    wait "\$fixture_pid" 2>/dev/null || true
  fi
}

trap cleanup_fixture INT TERM HUP

print_new_events() {
  if [[ ! -f '${REMOTE_EVENT_PATH}' ]]; then
    return
  fi
  event_output=\$(python3 - '${REMOTE_EVENT_PATH}' "\$last_event_line" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
last_line = int(sys.argv[2])
lines = path.read_text(encoding='utf-8').splitlines()
for index, line in enumerate(lines[last_line:], start=last_line + 1):
    record = json.loads(line)
    event = record.get('event', {})
    event_type = event.get('event_type', '-')
    task_name = event.get('task_name') or event.get('task_id') or '-'
    status = event.get('status_after') or event.get('status') or '-'
    message = event.get('message') or ''
    print(f"[EVENT {index}] {event_type} {task_name} {status} {message}".rstrip())
print(f"__LAST_LINE__={len(lines)}")
PY
)
  if [[ -z "\$event_output" ]]; then
    return
  fi
  printf '%s\n' "\$event_output" | grep -v '^__LAST_LINE__=' || true
  last_line_marker=\$(printf '%s\n' "\$event_output" | grep '^__LAST_LINE__=' | tail -n 1 || true)
  if [[ -n "\$last_line_marker" ]]; then
    last_event_line="\${last_line_marker#__LAST_LINE__=}"
  fi
}

print_heartbeat() {
  if [[ ! -f '${REMOTE_SNAPSHOT_PATH}' ]]; then
    return
  fi
  heartbeat_output=\$(python3 - '${REMOTE_SNAPSHOT_PATH}' <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
snapshot = json.loads(path.read_text(encoding='utf-8'))
cases = []
for case in snapshot.get('cases', []):
    cases.append(f"{case.get('name', '-')}: {case.get('status', '-')}")
overall = snapshot.get('current_status', '-')
updated = snapshot.get('updated_at', '-')
joined = ', '.join(cases) if cases else 'no-cases-yet'
print(f"__HEARTBEAT_KEY__={overall};{joined}")
print(f"[HEARTBEAT] {updated} overall={overall}; cases={joined}")
PY
)
  if [[ -z "\$heartbeat_output" ]]; then
    return
  fi
  heartbeat_key=\$(printf '%s\n' "\$heartbeat_output" | grep '^__HEARTBEAT_KEY__=' | tail -n 1 || true)
  heartbeat_line=\$(printf '%s\n' "\$heartbeat_output" | grep -v '^__HEARTBEAT_KEY__=' | tail -n 1 || true)
  if [[ -n "\$heartbeat_key" ]]; then
    heartbeat_key="\${heartbeat_key#__HEARTBEAT_KEY__=}"
  fi
  if [[ -n "\$heartbeat_line" && "\$heartbeat_key" != "\$last_heartbeat_key" ]]; then
    printf '%s\n' "\$heartbeat_line"
    last_heartbeat_key="\$heartbeat_key"
  fi
}

while kill -0 "\$fixture_pid" 2>/dev/null; do
  print_new_events
  now_ts=\$(date +%s)
  if (( now_ts - last_heartbeat_ts >= 5 )); then
    print_heartbeat
    last_heartbeat_ts=\$now_ts
  fi
  sleep 1
done

set +e
wait "\$fixture_pid"
fixture_exit=\$?
set -e
trap - INT TERM HUP
print_new_events
if [[ -f '${REMOTE_STDOUT_PATH}' ]]; then
  cat '${REMOTE_STDOUT_PATH}'
fi
exit "\$fixture_exit"
EOF

echo "[INFO] 最近报告文件:"
sshpass -p "$REMOTE_PASS" ssh -o StrictHostKeyChecking=no "$REMOTE_USER@$REMOTE_HOST" "cd '${REMOTE_WORKSPACE}' && ls -1t reports/* 2>/dev/null | head -n 20 || true"