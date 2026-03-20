import asyncio
import logging
import signal
import sys
import random
from datetime import datetime, timedelta

import config
from scraper import RCBScraper
from detector import TicketDetector
from notifier import send_alerts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("agent.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("rcb-agent")


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

    async def _run_check(self):
        self._check_count += 1
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

        if not results or not any(r.success for r in results):
            logger.error("All %d scrape attempts failed. Last error: %s", config.MAX_RETRIES, last_error)
            return

        detection = self.detector.analyze(results)
        logger.info("Detection: %s", detection.summary)

        if detection.tickets_found:
            if self._is_in_cooldown():
                logger.info("Tickets detected but in cooldown period, skipping alert")
                return

            logger.info("TICKETS FOUND! Sending alerts...")
            outcomes = await send_alerts(detection)
            self._last_alert_time = datetime.now()

            for channel, success in outcomes.items():
                status = "sent" if success else "FAILED"
                logger.info("  %s alert: %s", channel, status)
        else:
            logger.info("No tickets yet.")

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
