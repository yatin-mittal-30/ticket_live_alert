#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$ROOT/.agent.pid"

_kill_and_wait() {
  local pid=$1 max_wait=${2:-15}
  kill "$pid" 2>/dev/null || return 0
  echo "Sent SIGTERM to PID $pid, waiting up to ${max_wait}s..."
  local waited=0
  while kill -0 "$pid" 2>/dev/null && (( waited < max_wait )); do
    sleep 1
    (( waited++ ))
  done
  if kill -0 "$pid" 2>/dev/null; then
    echo "PID $pid still alive after ${max_wait}s — sending SIGKILL."
    kill -9 "$pid" 2>/dev/null || true
    sleep 1
  fi
  echo "PID $pid stopped."
}

# Kill any orphan main.py processes not tracked by PID file.
_kill_orphans() {
  local tracked_pid="${1:-}"
  for pid in $(pgrep -f "python.*main\.py" 2>/dev/null || true); do
    [[ "$pid" == "$tracked_pid" ]] && continue
    echo "Killing orphan main.py (PID $pid)."
    kill "$pid" 2>/dev/null || true
  done
}

if [[ ! -f "$PID_FILE" ]]; then
  echo "No PID file — checking for orphan processes."
  _kill_orphans ""
  exit 0
fi

PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  _kill_and_wait "$PID"
else
  echo "Process $PID not running; removing stale PID file."
fi

_kill_orphans "$PID"
rm -f "$PID_FILE"
