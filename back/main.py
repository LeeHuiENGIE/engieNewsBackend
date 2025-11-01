# back/main.py
# back/main.py
from dotenv import load_dotenv
load_dotenv()

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

# ---------------- CORS (final stable config) ----------------
DEFAULT_ALLOWED = [
    "https://engie-news-repo3-0.vercel.app",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
ENV_ALLOWED = [o.strip() for o in os.getenv("ALLOW_ORIGINS", "").split(",") if o.strip()]
ALLOWED = list(dict.fromkeys(DEFAULT_ALLOWED + ENV_ALLOWED))  # remove dupes

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED,
    # ⚠️ Removed regex — this was breaking preflights on Render
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure OPTIONS always replies with 204
@app.options("/{rest_of_path:path}")
def preflight_handler(rest_of_path: str):
    return Response(status_code=204)

# ---------------- Health ----------------
@app.get("/health")
def health():
    return {"status": "ok", "backend": BACKEND_NAME}

# ---------------- Articles (news) ----------------
@app.get("/articles")
def articles():
    print("📰 Fetching articles from", BACKEND_NAME)
    return get_articles()

@app.post("/refresh")
def refresh():
    print("🔄 Fetching new RSS articles...")
    news = fetch_filtered_news(days_limit=DAYS_LIMIT)
    print(f"✅  Fetched {len(news)} items.")

    if BACKEND_NAME == "supabase":
        print("☁️ Writing to Supabase...")
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
        print("✈️ Writing to Airtable...")
        write_to_backend(news)
        return {"status": "updated", "fetched": len(news)}

# ---------------- Events ----------------
@app.get("/events")
def list_events():
    print("📅 Fetching upcoming events (Supabase)")
    events = fetch_upcoming_events()
    print(f"✅ Returned {len(events)} upcoming events.")
    return events

@app.post("/refresh/events")
def refresh_events():
    print("🔄 Running Events ETL (Reuters → Supabase)...")
    stats = run_events_ingest()
    print(f"✅ Events ETL done. Stats: {stats}")
    return {"ok": True, "stats": stats}
