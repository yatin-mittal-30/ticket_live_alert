import logging
from dataclasses import dataclass, field
from urllib.parse import urlparse

from scraper import ScrapeResult
import config

logger = logging.getLogger(__name__)


def _is_rcb_ticket_listing_url(url: str) -> bool:
    path = (urlparse(url).path or "").lower().rstrip("/")
    return path.endswith("/ticket") or path.endswith("/tickets")


def _is_shop_ticket_tab_path(url: str) -> bool:
    """True only for /ticket, not /tickets (str.endswith('/ticket') matches /tickets incorrectly)."""
    seg = (urlparse(url).path or "").lower().strip("/").split("/")[-1:]
    return bool(seg) and seg[0] == "ticket"


def _is_shop_home_url(url: str) -> bool:
    return (
        url.rstrip("/") == config.URLS["shop_home"].rstrip("/")
    )


@dataclass
class DetectionResult:
    tickets_found: bool = False
    new_matches: list[str] = field(default_factory=list)
    all_matches_found: list[str] = field(default_factory=list)
    action_keywords_found: list[str] = field(default_factory=list)
    signal_keywords_found: list[str] = field(default_factory=list)
    content_length: int = 0
    baseline_length: int = 0
    screenshot_path: str = ""
    url: str = ""
    summary: str = ""


LINK_FALSE_POSITIVES = [
    "facebook", "twitter", "instagram", "youtube", "whatsapp",
    "shop-terms", "privacy", "about-us", "contact",
    "playstore", "apple.com", "apps.apple",
]


def _ticket_page_shows_wait_copy(text_lower: str) -> bool:
    """True when the shop still shows the standard 'no tickets yet' messaging."""
    return any(phrase in text_lower for phrase in config.TICKET_PAGE_WAIT_PHRASES)


class _Signals:
    """Accumulates detection signals across all pages."""

    def __init__(self):
        self.ticket_page_length: int = 0
        self.ticket_page_baseline: int = 0
        self.ticket_page_grew: bool = False
        self.ticket_page_wait_copy: bool = False
        self.ticket_tab_gate_ok: bool = False
        self.ticket_tab_gate_reason: str = ""
        self.match_keywords: list[str] = []
        self.action_keywords: list[str] = []
        self.signal_keywords: list[str] = []
        self.ticket_links: list[str] = []
        self.shop_has_ticket_nav: bool = False
        self.fixtures_has_buy_links: bool = False
        self.screenshot_path: str = ""
        self.url: str = ""


