import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID", "")

# Comma-separated Slack user IDs @mentioned on ticket alerts only (not heartbeats).
_notify_raw = os.getenv("SLACK_NOTIFY_USER_IDS", "").strip()
if _notify_raw:
    SLACK_NOTIFY_USER_IDS = [x.strip() for x in _notify_raw.split(",") if x.strip()]
else:
    _legacy = os.getenv("SLACK_USER_ID", "").strip()
    if _legacy:
        SLACK_NOTIFY_USER_IDS = [_legacy]
    else:
        SLACK_NOTIFY_USER_IDS = ["U059LSX2PV1", "U059J2TDZNZ"]

CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "45"))
ALERT_COOLDOWN_MINUTES = int(os.getenv("ALERT_COOLDOWN_MINUTES", "10"))
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"

# Slack-only periodic “still running” ping (main.py local loop only; not ticket alerts).
SLACK_HEARTBEAT_ENABLED = os.getenv("SLACK_HEARTBEAT_ENABLED", "true").lower() == "true"
SLACK_HEARTBEAT_MINUTES = int(os.getenv("SLACK_HEARTBEAT_MINUTES", "30"))

URLS = {
    "ticket_page": "https://shop.royalchallengers.com/ticket",
    "tickets_page": "https://shop.royalchallengers.com/tickets",
    "shop_home": "https://shop.royalchallengers.com/",
    "fixtures": "https://royalchallengers.com/fixtures",
}

# Book-now links in Slack/Telegram (both /ticket and /tickets are monitored above).
PRIMARY_TICKET_SHOP_URL = os.getenv(
    "PRIMARY_TICKET_SHOP_URL",
    "https://shop.royalchallengers.com/tickets",
)

TARGET_MATCHES = [
    {"opponent": "SRH", "full_name": "Sunrisers Hyderabad", "date": "March 28, 2026"},
    {"opponent": "CSK", "full_name": "Chennai Super Kings", "date": "April 5, 2026"},
]

MATCH_KEYWORDS = [
    "srh", "csk", "sunrisers", "chennai",
    "march 28", "28 mar", "28th march",
    "april 5", "5 apr", "5th april",
]

TICKET_ACTION_KEYWORDS = [
    "buy now", "book now", "add to cart", "select seat",
    "book ticket", "get ticket", "buy ticket",
]

# Shop page: button / visible text hints (lowercase) for ticket CTAs.
SHOP_TICKET_BUTTON_HINTS = [
    "ticket", "tickets", "buy ticket", "book ticket", "get ticket", "match tickets",
]

TICKET_SIGNAL_KEYWORDS = [
    "chinnaswamy", "m. chinnaswamy", "stadium",
    "east stand", "west stand", "north", "south",
    "pavilion", "terrace", "gallery",
    "rs.", "rs ", "inr", "/-",
]

SCREENSHOTS_DIR = "screenshots"
PAGE_LOAD_TIMEOUT_MS = 30_000
MAX_RETRIES = 3
