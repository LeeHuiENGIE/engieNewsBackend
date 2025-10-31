# -----------------------------
# config.py · ENGIE News Repo (RSS-only)
# -----------------------------
import os
from typing import List

# ---------- helpers ----------
def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}

def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip())
    except Exception:
        return default

def _csv(name: str, default: List[str]) -> List[str]:
    raw = os.getenv(name)
    if not raw:
        return default
    return [s.strip() for s in raw.split(",") if s.strip()]

# ============ GLOBAL ============
DAYS_LIMIT = _get_int("DAYS_LIMIT", 7)   # keep only recent N days

# ============ SUPABASE ============
SUPABASE_URL         = os.getenv("SUPABASE_URL", "")          # e.g. https://xxxx.supabase.co
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")  # service_role key (backend only)
SUPABASE_TABLE       = os.getenv("SUPABASE_TABLE", "news")
USE_SUPABASE         = _get_bool("USE_SUPABASE", True)        # flip to False to fall back to Airtable

# ============ RSS ============
RSS_ENABLED   = _get_bool("RSS_ENABLED", True)
RSS_MAX_ITEMS = _get_int("RSS_MAX_ITEMS", 20)

RSS_FEEDS = [
    {"name": "Eco-Business News",   "url": "https://www.eco-business.com/feeds/news/"},
    {"name": "Asian Power (GNews)", "url": "https://news.google.com/rss/search?q=site:asian-power.com&hl=en-SG&gl=SG&ceid=SG:en"},
    {"name": "IEMOP (GNews)",       "url": "https://news.google.com/rss/search?q=site:iemop.ph&hl=en-SG&gl=SG&ceid=SG:en"},
    {"name": "Power Philippines",   "url": "https://powerphilippines.com/feed/"},
    {"name": "The Business Times (GNews)",
     "url": "https://news.google.com/rss/search?q=site:businesstimes.com.sg&hl=en-SG&gl=SG&ceid=SG:en"},
    {"name": "The Edge Malaysia (GNews)",
     "url": "https://news.google.com/rss/search?q=site:theedgemalaysia.com&hl=en-SG&gl=SG&ceid=SG:en"},
    {"name": "Reuters (GNews)",
     "url": "https://news.google.com/rss/search?q=site:reuters.com+energy+OR+climate+OR+renewable&hl=en-SG&gl=SG&ceid=SG:en"},
]

# ============ Keyword rules (used by rss_adapter / filters) ============
ANY_KEYWORDS = _csv("ANY_KEYWORDS", [
    "engie", "energy", "carbon", "regulation", "policy",
    "emissions", "solar", "wind", "fuel", "battery",
    "renewable", "storage", "grid", "power", "electricity",
    "Singapore", "Malaysia", "Philippines",
])
ALL_KEYWORDS = _csv("ALL_KEYWORDS", ["energy"])

# Title-only keyword rules (stricter)
TITLE_KEYWORDS_ANY = _csv("TITLE_KEYWORDS_ANY", [
    "engie",
    "solar", "energy", "hydrogen", "grid", "wind", "carbon", "LNG", "district cooling", "fuel",
    "policy", "regulation",
    "emissions",
    "renewable", "storage", "power", "electricity",
])
TITLE_KEYWORDS_ALL = _csv("TITLE_KEYWORDS_ALL", [])
