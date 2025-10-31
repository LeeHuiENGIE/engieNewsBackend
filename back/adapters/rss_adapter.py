# back/adapters/rss_adapter.py
import re
import logging
import feedparser
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlunparse
from dateutil import parser as dtparser

# ✅ relative import from back.config
from ..config import (
    RSS_FEEDS, RSS_ENABLED, RSS_MAX_ITEMS,
    TITLE_KEYWORDS_ANY, TITLE_KEYWORDS_ALL,
)

UA = {"User-Agent": "Mozilla/5.0 (ENGIE-NewsBot/1.0)"}

# ---------------------------------------------------------------------
# URL / source helpers
# ---------------------------------------------------------------------
def _canonical_url(u: str) -> str:
    try:
        p = urlparse(u)
        return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))
    except Exception:
        return u or ""

def _source_from_url(u: str) -> str:
    try:
        return urlparse(u).netloc or ""
    except Exception:
        return ""

def _is_gnews(u: str) -> bool:
    try:
        return urlparse(u).netloc.endswith("news.google.com")
    except Exception:
        return False

def _gnews_source_name(entry, fallback: str) -> str:
    try:
        src = getattr(entry, "source", None) or getattr(entry, "source_detail", None)
        if isinstance(src, dict):
            title = (src.get("title") or src.get("href") or "").strip()
            if title:
                return title
        elif isinstance(src, str) and src.strip():
            return src.strip()
    except Exception:
        pass
    # last resort: parse " - Publisher" at end of title
    try:
        t = (getattr(entry, "title", "") or "")
        m = re.search(r"\s[-–]\s([^–-]+)$", t)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return fallback

def _to_iso(dt_value) -> str:
    try:
        if hasattr(dt_value, "tm_year"):
            d = datetime(*dt_value[:6], tzinfo=timezone.utc)
            return d.replace(microsecond=0).isoformat()
        if isinstance(dt_value, str) and dt_value.strip():
            d = dtparser.parse(dt_value)
            if not d.tzinfo:
                d = d.replace(tzinfo=timezone.utc)
            return d.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    except Exception:
        pass
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

# ---------------------------------------------------------------------
# Title keyword gate (existing behavior)
# ---------------------------------------------------------------------
def _title_matches_and_keywords(title: str):
    t = (title or "").lower()
    any_present = [k for k in (TITLE_KEYWORDS_ANY or []) if k.lower() in t]
    all_ok = all(k.lower() in t for k in (TITLE_KEYWORDS_ALL or []))
    keep = True
    if TITLE_KEYWORDS_ANY and not any_present:
        keep = False
    if TITLE_KEYWORDS_ALL and not all_ok:
        keep = False
    matched = sorted(set(any_present + (TITLE_KEYWORDS_ALL or [])))
    return keep, matched

# ---------------------------------------------------------------------
# NEW: Region inference (title-first, multi-region) + compatibility
# ---------------------------------------------------------------------
# Patterns to detect regions from TITLE (priority-ordered list later decides primary)
_REGION_PATTERNS = {
    "Singapore":   [r"\bsingapore\b", r"\bS’pore\b", r"\bSg\b", r"\bSG\b"],
    "Malaysia":    [r"\bmalaysia\b", r"\bM’sia\b", r"\bMY\b"],
    "Philippines": [r"\bphilippines\b", r"\bphilippine\b", r"\bmanila\b", r"\bPH\b"],
    "Indonesia":   [r"\bindonesia\b", r"\bjakarta\b", r"\bID\b"],
    "Vietnam":     [r"\bvietnam\b", r"\bhanoi\b", r"\bhà nội\b", r"\bho chi minh\b", r"\bhcmc\b", r"\bVN\b"],
    "Thailand":    [r"\bthailand\b", r"\bbangkok\b", r"\bTH\b"],
    # Ready to extend when needed:
    # "Cambodia":  [r"\bcambodia\b", r"\bphnom penh\b", r"\bKH\b"],
    # "Laos":      [r"\blao(s)?\b", r"\bvientiane\b", r"\bLA\b"],
    # "Myanmar":   [r"\bmyanmar\b", r"\bburma\b", r"\byangon\b", r"\bMM\b"],
    # "Brunei":    [r"\bbrunei\b", r"\bbandar seri begawan\b", r"\bBN\b"],
}

# Priority to choose a primary when multiple are detected
_REGION_PRIORITY = ["Singapore", "Malaysia", "Philippines", "Indonesia", "Vietnam", "Thailand"]

def _extract_regions_from_title(title: str):
    """
    Return 0..N regions based on title text alone (first priority).
    Hyphens / en-dashes / em-dashes are normalized to spaces so
    'Vietnam-Malaysia-Singapore' matches all three.
    """
    t_original = (title or "")
    # Normalize hyphens/dashes to spaces to restore word boundaries
    t = re.sub(r"[-–—]", " ", t_original)
    found = []
    for country, patterns in _REGION_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, t, flags=re.IGNORECASE):
                found.append(country)
                break
    # de-dup, then sort by priority
    uniq = []
    for c in found:
        if c not in uniq:
            uniq.append(c)
    prio_index = {c: i for i, c in enumerate(_REGION_PRIORITY)}
    uniq.sort(key=lambda c: prio_index.get(c, 999))
    return uniq

