#!/usr/bin/env bash
# Run the RCB ticket agent on this Mac (parallel to GitHub Actions if you use both).
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

echo "Starting RCB agent from $ROOT (Ctrl+C to stop). Logs also in agent.log"
exec python main.py
