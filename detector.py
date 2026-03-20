import logging
from dataclasses import dataclass, field

from scraper import ScrapeResult
import config

logger = logging.getLogger(__name__)


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


class _Signals:
    """Accumulates detection signals across all pages."""

    def __init__(self):
        self.ticket_page_length: int = 0
        self.ticket_page_baseline: int = 0
        self.ticket_page_grew: bool = False
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
        ticket_page = next((r for r in results if "ticket" in r.url and r.success), None)
        shop_home = next((r for r in results if r.url.rstrip("/").endswith(".com") and r.success), None)
        fixtures_page = next((r for r in results if "fixtures" in r.url and r.success), None)

        signals = _Signals()

        if ticket_page:
            self._analyze_ticket_page(ticket_page, signals)

        if shop_home:
            self._analyze_shop_home(shop_home, signals)

        if fixtures_page:
            self._analyze_fixtures_page(fixtures_page, signals)

        return self._make_decision(signals, ticket_page)

    def _analyze_ticket_page(self, result: ScrapeResult, signals: _Signals):
        """The primary signal source. If this page has ticket content, that's the strongest indicator."""
        text = result.page_text.strip()
        text_lower = text.lower()
        content_length = len(text)

        if self._ticket_page_baseline is None:
            self._ticket_page_baseline = content_length
            logger.info("Ticket page baseline: %d chars", self._ticket_page_baseline)

        signals.ticket_page_length = content_length
        signals.ticket_page_baseline = self._ticket_page_baseline
        signals.screenshot_path = result.screenshot_path
        signals.url = result.url

        content_grew = content_length > (self._ticket_page_baseline + 200)
        signals.ticket_page_grew = content_grew

        signals.match_keywords.extend(self._find_match_keywords(text_lower))
        signals.action_keywords.extend(self._find_keywords(text_lower, config.TICKET_ACTION_KEYWORDS))
        signals.signal_keywords.extend(self._find_keywords(text_lower, config.TICKET_SIGNAL_KEYWORDS))
        signals.ticket_links.extend(self._find_ticket_links(result.links))

    def _analyze_shop_home(self, result: ScrapeResult, signals: _Signals):
        """Check if shop homepage now has a visible 'Tickets' nav link or banner."""
        for link in result.links:
            href = link["href"].lower()
            text = link["text"].lower().strip()
            if "ticket" in text and not self._is_false_positive_link(href):
                signals.shop_has_ticket_nav = True
                signals.ticket_links.append(f"nav: {link['text']} ({link['href']})")
                break

    def _analyze_fixtures_page(self, result: ScrapeResult, signals: _Signals):
        """Only look for 'Buy Tickets' or 'Book Now' links next to match entries."""
        for link in result.links:
            href = link["href"].lower()
            text = link["text"].lower().strip()
            if self._is_false_positive_link(href):
                continue
            if any(kw in text for kw in ["buy ticket", "book ticket", "get ticket", "buy now"]):
                signals.fixtures_has_buy_links = True
                signals.ticket_links.append(f"fixtures: {link['text'][:50]} ({link['href'][:80]})")

    def _make_decision(self, signals: _Signals, ticket_page: ScrapeResult | None) -> DetectionResult:
        unique_matches = list(dict.fromkeys(signals.match_keywords))
        new_matches = [m for m in unique_matches if m not in self._known_matches]

        tickets_found = False

        if signals.ticket_page_grew and signals.action_keywords:
            tickets_found = True
        elif signals.ticket_page_grew and signals.match_keywords:
            tickets_found = True
        elif signals.ticket_links:
            tickets_found = True
        elif signals.shop_has_ticket_nav:
            tickets_found = True
        elif signals.fixtures_has_buy_links:
            tickets_found = True

        if tickets_found and new_matches:
            self._known_matches.update(new_matches)

        summary = self._build_summary(tickets_found, new_matches, unique_matches, signals)

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
    ) -> str:
        if not tickets_found:
            return (
                f"No tickets detected. "
                f"Ticket page: {signals.ticket_page_length} chars "
                f"(baseline: {signals.ticket_page_baseline}). "
                f"Shop nav ticket link: {signals.shop_has_ticket_nav}. "
                f"Fixtures buy links: {signals.fixtures_has_buy_links}."
            )

        parts = ["TICKETS DETECTED!"]
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
