#superbase_writer.py

import json
import requests
from typing import List, Tuple, Optional
from urllib.parse import urlparse
from .config import SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_TABLE

REST = f"{SUPABASE_URL.rstrip('/')}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation,resolution=merge-duplicates",
}

def _canon(u: str) -> str:
    try:
        p = urlparse(u or "")
        return f"{p.scheme}://{p.netloc}{p.path}"
    except Exception:
        return u or ""

def _row(a: dict) -> dict:
    pub_raw = a.get("Published") or a.get("PublishedAt") or ""
    published = pub_raw.split("T", 1)[0] if isinstance(pub_raw, str) and "T" in pub_raw else pub_raw

    # keywords fallback
    kw = a.get("Keywords")
    if not kw and isinstance(a.get("Topic"), list):
        kw = ", ".join(a["Topic"]) if a["Topic"] else "Energy"
    if not kw:
        kw = "Energy"

    # topic as json array
    topic = a.get("Topic") if isinstance(a.get("Topic"), list) else []

    region = a.get("Region", "Global") or "Global"

    return {
        "title": a.get("Title", ""),
        "link": _canon(a.get("Link", "")),
        "source": a.get("Source", ""),
        "published": published,        # DATE (YYYY-MM-DD) or empty
        "summary": a.get("Summary", ""),
        "keywords": kw,
        "region": region,
        "topic": topic,                # jsonb array
    }

def write_to_supabase(items: List[dict]) -> Tuple[int, List[str], Optional[dict]]:
    def chunks(seq, n):
        for i in range(0, len(seq), n):
            yield seq[i:i+n]

    total, errs, sample = 0, [], None
    payload_rows = [_row(i) for i in (items or [])]

    for ch in chunks(payload_rows, 200):
        r = requests.post(
            f"{REST}/{SUPABASE_TABLE}",
            headers=HEADERS,
            params={"on_conflict": "link"},
            data=json.dumps(ch),
            timeout=25,
        )
        if r.status_code >= 400:
            errs.append(f"upsert {r.status_code}: {r.text[:300]}")
            if sample is None:
                sample = {"chunk": ch[:2], "error": r.text}
            continue
        data = r.json() if r.text else []
        total += len(data)

    return total, errs, sample
