# RCB Ticket Alert Agent

Monitors the [RCB ticket shop](https://shop.royalchallengers.com/ticket) and sends instant alerts via **Telegram** and **Slack** when match tickets go live.

## Current Target Matches

| Match | Date |
|-------|------|
| RCB vs SRH (Sunrisers Hyderabad) | March 28, 2026 |
| RCB vs CSK (Chennai Super Kings) | April 5, 2026 |

Edit `config.py` → `TARGET_MATCHES` to add more as they're announced.

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Create a Telegram Bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot`, follow the prompts, and copy the **bot token**
3. Start a chat with your new bot and send any message
4. Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser
5. Find `"chat":{"id": 123456789}` in the response — that's your **chat ID**

### 3. Slack bot (not webhook)

Create a Slack app with a **Bot User OAuth Token** (`xoxb-...`) and invite the bot to your channel. Put the token and channel ID in `.env` (see `.env.example`).

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=123456789
SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNEL_ID=C0XXXXXXXXX
CHECK_INTERVAL_SECONDS=90
```

### 5. Run the agent locally

**One-time (foreground — stops if you close the terminal):**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
./run_local.sh
```

Or: `source .venv/bin/activate && python main.py`

**Keep the Mac awake while the agent runs** (next ~48h at home, **plugged in**, lid open or clamshell + monitor):

```bash
./run_local_stay_awake.sh
```

Uses macOS `caffeinate` so **idle sleep is blocked** for as long as this process runs. Full checklist: [MAC_STAY_AWAKE.md](MAC_STAY_AWAKE.md).

**Background daemon + logs** (recommended for 24–48h; survives closing Terminal):

```bash
./start_local_daemon.sh          # start (uses caffeinate + nohup)
./status_local_daemon.sh         # running? tail of log
./stop_local_daemon.sh           # stop
```

Logs (not committed to git):

| File | What |
|------|------|
| `logs/agent.log` | Full log; **rotates daily**, keeps **14** days |
| `logs/checks.jsonl` | **One JSON line per check** (timestamp, scrape_ok, tickets_found, summary) |
| `logs/daemon.out` | Stdout/stderr from the shell wrapper |

**Keep running after you close Terminal** (still stops if the Mac sleeps — see below):

```bash
cd /path/to/ticket_booking_agent
nohup ./run_local_stay_awake.sh >> agent_nohup.log 2>&1 &
echo $!   # save this PID to kill later: kill <PID>
```

**Parallel with GitHub Actions:** safe to run both; when tickets go live you may get **duplicate** Telegram/Slack alerts (one from CI, one from this Mac). That is intentional redundancy while schedules are unreliable.

### When the local agent stops or “drops”

| Situation | What happens |
|-----------|----------------|
| **Close Terminal** (no `nohup`/`tmux`) | Process gets **SIGHUP** and exits |
| **Ctrl+C** in that terminal | **SIGINT** → graceful stop after current sleep/check |
| **Mac sleeps** (lid closed, Energy Saver) | Networking and scheduling pause; checks **do not run** until wake |
| **Logout / restart / shutdown** | Process **dies** |
| **Kill Terminal app / Force Quit** | Process **dies** |
| **`kill <pid>`** (default TERM) | **SIGTERM** → same as Ctrl+C path |
| **Wi‑Fi / internet down** | Scrapes fail; agent **logs errors and keeps going** after retries |
| **Playwright / Chromium crash** | Usually caught per-check; loop **continues** next interval |
| **Uncaught Python exception** | Process **exits** (rare if deps OK) |
| **Out of memory** | macOS may **kill** the process |
| **Battery dies / hard power off** | Process **dies** |

**Tip:** In **System Settings → Battery → Options**, disable or relax **“Put hard disks to sleep”** / use **“Prevent automatic sleeping when display is off”** on power adapter if you want fewer gaps while plugged in (still not as reliable as cloud).

The agent will:
- Check the ticket page every ~90 seconds
- Log every check to console and `agent.log`
- Save screenshots to `screenshots/`
- Send Telegram + Slack alerts when tickets are detected
- Track matches individually — you get alerted for each new batch

## How Detection Works

The agent renders the JavaScript-heavy RCB shop page using a headless browser and looks for:

- **Match keywords**: SRH, CSK, Sunrisers, Chennai, dates
- **Action keywords**: "buy now", "book now", "add to cart"
- **Venue signals**: Chinnaswamy, stand names, price patterns
- **Content growth**: significant increase in page text length

Alerts fire only when **new matches** appear, so you won't get spammed about matches you already know about.

## File Structure

```
main.py                  — Entry point, scheduler loop
run_local_stay_awake.sh  — Foreground + caffeinate
start_local_daemon.sh    — Background (nohup + .agent.pid)
stop_local_daemon.sh     / status_local_daemon.sh
logs/agent.log           — Daily rotating log (runtime)
logs/checks.jsonl        — One JSON line per check (runtime)
scraper.py               — Playwright browser automation
detector.py              — Ticket detection logic
notifier.py              — Telegram + Slack alert senders
config.py                — Configuration and env loading
.env.example             — Environment variable template
```
