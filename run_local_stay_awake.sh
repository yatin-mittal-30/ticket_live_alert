#!/usr/bin/env bash
# Run the agent with macOS caffeinate so the machine does not idle-sleep while this runs.
# Best with: power adapter plugged in, lid open (or clamshell + external display + power).
# Stop with Ctrl+C (stops caffeinate + Python together).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Missing .env — copy .env.example to .env and add Telegram + Slack values."
  exit 1
fi

if [[ ! -d .venv ]]; then
  echo "No .venv found. Run once:"
  echo "  python3 -m venv .venv"
  echo "  source .venv/bin/activate && pip install -r requirements.txt && playwright install chromium"
  exit 1
fi

# shellcheck source=/dev/null
source .venv/bin/activate
export HEADLESS="${HEADLESS:-true}"

echo "Starting RCB agent with caffeinate (idle sleep blocked while this runs)."
echo "Project: $ROOT — logs: agent.log"
echo "Plug in power; keep lid open unless using clamshell + monitor + power. Ctrl+C to stop."
echo ""

# -i idle sleep  -d display sleep  -m disk sleep  -s sleep on AC (when on adapter)  -u user active
exec caffeinate -dimsu python main.py
