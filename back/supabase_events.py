# back/supabase_events.py
from __future__ import annotations
import os, math
from typing import List, Dict, Tuple
from datetime import date
from supabase import create_client, Client

__all__ = ["upsert_events", "fetch_upcoming_events"]

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

def _client() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def _norm(s: str | None) -> str:
    return (s or "").strip().lower()

def _key(row: Dict) -> tuple[str, str, str]:
    # mirrors your dedupe logic: title + region + starts_on
    return (_norm(row.get("title")),
            _norm(row.get("region")),
            (row.get("starts_on") or "").strip())

def upsert_events(rows: List[Dict]) -> Tuple[int, int]:
    """
    Upsert normalized rows into public.events.
    Expected keys per row: title, region, city, venue, starts_on, ends_on, link, source
    Returns (written_count, skipped_count).
    """
    if not rows:
        return (0, 0)

    # 1) sanitize + keep only valid rows
    cleaned: List[Dict] = []
    for r in rows:
        title = (r.get("title") or "").strip()
        starts_on = (r.get("starts_on") or "").strip()
        if not title or not starts_on:
            continue
        cleaned.append({
            "title": title,
            "region": r.get("region"),
            "city": r.get("city"),
            "venue": r.get("venue"),
            "starts_on": starts_on,
            "ends_on": (r.get("ends_on") or None),
            "link": r.get("link"),
            "source": r.get("source") or "AllConferenceAlert",
        })

    if not cleaned:
        return (0, len(rows))

    # 2) dedupe **within this batch** to avoid the Postgres 21000 error
    seen = set()
    deduped: List[Dict] = []
    for r in cleaned:
        k = _key(r)
        if k in seen:
            continue
        seen.add(k)
        deduped.append(r)

    # 3) upsert in small chunks (e.g., 200) and ignore duplicates against existing rows
    sb = _client()
    written_total = 0
    chunk_size = 200
    for i in range(0, len(deduped), chunk_size):
        chunk = deduped[i:i + chunk_size]
        resp = sb.table("events").upsert(
            chunk,
            on_conflict="dedupe_key",
            ignore_duplicates=True  # extra safety vs existing rows
        ).execute()
        # supabase-py returns inserted/updated rows in resp.data
        written_total += len(resp.data or [])

    skipped = len(rows) - written_total
    return (written_total, max(0, skipped))

def fetch_upcoming_events() -> List[Dict]:
    sb = _client()
    today = date.today().isoformat()
    resp = sb.table("events") \
             .select("*") \
             .gte("starts_on", today) \
             .order("starts_on", desc=False) \
             .execute()
    return resp.data or []
