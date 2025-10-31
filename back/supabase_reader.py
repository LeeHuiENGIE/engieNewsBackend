# back/supabase_reader.py
import requests
from urllib.parse import urlparse
from datetime import datetime
from .config import SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_TABLE

REST = f"{SUPABASE_URL.rstrip('/')}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Accept": "application/json",
}

def _domain(link: str) -> str:
    try:
        return urlparse(link or "").netloc
    except Exception:
        return ""

def _infer_region(source: str, link: str) -> str:
    t = f"{source or ''} {link or ''}".lower()
    for suf, name in [
        (".ph", "Philippines"), (".sg", "Singapore"), (".my", "Malaysia"),
        (".id", "Indonesia"),   (".vn", "Vietnam"),   (".th", "Thailand"),
    ]:
        if suf in t: return name
    return "Global"

def _to_frontend(row: dict) -> dict:
    link = row.get("link", "")
    source = row.get("source") or _domain(link)
    region = row.get("region") or _infer_region(source, link)
    topic = row.get("topic")
    if not isinstance(topic, list):
        topic = []
    keywords = row.get("keywords") or ""   # ← ADDED

    return {
        "Title": row.get("title", ""),
        "Link": link,
        "Source": source,
        "PublishedAt": row.get("published") or "",
        "Summary": row.get("summary", ""),
        "Topic": topic,
        "Region": region,
        "Keywords": keywords,              # ← ADDED
        "Bookmarked": False,
        "id": link or row.get("id", ""),
    }

def get_articles() -> list:
    params = {
        "select": "id,title,link,source,published,summary,keywords,region,topic,inserted_at,updated_at",
        "order": "published.desc",
        "limit": "1000",
    }
    r = requests.get(f"{REST}/{SUPABASE_TABLE}", headers=HEADERS, params=params, timeout=20)
    r.raise_for_status()
    rows = r.json() if r.text else []
    out = [_to_frontend(x) for x in rows]

    def ts(a):
        try:
            return datetime.fromisoformat((a.get("PublishedAt") or "").replace("Z", "+00:00"))
        except Exception:
            return datetime.min

    out.sort(key=ts, reverse=True)
    return out
