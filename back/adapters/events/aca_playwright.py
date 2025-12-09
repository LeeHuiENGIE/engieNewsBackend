# back/adapters/events/aca_playwright.py
from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Optional

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup  # type: ignore


ACA_SOURCES = [
    ("Singapore",  "https://www.allconferencealert.com/singapore/energy-conference.html"),
    ("Malaysia",   "https://www.allconferencealert.com/malaysia/energy-conference.html"),
    ("Philippines","https://www.allconferencealert.com/philippines/energy-conference.html"),
]

# Accept short + long month names
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

def _clean_text(s: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


# Date formats: "20 December 2025", "13th Jan 2026"
_DATE_RE = re.compile(
    r"(?P<d>\d{1,2})(?:ST|ND|RD|TH)?\s+(?P<mon>[A-Za-z]+)\s+(?P<y>\d{4})"
)

def _parse_full_date(text: str) -> Optional[str]:
    if not text:
        return None
    m = _DATE_RE.search(text)
    if not m:
        return None

    d = int(m.group("d"))
    mon_raw = m.group("mon").upper()
    mon = MONTHS.get(mon_raw) or MONTHS.get(mon_raw[:3])
    if not mon:
        return None

    y = int(m.group("y"))
    try:
        return datetime(y, mon, d).date().isoformat()
    except ValueError:
        return None


def _extract_events_from_html(html: str, country_name: str) -> List[Dict]:
    """
    Parse the new ACA layout (div/card-based) into normalized event rows:
    title, region, city, venue, starts_on, ends_on, link, source
    """
    soup = BeautifulSoup(html, "lxml")

    # Try to find "Upcoming Energy Conferences in <country>"
    header_pat = re.compile(
        rf"Upcoming Energy Conferences in .*{re.escape(country_name)}",
        re.I,
    )
    header_node = soup.find(string=header_pat)

    if header_node:
        container = header_node.parent
        for _ in range(4):
            if container.parent:
                container = container.parent
        section_soup = container
    else:
        section_soup = soup

    section_text = section_soup.get_text("\n", strip=True)

    events: List[Dict] = []

    # Split by "View Event" since each card ends with that button
    chunks = re.split(r"View Event", section_text)

    for raw_chunk in chunks:
        lines = [ln.strip() for ln in raw_chunk.splitlines() if ln.strip()]

        if len(lines) < 3:
            continue

        title = None
        date_line = None
        loc_line = None

        # Detect title
        for ln in lines:
            if any(k in ln for k in _TITLE_KEYWORDS):
                title = ln
                break

        # Detect date
        for ln in lines:
            if _DATE_RE.search(ln):
                date_line = ln
                break

        # Detect location (City, Country)
        for ln in lines:
            if "," in ln and country_name.lower() in ln.lower():
                loc_line = ln
                break

        if not (title and date_line and loc_line):
            continue

        starts_on = _parse_full_date(date_line)
        if not starts_on:
            continue

        city = loc_line.split(",")[0].strip().title()

        events.append(
            {
                "title": title,
                "region": country_name,
                "city": city,
                "venue": None,
                "starts_on": starts_on,
                "ends_on": None,
                "link": None,  # Filled in later
                "source": "AllConferenceAlert",
            }
        )

    # ---------------------------
    # SECOND PASS → ATTACH LINKS
    # ---------------------------
    for ev in events:
        title_pat = re.compile(re.escape(ev["title"]), re.I)

        title_node = section_soup.find(string=title_pat)
        if not title_node:
            title_node = soup.find(string=title_pat)
        if not title_node:
            continue

        # climb up until the card wrapper
        card = title_node.parent
        for _ in range(6):
            if card.parent:
                card = card.parent

        # Find the "View Event" link
        link_el = card.find("a", href=True, string=re.compile(r"view event", re.I))

        if not link_el:
            # fallback: any anchor inside card
            link_el = card.find("a", href=True)

        if not link_el:
            continue

        href = link_el.get("href", "").strip()
        if not href:
            continue

        # Absolute URL
        if href.startswith("/"):
            href = "https://www.allconferencealert.com" + href

        ev["link"] = href

    return events


def fetch_allconferencealert_events() -> List[Dict]:
    """
    Fetch + parse new ACA layout using Playwright (render JS),
    returning normalized rows ready for Supabase.
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
