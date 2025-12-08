# back/adapters/events/aca_playwright.py
from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from playwright.sync_api import sync_playwright


ACA_SOURCES = [
    # Country pages to scrape
    ("Singapore",  "https://www.allconferencealert.com/singapore/energy-conference.html"),
    ("Malaysia",   "https://www.allconferencealert.com/malaysia/energy-conference.html"),
    ("Philippines","https://www.allconferencealert.com/philippines/energy-conference.html"),
]

MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "SEPT": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

def _infer_year_from_header(title_text: str) -> Optional[int]:
    """
    Header usually looks like:
      'Energy Conference in Singapore 2025-2026'
       -> return first year (2025)
    """
    if not title_text:
        return None
    m = re.search(r"(\d{4})(?:\s*[-–]\s*(\d{4}))?", title_text)
    if m:
        return int(m.group(1))
    return None

def _parse_day_mon(day_mon: str, fallback_year: Optional[int]) -> Optional[str]:
    """
    Accepts '02 Nov' or '2 Nov'. Returns ISO date string 'YYYY-MM-DD' using fallback_year.
    """
    if not day_mon:
        return None
    s = day_mon.strip().upper().replace(".", "")
    m = re.match(r"(?P<d>\d{1,2})\s+(?P<mon>[A-Z]{3,4})", s)
    if not m:
        return None
    d = int(m.group("d"))
    mon = MONTHS.get(m.group("mon"))
    if not mon:
        return None
    y = fallback_year or datetime.now().year
    try:
        return datetime(y, mon, d).date().isoformat()
    except ValueError:
        return None

def _clean_text(s: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def fetch_allconferencealert_events() -> List[Dict]:
    """
    Uses Playwright (Chromium) to render JS and scrape the events table.
    Normalized output rows with keys:
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
            print("[ACA] HTML size:", len(html))


            # Wait for table to render. The site shows a spinner first.
            # We wait for *any* table row to appear.
            try:
                page.wait_for_selector("table tbody tr", timeout=15000)
                print(f"[ACA] Table detected for {url}")
            except Exception:
                # dump the page title to help debug
                print(f"[ACA] WARNING: no table found for {url} (title={page.title()!r})")
                continue

            # Try to get header text to infer year
            heading_text = ""
            try:
                # Header near the table area
                heading_el = page.query_selector("h1,h2,h3")
                heading_text = heading_el.inner_text() if heading_el else ""
            except Exception:
                pass
            fallback_year = _infer_year_from_header(heading_text)

            # Iterate rows
            rows = page.query_selector_all("table tbody tr")
            for tr in rows:
                tds = tr.query_selector_all("td")
                if len(tds) < 3:
                    continue

                date_text = _clean_text(tds[0].inner_text())          # e.g., "02 Nov"
                title_el = tds[1].query_selector("a") or tds[1]
                title_text = _clean_text(title_el.inner_text())
                href = title_el.get_attribute("href") if title_el else None
                if href and href.startswith("/"):
                    # Convert relative to absolute
                    href = url.rstrip("/") + href

                venue_text = _clean_text(tds[2].inner_text())         # e.g., "Singapore, Singapore"

                # Split venue → city, country
                city = None
                region = None
                if venue_text:
                    parts = [p.strip() for p in venue_text.split(",") if p.strip()]
                    if len(parts) == 1:
                        # Sometimes the site repeats country only (e.g., "Singapore")
                        city = parts[0].title()
                        region = parts[0].title()
                    else:
                        city = parts[0].title()
                        region = parts[-1].title()

                starts_on = _parse_day_mon(date_text, fallback_year)

                if title_text and starts_on:
                    out.append({
                        "title": title_text,
                        "region": region or country_name,   # fallback to page country
                        "city": city,
                        "venue": None,
                        "starts_on": starts_on,
                        "ends_on": None,
                        "link": href or url,
                        "source": "AllConferenceAlert",
                    })

            page.close()

        context.close()
        browser.close()

    return out
