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

echo "Starting RCB agent with caffeinate (system idle sleep blocked while this runs)."
echo "Project: $ROOT — logs: logs/agent.log"
echo "Plug in power; keep lid open unless using clamshell + monitor + power. Ctrl+C to stop."
if [[ "${ALLOW_DISPLAY_SLEEP:-0}" == "1" ]]; then
  echo "ALLOW_DISPLAY_SLEEP=1 → screen may turn off; Mac stays awake (needs power + Battery settings)."
else
  echo "Tip: overnight with lights off → ALLOW_DISPLAY_SLEEP=1 ./run_local_stay_awake.sh"
fi
echo ""

# -i system idle sleep  -d block DISPLAY sleep (omit if ALLOW_DISPLAY_SLEEP=1)
# -m disk idle sleep  -s system sleep on AC  -u user active
if [[ "${ALLOW_DISPLAY_SLEEP:-0}" == "1" ]]; then
  exec caffeinate -imsu python main.py
else
  exec caffeinate -dimsu python main.py
fi
