#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$ROOT/.agent.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "Status: not running (no .agent.pid)"
  exit 1
fi

PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  echo "Status: running (PID $PID)"
  echo "Log tail:"
  tail -n 5 "$ROOT/logs/agent.log" 2>/dev/null || echo "  (no agent.log yet)"
else
  echo "Status: stale PID file ($PID not running)"
  exit 1
fi
