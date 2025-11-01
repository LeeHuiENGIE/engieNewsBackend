# back/main.py
# back/main.py
from dotenv import load_dotenv
load_dotenv()  # finds .env in root by default

import os
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

# ---------------- Config Imports ----------------
from .config import USE_SUPABASE, DAYS_LIMIT
from .fetch_news import fetch_filtered_news

# ----- News backend (existing) -----
if USE_SUPABASE:
    from .supabase_reader import get_articles
    from .supabase_writer import write_to_supabase as write_to_backend
    BACKEND_NAME = "supabase"
else:
    from .airtable_reader import get_articles
    from .airtable_writer import write_to_airtable as write_to_backend
    BACKEND_NAME = "airtable"

# ----- Events backend (new) -----
from back.events_ingest import run_events_ingest
from back.supabase_events import fetch_upcoming_events

# ---------------- FastAPI App ----------------
app = FastAPI(title="ENGIE News API (Render)")

# ---------------- CORS ----------------
# Allow your Vercel prod site, Vercel preview URLs (*.vercel.app), and local dev.
# You can also override/append via the ALLOW_ORIGINS env (comma-separated).
DEFAULT_ALLOWED = [
    "https://engie-news-repo3-0.vercel.app",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

ENV_ALLOWED = [o.strip() for o in os.getenv("ALLOW_ORIGINS", "").split(",") if o.strip()]
ALLOWED = list(dict.fromkeys(DEFAULT_ALLOWED + ENV_ALLOWED))  # de-dup while preserving order

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED,                 # explicit origins (localhost + prod)
    allow_origin_regex=r"https://.*\.vercel\.app$",  # preview deployments
    allow_credentials=False,               # we don't use cookies
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Explicitly return for preflight so proxies never block it
@app.options("/{full_path:path}")
def preflight(full_path: str):
    return Response(status_code=204)

# ---------------- Health ----------------
@app.get("/health")
def health():
    return {"status": "ok", "backend": BACKEND_NAME}

# ---------------- Articles (news) ----------------
@app.get("/articles")
def articles():
    """Return news articles from the current backend (Supabase/Airtable reader)."""
    print("📰  Fetching articles from", BACKEND_NAME)
    return get_articles()

@app.post("/refresh")
def refresh():
    """Fetch RSS news → filter → write to backend (Supabase/Airtable)."""
    print("🔄  Fetching new RSS articles...")
    news = fetch_filtered_news(days_limit=DAYS_LIMIT)
    print(f"✅  Fetched {len(news)} items.")

    if BACKEND_NAME == "supabase":
        print("☁️  Writing to Supabase...")
        written, errs, sample = write_to_backend(news)
        print(f"✅  Written {written} rows. Errors: {len(errs)}")
        if errs:
            print("Example error:", errs[0])
        return {
            "status": "updated",
            "fetched": len(news),
            "written": written,
            "backend_errors": errs,
            "backend_sample": sample,
        }
    else:
        print("✈️  Writing to Airtable...")
        write_to_backend(news)
        print("✅  Done writing to Airtable.")
        return {"status": "updated", "fetched": len(news)}

# ---------------- Events (new) ----------------
@app.get("/events")
def list_events():
    """Return upcoming energy events from Supabase."""
    print("📅  Fetching upcoming events (Supabase)")
    events = fetch_upcoming_events()
    print(f"✅  Returned {len(events)} upcoming events.")
    return events

@app.post("/refresh/events")
def refresh_events():
    """Run the events ETL (Reuters → normalize → upsert to Supabase)."""
    print("🔄  Running Events ETL (Reuters → Supabase)...")
    stats = run_events_ingest()
    print(f"✅  Events ETL done. Stats: {stats}")
    return {"ok": True, "stats": stats}