class TicketDetector:
    def __init__(self):
        self._known_matches: set[str] = set()
        self._ticket_page_baseline: int | None = None

    def analyze(self, results: list[ScrapeResult]) -> DetectionResult:
        ticket_pages = [r for r in results if r.success and _is_rcb_ticket_listing_url(r.url)]
        shop_home = next((r for r in results if r.success and _is_shop_home_url(r.url)), None)
        fixtures_page = next((r for r in results if r.success and "fixtures" in r.url), None)

        signals = _Signals()

        if ticket_pages:
            self._analyze_ticket_pages(ticket_pages, signals)
        elif self._ticket_page_baseline is not None:
            signals.ticket_page_baseline = self._ticket_page_baseline

        if shop_home:
            self._analyze_shop_home(shop_home, signals)

        if fixtures_page:
            self._analyze_fixtures_page(fixtures_page, signals)

        tab = self._result_for_shop_ticket_tab(results)
        signals.ticket_tab_gate_ok, signals.ticket_tab_gate_reason = self._evaluate_ticket_tab_alert_gate(
            tab
        )

        primary = ticket_pages[0] if ticket_pages else None
        return self._make_decision(signals, primary)

    def _analyze_ticket_pages(self, pages: list[ScrapeResult], signals: _Signals):
        """Merge /ticket and /tickets listing pages: combined length baseline and shared signals."""
        total_len = sum(len(r.page_text.strip()) for r in pages)

        if self._ticket_page_baseline is None:
            self._ticket_page_baseline = total_len
            logger.info(
                "Ticket pages combined baseline (/ticket + /tickets): %d chars",
                total_len,
            )

        signals.ticket_page_length = total_len
        signals.ticket_page_baseline = self._ticket_page_baseline
        signals.ticket_page_grew = total_len > (self._ticket_page_baseline + 200)

        shot = next((r for r in pages if "/tickets" in r.url.lower() and r.screenshot_path), None)
        if not shot:
            shot = next((r for r in pages if r.screenshot_path), None)
        if shot:
            signals.screenshot_path = shot.screenshot_path
        signals.url = config.PRIMARY_TICKET_SHOP_URL

        combined_lower = "\n".join(
            r.page_text.strip().lower() for r in pages if (r.page_text or "").strip()
        )
        signals.ticket_page_wait_copy = _ticket_page_shows_wait_copy(combined_lower)

        for result in pages:
            text_lower = result.page_text.strip().lower()
            signals.match_keywords.extend(self._find_match_keywords(text_lower))
            signals.action_keywords.extend(self._find_keywords(text_lower, config.TICKET_ACTION_KEYWORDS))
            signals.signal_keywords.extend(self._find_keywords(text_lower, config.TICKET_SIGNAL_KEYWORDS))
            signals.ticket_links.extend(self._find_ticket_links(result.links))

    def _analyze_shop_home(self, result: ScrapeResult, signals: _Signals):
        """Nav links, ticket hrefs on shop, and visible buttons that look like ticket CTAs."""
        for link in result.links:
            href = link["href"].lower()
            text = link["text"].lower().strip()
            if self._is_false_positive_link(href):
                continue
            if "ticket" in text and not self._is_false_positive_link(href):
                signals.shop_has_ticket_nav = True
                signals.ticket_links.append(f"nav: {link['text']} ({link['href']})")
            if "ticket" in href and "shop.royalchallengers.com" in href:
                signals.shop_has_ticket_nav = True
                signals.ticket_links.append(f"shop-link: {link['text'][:40]} ({link['href'][:90]})")

        for btn in result.buttons:
            low = btn.lower().strip()
            if low in config.SHOP_NAV_IGNORE_BUTTONS:
                continue
            if not any(h in low for h in config.SHOP_TICKET_BUTTON_HINTS):
                continue
            signals.shop_has_ticket_nav = True
            signals.ticket_links.append(f"shop-btn: {btn[:100]}")

    def _analyze_fixtures_page(self, result: ScrapeResult, signals: _Signals):
        """Match fixture CTAs that clearly refer to tickets (not generic merch 'Buy now')."""
        ticket_cta_in_text = ("buy ticket", "book ticket", "get ticket")
        loose_cta_in_text = ("book now", "buy now")
        for link in result.links:
            href = link["href"].lower()
            text = link["text"].lower().strip()
            if self._is_false_positive_link(href):
                continue
            has_explicit_ticket = any(kw in text for kw in ticket_cta_in_text)
            has_loose_cta = any(kw in text for kw in loose_cta_in_text)
            href_suggests_tickets = "ticket" in href
            if not has_explicit_ticket and not (has_loose_cta and href_suggests_tickets):
                continue
            signals.fixtures_has_buy_links = True
            signals.ticket_links.append(f"fixtures: {link['text'][:50]} ({link['href'][:80]})")

    def _result_for_shop_ticket_tab(self, results: list[ScrapeResult]) -> ScrapeResult | None:
        """Successful scrape for the /ticket URL (not /tickets)."""
        want = config.URLS["ticket_page"].rstrip("/").lower()
        for r in results:
            if not r.success:
                continue
            if r.url.rstrip("/").lower() == want:
                return r
        for r in results:
            if not r.success:
                continue
            host = (urlparse(r.url).netloc or "").lower()
            if "shop.royalchallengers.com" not in host:
                continue
            if _is_shop_ticket_tab_path(r.url):
                return r
        return None

    def _evaluate_ticket_tab_alert_gate(self, tab: ScrapeResult | None) -> tuple[bool, str]:
        """
        Alerts only if https://shop.royalchallengers.com/ticket shows an opponent
        or no longer shows the standard wait copy (with enough body text to trust that).
        """
        if tab is None:
            return False, "no successful /ticket scrape"

        text = tab.page_text.strip()
        low = text.lower()
        if self._find_match_keywords(low):
            return True, "opponent named on /ticket"

        if len(text) < config.TICKET_TAB_MIN_BODY_CHARS:
            return False, f"/ticket body too short (<{config.TICKET_TAB_MIN_BODY_CHARS} chars)"

        if _ticket_page_shows_wait_copy(low):
            return False, "wait copy still on /ticket"

        return True, "no wait copy on /ticket"

    def _make_decision(self, signals: _Signals, _primary_ticket_page: ScrapeResult | None) -> DetectionResult:
        unique_matches = list(dict.fromkeys(signals.match_keywords))
        new_matches = [m for m in unique_matches if m not in self._known_matches]

        raw_tickets_found = False
        has_team_listing = bool(unique_matches)
        # Merch "Buy Now" and persistent nav stay on the wait-state page; do not treat as live tickets.
        wait_page_blocks_weak_signals = signals.ticket_page_wait_copy and not has_team_listing

        if has_team_listing:
            raw_tickets_found = True
        elif not wait_page_blocks_weak_signals and signals.fixtures_has_buy_links:
            raw_tickets_found = True
        elif not wait_page_blocks_weak_signals and signals.shop_has_ticket_nav:
            raw_tickets_found = True
        elif not wait_page_blocks_weak_signals and signals.ticket_links:
            raw_tickets_found = True
        elif (
            not wait_page_blocks_weak_signals
            and signals.ticket_page_grew
            and (signals.action_keywords or signals.signal_keywords)
        ):
            raw_tickets_found = True

        tickets_found = raw_tickets_found and signals.ticket_tab_gate_ok

        if tickets_found and new_matches:
            self._known_matches.update(new_matches)

        summary = self._build_summary(
            tickets_found,
            new_matches,
            unique_matches,
            signals,
            raw_tickets_found=raw_tickets_found,
        )

        return DetectionResult(
            tickets_found=tickets_found,
            new_matches=new_matches,
            all_matches_found=unique_matches,
            action_keywords_found=signals.action_keywords + signals.ticket_links,
            signal_keywords_found=signals.signal_keywords,
            content_length=signals.ticket_page_length,
            baseline_length=signals.ticket_page_baseline,
            screenshot_path=signals.screenshot_path,
            url=signals.url,
            summary=summary,
        )

    def _find_match_keywords(self, text: str) -> list[str]:
        found = []
        seen = set()
        for match_info in config.TARGET_MATCHES:
            opponent = match_info["opponent"]
            if opponent.lower() in seen:
                continue
            if opponent.lower() in text or match_info["full_name"].lower() in text:
                found.append(f"RCB vs {opponent}")
                seen.add(opponent.lower())
        return found

    def _find_keywords(self, text: str, keywords: list[str]) -> list[str]:
        return [kw for kw in keywords if kw in text]

    def _find_ticket_links(self, links: list[dict]) -> list[str]:
        """Find links that are genuinely ticket-related (not nav, not social media)."""
        results = []
        for link in links:
            href = link["href"].lower()
            text = link["text"].lower().strip()
            if self._is_false_positive_link(href):
                continue
            combined = href + " " + text
            if any(kw in combined for kw in ["buy now", "book now", "add to cart", "select seat"]):
                results.append(f"link: {link['text'][:50]} ({link['href'][:80]})")
        return results

    def _is_false_positive_link(self, href: str) -> bool:
        href_lower = href.lower()
        return any(fp in href_lower for fp in LINK_FALSE_POSITIVES)

    def _build_summary(
        self,
        tickets_found: bool,
        new_matches: list[str],
        all_matches: list[str],
        signals: _Signals,
        *,
        raw_tickets_found: bool = False,
    ) -> str:
        if not tickets_found:
            wait_note = (
                f" Wait-state copy on ticket page: {signals.ticket_page_wait_copy}."
                if signals.ticket_page_length or signals.ticket_page_wait_copy
                else ""
            )
            gate_note = ""
            if raw_tickets_found and not signals.ticket_tab_gate_ok:
                gate_note = f" Alert suppressed: {signals.ticket_tab_gate_reason}."
            return (
                f"No tickets detected. "
                f"Ticket page: {signals.ticket_page_length} chars "
                f"(baseline: {signals.ticket_page_baseline}).{wait_note} "
                f"/ticket gate: {signals.ticket_tab_gate_reason}.{gate_note} "
                f"Shop nav ticket link: {signals.shop_has_ticket_nav}. "
                f"Fixtures buy links: {signals.fixtures_has_buy_links}."
            )

        parts = ["TICKETS DETECTED!"]
        parts.append(f"/ticket gate: {signals.ticket_tab_gate_reason}")
        if new_matches:
            parts.append(f"New matches: {', '.join(new_matches)}")
        if signals.ticket_page_grew:
            parts.append(
                f"Ticket page grew: {signals.ticket_page_baseline} -> {signals.ticket_page_length} chars"
            )
        if signals.action_keywords:
            parts.append(f"Actions: {', '.join(signals.action_keywords[:3])}")
        if signals.ticket_links:
            parts.append(f"Ticket links: {', '.join(signals.ticket_links[:3])}")
        if signals.shop_has_ticket_nav:
            parts.append("Shop has ticket nav")
        if signals.fixtures_has_buy_links:
            parts.append("Fixtures page has buy links")
        return " | ".join(parts)
