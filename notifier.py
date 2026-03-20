import asyncio
import logging

import config
from detector import DetectionResult

logger = logging.getLogger(__name__)


ALERT_REPEAT_COUNT = 3
ALERT_REPEAT_INTERVAL_SECONDS = 10


async def send_telegram_alert(result: DetectionResult) -> bool:
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured, skipping")
        return False

    try:
        from telegram import Bot

        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)

        message = _format_telegram_message(result)

        await bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=message,
            parse_mode="HTML",
        )
        logger.info("Telegram text alert sent")

        if result.screenshot_path:
            with open(result.screenshot_path, "rb") as photo:
                await bot.send_photo(
                    chat_id=config.TELEGRAM_CHAT_ID,
                    photo=photo,
                    caption="RCB Ticket Page Screenshot",
                )
            logger.info("Telegram screenshot sent")

        for i in range(ALERT_REPEAT_COUNT - 1):
            await asyncio.sleep(ALERT_REPEAT_INTERVAL_SECONDS)
            matches_text = ", ".join(result.new_matches) if result.new_matches else "New tickets"
            await bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=(
                    f"🚨🚨🚨 REMINDER {i + 2}/{ALERT_REPEAT_COUNT} 🚨🚨🚨\n\n"
                    f"<b>{matches_text} -- TICKETS ARE LIVE!</b>\n\n"
                    f"🔗 <a href='https://shop.royalchallengers.com/ticket'>BOOK NOW</a>"
                ),
                parse_mode="HTML",
            )
            logger.info("Telegram reminder %d/%d sent", i + 2, ALERT_REPEAT_COUNT)

        return True

    except Exception as e:
        logger.error("Telegram alert failed: %s", e)
        return False


def send_slack_alert(result: DetectionResult) -> bool:
    if not config.SLACK_BOT_TOKEN or not config.SLACK_CHANNEL_ID:
        logger.warning("Slack not configured, skipping")
        return False

    try:
        from slack_sdk import WebClient

        client = WebClient(token=config.SLACK_BOT_TOKEN)
        message = _format_slack_message(result)

        client.chat_postMessage(
            channel=config.SLACK_CHANNEL_ID,
            text="🏏 RCB TICKETS ARE LIVE!",
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🏏 RCB TICKETS ARE LIVE!",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": message,
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "🎟️ Book Now"},
                            "url": "https://shop.royalchallengers.com/ticket",
                            "style": "primary",
                        }
                    ],
                },
            ],
        )
        logger.info("Slack alert sent")
        return True

    except Exception as e:
        logger.error("Slack alert failed: %s", e)
        return False


async def send_alerts(result: DetectionResult) -> dict[str, bool]:
    outcomes = {}
    outcomes["telegram"] = await send_telegram_alert(result)
    outcomes["slack"] = send_slack_alert(result)
    return outcomes


def _format_telegram_message(result: DetectionResult) -> str:
    lines = [
        "🚨 <b>RCB TICKETS ARE LIVE!</b> 🚨",
        "",
    ]

    if result.new_matches:
        lines.append("<b>New matches available:</b>")
        for match in result.new_matches:
            lines.append(f"  🏏 {match}")
        lines.append("")

    if result.action_keywords_found:
        actions = ", ".join(result.action_keywords_found[:5])
        lines.append(f"<b>Detected:</b> {actions}")

    lines.extend([
        "",
        f"🔗 <a href='{result.url}'>Open Ticket Page</a>",
        "",
        f"📊 Page content: {result.content_length} chars (was {result.baseline_length})",
        "",
        "⚡ <b>GO BOOK NOW before they sell out!</b>",
    ])

    return "\n".join(lines)


def _format_slack_message(result: DetectionResult) -> str:
    lines = []

    if result.new_matches:
        lines.append("*New matches available:*")
        for match in result.new_matches:
            lines.append(f"  :cricket_bat_and_ball: {match}")
        lines.append("")

    if result.action_keywords_found:
        actions = ", ".join(result.action_keywords_found[:5])
        lines.append(f"*Detected:* {actions}")

    lines.extend([
        "",
        f":link: <https://shop.royalchallengers.com/ticket|Open Ticket Page>",
        f":bar_chart: Page content: {result.content_length} chars (was {result.baseline_length})",
        "",
        ":zap: *GO BOOK NOW before they sell out!*",
    ])

    return "\n".join(lines)
