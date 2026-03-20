"""
Single-run ticket checker for GitHub Actions.

Performs multiple check rounds with intervals, then exits.
Usage: python check_once.py --rounds 3 --interval 90
"""

import argparse
import asyncio
import logging
import sys

import config
from scraper import RCBScraper
from detector import TicketDetector
from notifier import send_alerts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("rcb-check")


async def run(rounds: int, interval: int):
    scraper = RCBScraper()
    detector = TicketDetector()

    await scraper.start()

    try:
        for i in range(1, rounds + 1):
            logger.info("=== Round %d/%d ===", i, rounds)

            results = None
            for attempt in range(1, config.MAX_RETRIES + 1):
                try:
                    results = await scraper.scrape_all()
                    if any(r.success for r in results):
                        break
                except Exception as e:
                    logger.warning("Attempt %d failed: %s", attempt, e)
                    await asyncio.sleep(2 ** attempt)

            if not results or not any(r.success for r in results):
                logger.error("All scrape attempts failed in round %d", i)
                continue

            for r in results:
                tag = "OK" if r.success else "FAIL"
                logger.info("[%s] %s: %d chars", tag, r.url, len(r.page_text))

            detection = detector.analyze(results)
            logger.info("Result: %s", detection.summary)

            if detection.tickets_found:
                logger.info("TICKETS FOUND! Sending alerts...")
                outcomes = await send_alerts(detection)
                for channel, success in outcomes.items():
                    logger.info("  %s: %s", channel, "sent" if success else "FAILED")
            else:
                logger.info("No tickets yet.")

            if i < rounds:
                logger.info("Sleeping %ds before next round...", interval)
                await asyncio.sleep(interval)

    finally:
        await scraper.stop()

    logger.info("All rounds complete.")


def main():
    parser = argparse.ArgumentParser(description="RCB Ticket Checker (single run)")
    parser.add_argument("--rounds", type=int, default=3, help="Number of check rounds")
    parser.add_argument("--interval", type=int, default=90, help="Seconds between rounds")
    args = parser.parse_args()

    asyncio.run(run(args.rounds, args.interval))


if __name__ == "__main__":
    main()
