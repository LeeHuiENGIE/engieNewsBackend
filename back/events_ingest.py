# back/events_ingest.py
from __future__ import annotations
from typing import Dict, List

from back.adapters.events.aca_playwright import fetch_allconferencealert_events
from back.supabase_events import upsert_events


def run_events_ingest() -> Dict:
    """
    Scrape AllConferenceAlert (JS-rendered via Playwright) for SG/MY/PH energy events,
    normalize them into (title, region, city, venue, starts_on, ends_on, link, source),
    then upsert into Supabase (public.events).
    """
    # 1) Fetch & normalize (already normalized by the fetcher)
    rows: List[Dict] = fetch_allconferencealert_events()
    raw_count = len(rows)

    # 2) Upsert to Supabase
    inserted, skipped = upsert_events(rows)

    return {
        "raw": raw_count,
        "normalized": raw_count,  # fetcher returns normalized rows
        "upserted": inserted,
        "skipped": skipped,
    }
