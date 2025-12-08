# back/adapters/events/aca_playwright.py
from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Optional

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup  # type: ignore


ACA_SOURCES = [
    # Country pages to scrape
    ("Singapore",  "https://www.allconferencealert.com/singapore/energy-conference.html"),
    ("Malaysia",   "https://www.allconferencealert.com/malaysia/energy-conference.html"),
    ("Philippines","https://www.allconferencealert.com/philippines/energy-conference.html"),
]

# Accept both short and long month names
MONTHS = {
    "JAN": 1, "JANUARY": 1,
    "FEB": 2, "FEBRUARY": 2,
    "MAR": 3, "MARCH": 3,
    "APR": 4, "APRIL": 4,
    "MAY": 5,
    "JUN": 6, "JUNE": 6,
    "JUL": 7, "JULY": 7,
    "AUG": 8, "AUGUST": 8,
    "SEP": 9, "SEPT": 9, "SEPTEMBER": 9,
    "OCT": 10, "OCTOBER": 10,
    "NOV": 11, "NOVEMBER": 11,
    "DEC": 12, "DECEMBER": 12,
}


def _clean_text(s: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


# e.g. "20 December 2025", "13th Jan 2026"
_DATE_RE = re.compile(
    r"(?P<d>\d{1,2})(?:ST|ND|RD|TH)?\s+(?P<mon>[A-Z][a-zA-Z]+)\s+(?P<y>\d{4})"
)


def _parse_full_date(text: str) -> Optional[str]:
    """
    Parse dates like '20 December 2025' or '13th Jan 2026' → 'YYYY-MM-DD'
    """
    if not text:
        return None
    m = _DATE_RE.search(text)
    if not m:
        return None

    d = int(m.group("d"))
    mon_raw = m.group("mon").upper()
    # Try full month, then first 3 letters
    mon = MONTHS.get(mon_raw) or MONTHS.get(mon_raw[:3])
    if not mon:
        return None
    y = int(m.group("y"))
    try:
        return datetime(y, mon, d).date().isoformat()
    except ValueError:
        return None


_TITLE_KEYWORDS = (
    "Conference",
    "Congress",
    "Summit",
    "Symposium",
    "Meeting",
    "Forum",
    "Expo",
    "Workshop",
)


def _extract_events_from_html(html: str, country_name: str) -> List[Dict]:
    """
    Parse the new ACA layout (Tailwind + div-based cards) into normalized rows:
      title, region, city, venue, starts_on, ends_on, link, source
    """
    soup = BeautifulSoup(html, "lxml")

    # Try to narrow to "Upcoming Energy Conferences in <country>" section
    header_pat = re.compile(
        rf"Upcoming Energy Conferences in .*{re.escape(country_name)}",
        re.I,
    )
    header_node = soup.find(string=header_pat)
    if header_node:
        container = header_node.parent
        # Walk up a few levels to capture the surrounding conference list wrapper
        for _ in range(4):
            if container.parent:
                container = container.parent
        section_text = container.get_text("\n", strip=True)
    else:
        # Fallback: whole page text
        section_text = soup.get_text("\n", strip=True)

    events: List[Dict] = []

    # Each event card ends with a "View Event" button; use that to split.
    chunks = re.split(r"View Event", section_text)

    for raw_chunk in chunks:
        lines = [ln.strip() for ln in raw_chunk.splitlines() if ln.strip()]
        if len(lines) < 3:
            continue

        title = None
        date_line = None
        loc_line = None

        # Find a title-looking line
        for ln in lines:
            if any(k in ln for k in _TITLE_KEYWORDS):
                title = ln
                break

        # Find a date-looking line
        for ln in lines:
            if _DATE_RE.search(ln):
                date_line = ln
                break

        # Find a location line that references the country and has a comma
        for ln in lines:
            if "," in ln and country_name.lower() in ln.lower():
                loc_line = ln
                break

        if not (title and date_line and loc_line):
            continue

        starts_on = _parse_full_date(date_line)
        if not starts_on:
            continue

        # Location: "City, Country"
        city = loc_line.split(",")[0].strip().title()

        events.append(
            {
                "title": title,
                "region": country_name,
                "city": city,
                "venue": None,
                "starts_on": starts_on,
                "ends_on": None,
                "link": None,  # could parse event URL later if needed
                "source": "AllConferenceAlert",
            }
        )

    return events


def fetch_allconferencealert_events() -> List[Dict]:
    """
    Uses Playwright (Chromium) to render JS and scrape the new ACA
    div/card-based layout. Normalized output rows with keys:
      title, region, city, venue, starts_on, ends_on, link, source
    """
    out: List[Dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/118.0.0.0 Safari/537.36"
            )
        )

        for country_name, url in ACA_SOURCES:
            page = context.new_page()
            print(f"[ACA] GET {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)

            html = page.content()
            print(f"[ACA] HTML size: {len(html)}")

            rows = _extract_events_from_html(html, country_name)
            print(f"[ACA] Parsed {len(rows)} rows for {country_name}")
            out.extend(rows)

            page.close()

        context.close()
        browser.close()

    print(f"[ACA] Total parsed events: {len(out)}")
    return out
