from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup, Tag
from dateutil import parser as date_parser


REQUEST_TIMEOUT_SECONDS = 20
SEEK_RECENT_DATE_LABEL = "Within last 7 days"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}


@dataclass
class ListingSelectors:
    listing: str | None = None
    title: str | None = None
    company: str | None = None
    description: str | None = None
    date: str | None = None
    link: str | None = "a"


def scrape_listings(
    url: str,
    selectors: ListingSelectors | None = None,
    max_pages: int = 1,
    progress_callback=None,
) -> list[dict]:
    selectors = selectors or ListingSelectors()
    listings: list[dict] = []

    for page_number in range(1, max_pages + 1):
        page_url = _build_page_url(url, page_number)
        html = _fetch_html(page_url)
        soup = BeautifulSoup(html, "html.parser")

        cards = _find_listing_cards(soup, selectors)
        if not cards:
            _report_progress(
                progress_callback,
                page_number=page_number,
                page_url=page_url,
                cards_found=0,
                total_listings=len(listings),
                status="No listing cards found. Stopping.",
            )
            break

        previous_count = len(listings)
        for card in cards:
            listing = _extract_listing(card, page_url, selectors)
            if listing and listing["title"]:
                listings.append(listing)

        listings = _dedupe_listings(listings)
        new_listings = len(listings) - previous_count
        _report_progress(
            progress_callback,
            page_number=page_number,
            page_url=page_url,
            cards_found=len(cards),
            total_listings=len(listings),
            status=f"Added {new_listings} new listings.",
        )
        if len(listings) == previous_count:
            _report_progress(
                progress_callback,
                page_number=page_number,
                page_url=page_url,
                cards_found=len(cards),
                total_listings=len(listings),
                status="No new listings found. Stopping.",
            )
            break

    return listings


def _report_progress(progress_callback, **status) -> None:
    if progress_callback:
        progress_callback(status)


def enrich_listing_details(
    listings: list[dict],
    max_details: int | None = None,
    progress_callback=None,
) -> list[dict]:
    limit = len(listings) if max_details is None else min(max_details, len(listings))
    enriched: list[dict] = []

    for index, listing in enumerate(listings, start=1):
        if index > limit:
            enriched.append(listing)
            continue

        detail_url = listing.get("url", "")
        merged = dict(listing)

        if detail_url:
            try:
                detail_data = scrape_listing_detail(detail_url)
                merged.update({key: value for key, value in detail_data.items() if value})
                merged["detail_scraped"] = True
                status = "Detail page scraped."
            except requests.RequestException as exc:
                merged["detail_scraped"] = False
                merged["detail_error"] = str(exc)
                status = f"Detail scrape failed: {exc}"
        else:
            merged["detail_scraped"] = False
            status = "No detail URL found."

        enriched.append(merged)
        _report_progress(
            progress_callback,
            current=index,
            total=limit,
            title=merged.get("title", "Untitled listing"),
            url=detail_url,
            status=status,
        )

    return enriched


def scrape_listing_detail(url: str) -> dict:
    html = _fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    title = _first_text(soup, ["h1"])
    sections = _extract_detail_sections(soup)
    page_lines = _page_text_lines(soup)
    full_description = _detail_description_from_sections(sections)

    return {
        "detail_title": title,
        "detail_posted_date": _find_detail_posted_date(page_lines, title),
        "location": _find_detail_value(page_lines, "Location") or "",
        "price": _find_detail_value(page_lines, "Investment level") or "",
        "category": _find_detail_value(page_lines, "Industry") or "",
        "full_description": full_description,
        "detail_sections": sections,
        "detail_text": _clean_text(" ".join(page_lines[:220])),
    }


def filter_recent_listings(listings: Iterable[dict], days: int = 7) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    recent: list[dict] = []

    for listing in listings:
        parsed_date = parse_posted_date(listing.get("posted_date", ""))
        enriched = dict(listing)
        enriched["parsed_posted_date"] = parsed_date.date().isoformat() if parsed_date else None

        if parsed_date and parsed_date >= cutoff:
            recent.append(enriched)

    return recent


def parse_posted_date(raw_date: str | None) -> datetime | None:
    if not raw_date:
        return None

    value = " ".join(raw_date.strip().split()).lower()
    now = datetime.now(timezone.utc)

    if value in {"today", "now", "just now", "new", "within last 7 days"}:
        return now

    if value == "yesterday":
        return now - timedelta(days=1)

    relative_match = re.search(r"(\d+)\s+(minute|hour|day|week|month)s?\s+ago", value)
    if relative_match:
        amount = int(relative_match.group(1))
        unit = relative_match.group(2)
        if unit == "minute":
            return now - timedelta(minutes=amount)
        if unit == "hour":
            return now - timedelta(hours=amount)
        if unit == "day":
            return now - timedelta(days=amount)
        if unit == "week":
            return now - timedelta(weeks=amount)
        if unit == "month":
            return now - timedelta(days=amount * 30)

    try:
        parsed = date_parser.parse(raw_date, fuzzy=True)
    except (ValueError, OverflowError, TypeError):
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _fetch_html(url: str) -> str:
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.text


