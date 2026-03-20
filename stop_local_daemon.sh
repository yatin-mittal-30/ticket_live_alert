#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$ROOT/.agent.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "No PID file — agent may not be running."
  exit 1
fi

PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  echo "Sent SIGTERM to PID $PID (agent should exit after current step)."
else
  echo "Process $PID not running; removing stale PID file."
fi

rm -f "$PID_FILE"