def _infer_regions_from_source_link(source: str, link: str):
    """Fallback to your original single-region mapping using source/link; returns [] or [one country]."""
    text = f"{source} {link}".lower()
    if "philippines" in text or ".ph" in text:
        return ["Philippines"]
    if "singapore" in text or ".sg" in text:
        return ["Singapore"]
    if "malaysia" in text or ".my" in text:
        return ["Malaysia"]
    if "indonesia" in text or ".id" in text:
        return ["Indonesia"]
    if "vietnam" in text or ".vn" in text:
        return ["Vietnam"]
    if "thailand" in text or ".th" in text:
        return ["Thailand"]
    return []

def _infer_regions_title_first(title: str, source: str, link: str):
    """
    1) Try title-based multi-region extraction.
    2) If none, fall back to source/link heuristic (0..1 region).
    3) If still none, return [] (caller assigns Global as primary).
    """
    from_title = _extract_regions_from_title(title)
    if from_title:
        return from_title
    return _infer_regions_from_source_link(source, link)

def _pick_primary_region(regions):
    """Pick one primary region for backward compatibility; default Global."""
    if not regions:
        return "Global"
    prio_index = {c: i for i, c in enumerate(_REGION_PRIORITY)}
    return sorted(regions, key=lambda c: prio_index.get(c, 999))[0]

# 🔒 Backward-compat shim (in case other modules import _infer_region)
def _infer_region(source: str, link: str) -> str:
    """Legacy signature: returns a single string. Now delegates to the new logic."""
    primary = _pick_primary_region(_infer_regions_title_first("", source, link))
    return primary

# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------
def get_news_from_rss(days_limit: int = 7) -> list:
    if not RSS_ENABLED or not RSS_FEEDS:
        return []

    since = datetime.now(timezone.utc) - timedelta(days=days_limit)
    items, seen = [], set()
    print(f"[RSS] Loaded {len(RSS_FEEDS)} feeds from config")

    for src in RSS_FEEDS:
        url = src.get("url", "") if isinstance(src, dict) else str(src)
        label = (src.get("name") if isinstance(src, dict) else None) or _source_from_url(url)
        if not url:
            continue

        feed = feedparser.parse(url, request_headers=UA)
        if feed.bozo:
            logging.warning("[RSS] BOZO on %s: %s", url, getattr(feed, "bozo_exception", "Unknown parse error"))
        if not getattr(feed, "entries", []):
            logging.warning("[RSS] EMPTY feed: %s", url)
            continue

        kept = 0
        for e in feed.entries:
            if RSS_MAX_ITEMS and kept >= RSS_MAX_ITEMS:
                break

            title = (getattr(e, "title", "") or "").strip()
            link = _canonical_url(getattr(e, "link", "") or "")
            if not title or not link or link in seen:
                continue

            # Title-keyword gate (existing behavior)
            keep, matched_keywords = _title_matches_and_keywords(title)
            if not keep:
                continue

            source_label = label or _source_from_url(link)
            # If it's a GNews link or feed, repair the source label to the real publisher
            if _is_gnews(link) or _is_gnews(url):
                source_label = _gnews_source_name(e, source_label)

            # Published time handling
            published = getattr(e, "published", None)
            published_parsed = getattr(e, "published_parsed", None)
            ts_str = _to_iso(published_parsed or published)
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except Exception:
                ts = None
            if ts and ts < since:
                continue

            # Summary: blank for GNews (to avoid duplicates/boilerplate), else trimmed
            if _is_gnews(link):
                summary = ""
            else:
                summary = (getattr(e, "summary", "") or getattr(e, "description", "") or "").strip()[:300]

            # --- Region inference (title-first, multiple allowed) ---
            regions = _infer_regions_title_first(title, source_label, link)
            primary_region = _pick_primary_region(regions)
            regions_text = ", ".join(regions) if regions else ""

            items.append({
                "Title": title,
                "Link": link,
                "Source": source_label,
                "PublishedAt": ts_str,
                "Summary": summary,
                "Topic": matched_keywords,                 # chips
                "Keywords": ", ".join(matched_keywords),   # text form

                # 🔹 New fields (multi-region support)
                "Regions": regions,                        # e.g., ["Singapore","Malaysia"]
                "Region": primary_region,                  # primary for backward compatibility
                "RegionsText": regions_text,               # "Singapore, Malaysia" (Airtable/CSV-friendly)
            })

            seen.add(link)
            kept += 1

        print(f"[RSS] {label} -> kept {kept} items (max {RSS_MAX_ITEMS})")

    return items