def _build_page_url(url: str, page_number: int) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query))

    page_param = "pg" if "seekbusiness.com.au" in parsed.netloc else "page"
    query[page_param] = str(page_number)

    return urlunparse(parsed._replace(query=urlencode(query)))


def _find_listing_cards(soup: BeautifulSoup, selectors: ListingSelectors) -> list[Tag]:
    if selectors.listing:
        cards = soup.select(selectors.listing)
        if cards:
            return [card for card in cards if isinstance(card, Tag)]

    candidate_selectors = [
        "article",
        "[class*='listing']",
        "[class*='card']",
        "[class*='result']",
        "[class*='job']",
        "li",
    ]

    for selector in candidate_selectors:
        cards = soup.select(selector)
        useful_cards = [
            card
            for card in cards
            if isinstance(card, Tag) and card.get_text(" ", strip=True) and card.find("a")
        ]
        if len(useful_cards) >= 3:
            return useful_cards

    body = soup.body
    return [body] if body else []


def _extract_listing(card: Tag, page_url: str, selectors: ListingSelectors) -> dict:
    if _is_seek_listing_card(card):
        return _extract_seek_listing(card, page_url)

    title = _select_text(card, selectors.title) or _first_text(card, ["h1", "h2", "h3", "a"])
    company = _select_text(card, selectors.company) or _first_text(
        card,
        [
            "[class*='company']",
            "[class*='business']",
            "[class*='organization']",
            "[class*='vendor']",
        ],
    )
    description = _select_text(card, selectors.description) or _first_text(
        card,
        ["p", "[class*='description']", "[class*='summary']", "[class*='excerpt']"],
    )
    posted_date = _select_text(card, selectors.date) or _find_date_text(card)
    listing_url = _select_link(card, page_url, selectors.link)

    return {
        "title": _clean_text(title),
        "company": _clean_text(company),
        "description": _clean_text(description),
        "posted_date": _clean_text(posted_date),
        "url": listing_url,
    }


def _is_seek_listing_card(card: Tag) -> bool:
    return card.get("data-testid") == "search-listings-result-item"


def _extract_seek_listing(card: Tag, page_url: str) -> dict:
    title_link = card.select_one("h2 a")
    title = title_link.get_text(" ", strip=True) if title_link else card.get("aria-label", "")
    listing_url = ""
    if title_link and title_link.has_attr("href"):
        listing_url = urljoin(page_url, str(title_link["href"]))

    company = _select_text(card, "[data-testid='serp-listing-business-name']")
    location = _select_text(card, "[data-testid='search-result-item-location-breadcrumbs']")
    category = _select_text(card, "[data-testid='search-result-item-industry-breadcrumbs']")
    description = _find_seek_description(card)
    posted_date = _find_date_text(card) or SEEK_RECENT_DATE_LABEL
    price, business_type = _find_seek_price_and_type(card)

    return {
        "title": _clean_text(title),
        "company": _clean_text(company),
        "location": _clean_text(location),
        "price": _clean_text(price),
        "business_type": _clean_text(business_type),
        "description": _clean_text(description),
        "category": _clean_text(category),
        "posted_date": _clean_text(posted_date),
        "url": listing_url,
        "source": "seekbusiness",
    }


def _find_seek_description(card: Tag) -> str:
    read_more_link = card.select_one("[data-testid='serp-listing-item-read-more-link']")
    if read_more_link and read_more_link.parent:
        return read_more_link.parent.get_text(" ", strip=True)

    spans = [
        span.get_text(" ", strip=True)
        for span in card.select("span")
        if span.get_text(" ", strip=True)
    ]
    candidates = [
        text
        for text in spans
        if len(text) > 80
        and "Enquire" not in text
        and "Featured" not in text
        and ">" not in text
    ]
    return max(candidates, key=len) if candidates else ""


def _find_seek_price_and_type(card: Tag) -> tuple[str, str]:
    known_business_types = {
        "Business",
        "Franchise New",
        "Franchise Resale",
        "Licence/Distribution",
    }
    price = ""
    business_type = ""

    for span in card.select("span"):
        text = _clean_text(span.get_text(" ", strip=True))
        if not text:
            continue

        if not price and ("$" in text or text.upper() == "P.O.A"):
            price = text
            continue

        if not business_type and text in known_business_types:
            business_type = text

    return price, business_type


