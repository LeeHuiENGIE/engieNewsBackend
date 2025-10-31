# back/adapters/events/aca.py
from __future__ import annotations
import os
import re
import sys
from typing import Dict, List, Optional
from datetime import date, timedelta

# ---------- HTTP layer ----------
try:
    import cloudscraper  # type: ignore
    _SCRAPER = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
    def http_get(url: str):
        # Referer + desktop UA often helps
        return _SCRAPER.get(
            url,
            timeout=25,
            headers={
                "Referer": "https://www.google.com/",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
except Exception:
    import requests  # type: ignore
    _SCRAPER = requests.Session()
    _SCRAPER.headers.update({
        "Referer": "https://www.google.com/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    })
    def http_get(url: str):
        return _SCRAPER.get(url, timeout=25)

from bs4 import BeautifulSoup  # type: ignore

# ---------- Utils ----------
MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "SEPT": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}
CANON = {
    "Singapore": "Singapore",
    "Malaysia": "Malaysia",
    "Philippines": "Philippines",
    "Viet Nam": "Vietnam",
    "Vietnam": "Vietnam",
    "Indonesia": "Indonesia",
    "Thailand": "Thailand",
    "Brunei": "Brunei",
    "Brunei Darussalam": "Brunei",
    "Lao Pdr": "Laos",
    "Laos": "Laos",
    "Cambodia": "Cambodia",
    "Myanmar": "Myanmar",
}

def _debug(msg: str):
    print(f"[ACA] {msg}", file=sys.stdout, flush=True)

def _ensure_debug_dir() -> str:
    d = os.path.join(os.path.dirname(__file__), "..", "..", "_debug")
    d = os.path.abspath(d)
    os.makedirs(d, exist_ok=True)
    return d

def _to_iso_upcoming(day_mon_text: str) -> Optional[str]:
    s = day_mon_text.strip().upper().replace(".", "")
    s = re.sub(r"\s+", " ", s)
    m = re.match(r"^(\d{1,2})\s+([A-Z]{3,4})$", s)
    if not m:
        return None
    d = int(m.group(1))
    mon = MONTHS.get(m.group(2))
    if not mon:
        return None
    today = date.today()
    y = today.year
    try_date = date(y, mon, d)
    if try_date < today - timedelta(days=1):
        try_date = date(y + 1, mon, d)
    return try_date.isoformat()

def _split_city_country(venue_text: str) -> Dict[str, Optional[str]]:
    s = venue_text.replace("\xa0", " ").strip()
    parts = [p.strip() for p in re.split(r",|\u2013|\u2014|-|/", s) if p.strip()]
    city = parts[0].title() if parts else None
    country = parts[-1].title() if parts else None
    region = CANON.get(country, country)
    if region and (not city or city.lower() == str(region).lower()):
        city = region
    return {"city": city, "region": region}

# ---------- Parsers ----------
def _extract_rows_from_table(table) -> List[Dict]:
    out: List[Dict] = []
    tb = table.find("tbody") or table
    for tr in tb.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if len(cells) < 3:
            continue
        date_text = cells[0].get_text(" ", strip=True)
        title = cells[1].get_text(" ", strip=True)
        venue = cells[2].get_text(" ", strip=True)
        iso = _to_iso_upcoming(date_text)
        if not title or not iso:
            continue
        loc = _split_city_country(venue)
        out.append({
            "title": title,
            "region": loc.get("region"),
            "city": loc.get("city"),
            "venue": None,
            "starts_on": iso,
            "ends_on": None,
            "link": None,
            "source": "AllConferenceAlert",
        })
    return out

def _extract_by_header_match(soup) -> List[Dict]:
    for t in soup.find_all("table"):
        headers = [th.get_text(" ", strip=True) for th in t.find_all("th")]
        header_line = " | ".join(headers).lower()
        if "date" in header_line and "venue" in header_line:
            return _extract_rows_from_table(t)
    return []

def _extract_any_table_with_3cols(soup) -> List[Dict]:
    # Broad fallback: take any table that *looks* like [date, title, venue]
    for t in soup.find_all("table"):
        first_row = (t.find("tbody") or t).find("tr")
        if not first_row:
            continue
        cells = first_row.find_all(["td","th"])
        if len(cells) >= 3:
            rows = _extract_rows_from_table(t)
            # sanity: at least 2 rows that parse as dates
            if sum(1 for r in rows if r["starts_on"]) >= 2:
                return rows
    return []

def _extract_rows_loosely(soup) -> List[Dict]:
    # Non-table fallback: sniff 3 adjacent chunks that look like date/title/venue
    out: List[Dict] = []
    texts = [el.get_text(" ", strip=True) for el in soup.select("div,li,p,span") if el.get_text(strip=True)]
    for i in range(0, max(0, len(texts) - 2)):
        d, ti, ve = texts[i:i+3]
        iso = _to_iso_upcoming(d)
        if iso and len(ti) > 4 and len(ve) > 3:
            loc = _split_city_country(ve)
            out.append({
                "title": ti,
                "region": loc.get("region"),
                "city": loc.get("city"),
                "venue": None,
                "starts_on": iso,
                "ends_on": None,
                "link": None,
                "source": "AllConferenceAlert",
            })
    return out

# ---------- Entrypoints ----------
def fetch_aca_country(url: str, fallback_region: str) -> List[Dict]:
    _debug(f"GET {url}")
    r = http_get(url)
    _debug(f"HTTP {r.status_code} for {url}")
    html = r.text or ""
    # Save for inspection
    dbg_dir = _ensure_debug_dir()
    fname = os.path.join(dbg_dir, f"aca_{fallback_region.lower()}.html")
    try:
        with open(fname, "w", encoding="utf-8") as f:
            f.write(html)
        _debug(f"Saved HTML → {fname} ({len(html)} bytes)")
    except Exception as e:
        _debug(f"Save failed: {e}")

    if r.status_code != 200 or len(html) < 500:
        # Likely blocked / empty shell
        return []

    soup = BeautifulSoup(html, "lxml")

    # Strategy 1: table with Date/Conference/Venue headers
    rows = _extract_by_header_match(soup)
    if rows:
        return rows

    # Strategy 2: any 3-col table with at least 2 valid date rows
    rows = _extract_any_table_with_3cols(soup)
    if rows:
        return rows

    # Strategy 3: loose sniff
    rows = _extract_rows_loosely(soup)

    # Apply fallback region when venue parsing fails
    for r in rows:
        if not r["region"]:
            r["region"] = fallback_region
    return rows

def fetch_aca_all() -> List[Dict]:
    pages = [
        ("https://www.allconferencealert.com/singapore/energy-conference.html", "Singapore"),
        ("https://www.allconferencealert.com/malaysia/energy-conference.html", "Malaysia"),
        ("https://www.allconferencealert.com/philippines/energy-conference.html", "Philippines"),
    ]
    total: List[Dict] = []
    for url, region in pages:
        try:
            got = fetch_aca_country(url, region)
            _debug(f"Parsed {len(got)} rows from {url}")
            total.extend(got)
        except Exception as e:
            _debug(f"Parse error on {url}: {e}")
    _debug(f"Total ACA rows: {len(total)}")
    return total
