import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime

from playwright.async_api import async_playwright, Browser, Page

import config

logger = logging.getLogger(__name__)


@dataclass
class ScrapeResult:
    url: str
    page_text: str
    links: list[dict] = field(default_factory=list)
    buttons: list[str] = field(default_factory=list)
    screenshot_path: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    success: bool = True
    error: str = ""


class RCBScraper:
    def __init__(self):
        self._playwright = None
        self._browser: Browser | None = None
        self._context = None

    async def start(self):
        os.makedirs(config.SCREENSHOTS_DIR, exist_ok=True)
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=config.HEADLESS,
        )
        self._context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
        )
        logger.info("Browser launched (headless=%s), persistent context ready", config.HEADLESS)

    async def stop(self):
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser closed")

    async def scrape_page(self, url: str, take_screenshot: bool = True) -> ScrapeResult:
        if not self._context:
            raise RuntimeError("Browser not started. Call start() first.")

        page: Page = await self._context.new_page()

        try:
            logger.debug("Navigating to %s", url)
            await page.goto(url, timeout=config.PAGE_LOAD_TIMEOUT_MS, wait_until="load")

            try:
                await page.wait_for_load_state("networkidle", timeout=10_000)
            except Exception:
                pass

            page_text = await self._wait_for_body_content(page)

            if len(page_text.strip()) < 50:
                raw_html = await page.content()
                fallback = self._extract_text_from_html(raw_html)
                if len(fallback.strip()) > len(page_text.strip()):
                    logger.info("Using HTML fallback for %s (%d chars vs %d)", url, len(fallback.strip()), len(page_text.strip()))
                    page_text = fallback

            link_elements = await page.query_selector_all("a")
            links = []
            for el in link_elements:
                href = await el.get_attribute("href") or ""
                text = (await el.inner_text()).strip()
                if href:
                    links.append({"href": href, "text": text})

            button_labels: set[str] = set()
            for sel in ("button", "[role='button']"):
                try:
                    for el in await page.query_selector_all(sel):
                        try:
                            parts = []
                            t = (await el.inner_text()).strip()
                            if t:
                                parts.append(t)
                            for attr in ("aria-label", "title", "value"):
                                v = await el.get_attribute(attr)
                                if v and v.strip():
                                    parts.append(v.strip())
                            label = " — ".join(dict.fromkeys(parts))
                            if label:
                                button_labels.add(label[:200])
                        except Exception:
                            continue
                except Exception:
                    continue
            buttons = sorted(button_labels)

            screenshot_path = ""
            if take_screenshot:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_url = url.replace("https://", "").replace("/", "_").replace(".", "_")
                screenshot_path = os.path.join(config.SCREENSHOTS_DIR, f"{safe_url}_{ts}.png")
                await page.screenshot(path=screenshot_path, full_page=True)

            return ScrapeResult(
                url=url,
                page_text=page_text,
                links=links,
                buttons=buttons,
                screenshot_path=screenshot_path,
            )

        except Exception as e:
            logger.error("Scrape failed for %s: %s", url, e)
            return ScrapeResult(url=url, page_text="", success=False, error=str(e))

        finally:
            await page.close()

    @staticmethod
    async def _wait_for_body_content(page: Page, min_chars: int = 50, timeout_ms: int = 15000) -> str:
        """Poll body text until the SPA has rendered meaningful content."""
        interval = 1000
        waited = 0
        text = ""
        while waited < timeout_ms:
            try:
                text = await page.evaluate(
                    "(min) => {"
                    "  const shop = document.querySelector('#rcb-shop');"
                    "  if (shop && shop.innerText.trim().length >= min) return shop.innerText;"
                    "  const body = document.body;"
                    "  return body ? body.innerText : '';"
                    "}",
                    min_chars,
                )
            except Exception:
                text = ""
            if len((text or "").strip()) >= min_chars:
                return text
            await page.wait_for_timeout(interval)
            waited += interval
        logger.warning(
            "Body still short (%d chars) after %dms on %s",
            len((text or "").strip()), timeout_ms, page.url,
        )
        return text or ""

    @staticmethod
    def _extract_text_from_html(html: str) -> str:
        """Crude tag-strip fallback when JS rendering fails."""
        text = re.sub(r"<script[^>]*>[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
        text = re.sub(r"<style[^>]*>[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"&[a-zA-Z]+;", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    async def scrape_all(self) -> list[ScrapeResult]:
        results = []
        for name, url in config.URLS.items():
            logger.info("Scraping [%s] %s", name, url)
            take_shot = name in ("ticket_page", "tickets_page")
            result = await self.scrape_page(url, take_screenshot=take_shot)
            results.append(result)
        return results