def _page_text_lines(soup: BeautifulSoup) -> list[str]:
    return [
        _clean_text(line)
        for line in soup.get_text("\n", strip=True).splitlines()
        if _clean_text(line)
    ]


def _find_detail_value(lines: list[str], label: str) -> str:
    normalized_label = label.lower().rstrip(":")

    for index, line in enumerate(lines):
        normalized_line = line.lower().rstrip(":")
        if normalized_line == normalized_label and index + 1 < len(lines):
            return lines[index + 1]

        prefix = f"{label}:"
        if line.lower().startswith(prefix.lower()):
            return _clean_text(line[len(prefix) :])

    return ""


def _find_detail_posted_date(lines: list[str], title: str) -> str:
    for index, line in enumerate(lines):
        if title and line == title and index + 1 < len(lines):
            candidate = lines[index + 1]
            if _looks_like_posted_date(candidate):
                return candidate

        if _looks_like_posted_date(line):
            return line

    return ""


def _looks_like_posted_date(value: str) -> bool:
    return bool(
        re.search(
            r"\b(today|yesterday|now|\d+\s+(?:minute|hour|day|week|month)s?\s+ago)\b",
            value,
            flags=re.IGNORECASE,
        )
        or re.search(r"\b\d{1,2}:\d{2}\s*(?:am|pm)\b", value, flags=re.IGNORECASE)
    )


def _extract_detail_sections(soup: BeautifulSoup) -> dict[str, str]:
    ignored_headings = {
        "send an enquiry",
        "enquiry sent",
        "you might also like...",
        "share this ad",
        "report this ad",
        "get email recommendation",
        "connect with us",
        "company",
        "customers",
        "legals",
    }
    sections: dict[str, str] = {}

    for heading in soup.find_all(["h2", "h3", "h4"]):
        heading_text = _clean_text(heading.get_text(" ", strip=True))
        if not heading_text or heading_text.lower() in ignored_headings:
            continue

        body_parts: list[str] = []
        for sibling in heading.next_siblings:
            if isinstance(sibling, Tag) and sibling.name in {"h2", "h3", "h4"}:
                break

            if isinstance(sibling, Tag):
                text = _clean_text(sibling.get_text(" ", strip=True))
            else:
                text = _clean_text(str(sibling))

            if text:
                body_parts.append(text)

        body = _clean_text(" ".join(body_parts))
        if body:
            sections[heading_text] = body[:4000]

    return sections


def _detail_description_from_sections(sections: dict[str, str]) -> str:
    preferred_headings = [
        "Summary",
        "Location Details",
        "About the Business",
        "About the Opportunity",
        "Marketing support",
        "Training provided",
        "Skills",
        "History",
    ]
    parts = [
        f"{heading}: {sections[heading]}"
        for heading in preferred_headings
        if sections.get(heading)
    ]

    if not parts:
        parts = [f"{heading}: {body}" for heading, body in sections.items()]

    return _clean_text(" ".join(parts))[:8000]


def _select_text(card: Tag, selector: str | None) -> str:
    if not selector:
        return ""

    element = card.select_one(selector)
    return element.get_text(" ", strip=True) if element else ""


def _first_text(card: Tag, selectors: list[str]) -> str:
    for selector in selectors:
        element = card.select_one(selector)
        if element:
            text = element.get_text(" ", strip=True)
            if text:
                return text
    return ""


def _select_link(card: Tag, page_url: str, selector: str | None) -> str:
    element = card.select_one(selector or "a")
    if not element or not element.has_attr("href"):
        return ""
    return urljoin(page_url, str(element["href"]))


def _find_date_text(card: Tag) -> str:
    date_candidates = card.select("time, [datetime], [class*='date'], [class*='posted'], [class*='time']")

    for candidate in date_candidates:
        if candidate.has_attr("datetime"):
            return str(candidate["datetime"])

        text = candidate.get_text(" ", strip=True)
        if text:
            return text

    text = card.get_text(" ", strip=True)
    relative_match = re.search(
        r"\b(now|today|yesterday|\d+\s+(?:minute|hour|day|week|month)s?\s+ago)\b",
        text,
        flags=re.IGNORECASE,
    )
    if relative_match:
        return relative_match.group(1)

    return ""


def _clean_text(value: str | None) -> str:
    cleaned = " ".join((value or "").split())
    return re.sub(r"\s*more\s*\W*$", "", cleaned, flags=re.IGNORECASE).strip()


def _dedupe_listings(listings: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict] = []

    for listing in listings:
        key = (listing.get("title", "").lower(), listing.get("url", "").lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(listing)

    return deduped
