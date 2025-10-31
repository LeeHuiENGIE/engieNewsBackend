# back/fetch_news.py (RSS-only)
from typing import List
from .config import DAYS_LIMIT, RSS_ENABLED
from .adapters.rss_adapter import get_news_from_rss

def fetch_filtered_news(days_limit: int = DAYS_LIMIT) -> List[dict]:
    """
    Fetch news items using RSS only, respecting days_limit.
    Returns a list of normalized article dicts that downstream writer expects.
    """
    items: List[dict] = []

    if RSS_ENABLED:
        rss_items = get_news_from_rss(days_limit=days_limit)
        if rss_items:
            items.extend(rss_items)

    # De-duplicate by Link (case-insensitive)
    seen = set()
    deduped = []
    for it in items:
        link = (it.get("Link") or "").strip()
        key = link.lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(it)

    return deduped
