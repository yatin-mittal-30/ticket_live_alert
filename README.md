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

### 3. Create a Slack Incoming Webhook

1. Go to [Slack API: Incoming Webhooks](https://api.slack.com/messaging/webhooks)
2. Create a new webhook for your workspace and channel
3. Copy the **webhook URL**

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=123456789
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T.../B.../xxx
CHECK_INTERVAL_SECONDS=90
```

### 5. Run the agent

```bash
python main.py
```

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
main.py          — Entry point, scheduler loop
scraper.py       — Playwright browser automation
detector.py      — Ticket detection logic
notifier.py      — Telegram + Slack alert senders
config.py        — Configuration and env loading
.env.example     — Environment variable template
```
