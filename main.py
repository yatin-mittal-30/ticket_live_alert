import asyncio
import json
import logging
import logging.handlers
import os
import signal
import sys
import random
from datetime import datetime, timedelta, timezone

import config
from scraper import RCBScraper
from detector import TicketDetector
from notifier import send_alerts

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_LOG_DATE = "%Y-%m-%d %H:%M:%S"


def _setup_logging() -> logging.Logger:
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in list(root.handlers):
        root.removeHandler(h)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(_LOG_FORMAT, _LOG_DATE))

    file_path = os.path.join(LOG_DIR, "agent.log")
    rotating = logging.handlers.TimedRotatingFileHandler(
        file_path,
        when="midnight",
        interval=1,
        backupCount=14,
        encoding="utf-8",
    )
    rotating.suffix = "%Y-%m-%d"
    rotating.setFormatter(logging.Formatter(_LOG_FORMAT, _LOG_DATE))

    root.addHandler(console)
    root.addHandler(rotating)
    return logging.getLogger("rcb-agent")


logger = _setup_logging()


class RCBTicketAgent:
    def __init__(self):
        self.scraper = RCBScraper()
        self.detector = TicketDetector()
        self._running = False
        self._check_count = 0
        self._last_alert_time: datetime | None = None

    async def start(self):
        logger.info("=" * 60)
        logger.info("RCB Ticket Alert Agent starting")
        logger.info("Check interval: %ds", config.CHECK_INTERVAL_SECONDS)
        logger.info("Alert cooldown: %d min", config.ALERT_COOLDOWN_MINUTES)
        logger.info("Monitoring URLs:")
        for name, url in config.URLS.items():
            logger.info("  [%s] %s", name, url)
        logger.info("Target matches:")
        for m in config.TARGET_MATCHES:
            logger.info("  RCB vs %s (%s) - %s", m["opponent"], m["full_name"], m["date"])
        logger.info("=" * 60)

        await self.scraper.start()
        self._running = True

        try:
            while self._running:
                await self._run_check()
                jitter = random.randint(0, 10)
                sleep_time = config.CHECK_INTERVAL_SECONDS + jitter
                logger.info("Next check in %ds...", sleep_time)
                await asyncio.sleep(sleep_time)
        except asyncio.CancelledError:
            logger.info("Agent loop cancelled")
        finally:
            await self.scraper.stop()
            logger.info("Agent stopped")

    def stop(self):
        self._running = False

    def _append_check_jsonl(self, record: dict) -> None:
        path = os.path.join(LOG_DIR, "checks.jsonl")
        line = json.dumps(record, ensure_ascii=False) + "\n"
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line)
        except OSError as e:
            logger.warning("Could not append checks.jsonl: %s", e)

    async def _run_check(self):
        self._check_count += 1
        now = datetime.now(timezone.utc)
        logger.info("--- Check #%d at %s ---", self._check_count, datetime.now().strftime("%H:%M:%S"))

        results = None
        last_error = None

        for attempt in range(1, config.MAX_RETRIES + 1):
            try:
                results = await self.scraper.scrape_all()
                if any(r.success for r in results):
                    break
            except Exception as e:
                last_error = e
                wait = 2 ** attempt
                logger.warning("Attempt %d/%d failed: %s. Retrying in %ds...", attempt, config.MAX_RETRIES, e, wait)
                await asyncio.sleep(wait)

        scrape_ok = bool(results and any(r.success for r in results))
        if not scrape_ok:
            logger.error("All %d scrape attempts failed. Last error: %s", config.MAX_RETRIES, last_error)
            self._append_check_jsonl({
                "ts_utc": now.isoformat(),
                "check": self._check_count,
                "scrape_ok": False,
                "tickets_found": False,
                "summary": str(last_error) if last_error else "scrape failed",
            })
            return

        detection = self.detector.analyze(results)
        logger.info("Detection: %s", detection.summary)

        alerted = False
        cooldown_skipped = False
        if detection.tickets_found:
            if self._is_in_cooldown():
                cooldown_skipped = True
                logger.info("Tickets detected but in cooldown period, skipping alert")
            else:
                logger.info("TICKETS FOUND! Sending alerts...")
                outcomes = await send_alerts(detection)
                self._last_alert_time = datetime.now()
                alerted = True

                for channel, success in outcomes.items():
                    status = "sent" if success else "FAILED"
                    logger.info("  %s alert: %s", channel, status)
        else:
            logger.info("No tickets yet.")

        self._append_check_jsonl({
            "ts_utc": now.isoformat(),
            "check": self._check_count,
            "scrape_ok": True,
            "tickets_found": bool(detection.tickets_found),
            "alert_sent": alerted,
            "cooldown_skipped": cooldown_skipped,
            "new_matches": detection.new_matches,
            "summary": detection.summary[:500] if detection.summary else "",
        })

    def _is_in_cooldown(self) -> bool:
        if not self._last_alert_time:
            return False
        cooldown = timedelta(minutes=config.ALERT_COOLDOWN_MINUTES)
        return datetime.now() - self._last_alert_time < cooldown


async def main():
    agent = RCBTicketAgent()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, agent.stop)

    await agent.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down via keyboard interrupt")
