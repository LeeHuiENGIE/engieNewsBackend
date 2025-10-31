# back/adapters/events/normalize.py
from __future__ import annotations
from typing import Dict, Optional, Tuple
import re
from datetime import datetime

__all__ = ["parse_date_range", "normalize_location"]

ASEAN_CANON = {
    "singapore": "Singapore",
    "malaysia": "Malaysia",
    "indonesia": "Indonesia",
    "thailand": "Thailand",
    "vietnam": "Vietnam",
    "philippines": "Philippines",
    "cambodia": "Cambodia",
    "laos": "Laos",
    "myanmar": "Myanmar",
    "brunei": "Brunei",
    "brunei darussalam": "Brunei",
    "lao pdr": "Laos",
}

_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "SEPT": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

def _year_guess() -> int:
    # basic guess: this year (fallback)
    return datetime.now().year

def parse_date_range(date_raw: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Accepts strings like:
      'OCT 20–21', 'OCT 20-21', 'OCT 13, 2025', 'DEC 9-10 2026'
    Returns ISO dates: ('YYYY-MM-DD', 'YYYY-MM-DD|None')
    If parsing fails, returns (None, None).
    """
    if not date_raw:
        return (None, None)
    s = date_raw.strip().upper().replace("–", "-").replace("—", "-")

    # Examples: OCT 20-21 [2025]
    m = re.match(r"^(?P<mon>[A-Z]{3,4})\s+(?P<d1>\d{1,2})(?:\s*-\s*(?P<d2>\d{1,2}))?(?:[, ]+(?P<y>\d{4}))?$", s)
    if m:
        mon = _MONTHS.get(m.group("mon"), None)
        if not mon: 
            return (None, None)
        y = int(m.group("y")) if m.group("y") else _year_guess()
        d1 = int(m.group("d1"))
        d2 = int(m.group("d2")) if m.group("d2") else None
        try:
            start = datetime(y, mon, d1).date().isoformat()
            end = datetime(y, mon, (d2 or d1)).date().isoformat()
            return (start, end if d2 else None)
        except ValueError:
            return (None, None)

    # Example: OCT 13, 2025 (comma variant)
    m = re.match(r"^(?P<mon>[A-Z]{3,4})\s+(?P<d1>\d{1,2}),\s*(?P<y>\d{4})$", s)
    if m:
        mon = _MONTHS.get(m.group("mon"), None)
        if not mon: 
            return (None, None)
        y = int(m.group("y"))
        d1 = int(m.group("d1"))
        try:
            start = datetime(y, mon, d1).date().isoformat()
            return (start, None)
        except ValueError:
            return (None, None)

    return (None, None)

def normalize_location(location_raw: str) -> Dict[str, Optional[str]]:
    """
    Roughly split a location string into (city, region) and map region to ASEAN canon.
    Examples: 'SINGAPORE', 'LONDON', 'HOUSTON', 'KUALA LUMPUR, MALAYSIA'
    """
    if not location_raw:
        return {"city": None, "region": None}
    s = location_raw.strip()
    parts = [p.strip() for p in re.split(r"[,/|-]", s) if p.strip()]
    city = parts[0].title() if parts else None

    region = None
    for p in parts[::-1]:
        key = p.strip().lower()
        if key in ASEAN_CANON:
            region = ASEAN_CANON[key]
            break
        # single-token city that equals region (e.g., 'SINGAPORE')
        if key in ("singapore",):
            region = "Singapore"
            break

    # If only single token and it matches ASEAN country
    if not region and len(parts) == 1 and parts[0].strip().lower() in ASEAN_CANON:
        region = ASEAN_CANON[parts[0].strip().lower()]
        city = region

    return {"city": city, "region": region}
