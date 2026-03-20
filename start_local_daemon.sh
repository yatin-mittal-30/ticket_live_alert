#!/usr/bin/env bash
# Start the RCB agent in the background with caffeinate (stay awake).
# Logs: logs/agent.log (daily rotation), logs/checks.jsonl (one JSON per check), logs/daemon.out (stdout/stderr).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PID_FILE="$ROOT/.agent.pid"
OUT_LOG="$ROOT/logs/daemon.out"

mkdir -p "$ROOT/logs"

if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "${PID:-}" ]] && kill -0 "$PID" 2>/dev/null; then
    echo "Agent already running (PID $PID). Stop with: ./stop_local_daemon.sh"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

if [[ ! -f .env ]]; then
  echo "Missing .env — copy .env.example to .env first."
  exit 1
fi

if [[ ! -d .venv ]]; then
  echo "No .venv — run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && playwright install chromium"
  exit 1
fi

nohup "$ROOT/run_local_stay_awake.sh" >>"$OUT_LOG" 2>&1 &
echo $! >"$PID_FILE"

echo "Started RCB agent (PID $(cat "$PID_FILE"))."
echo "  Human log:    $ROOT/logs/agent.log (rotates daily, 14 days kept)"
echo "  Check lines:  $ROOT/logs/checks.jsonl"
echo "  Shell output: $OUT_LOG"
echo "Stop: $ROOT/stop_local_daemon.sh   Status: $ROOT/status_local_daemon.sh"
