# back/main.py
from dotenv import load_dotenv
load_dotenv()  # finds .env in root by default

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
# Stubs you created:
#   back/events_ingest.py -> run_events_ingest()
#   back/supabase_events.py -> fetch_upcoming_events()
from back.events_ingest import run_events_ingest
from back.supabase_events import fetch_upcoming_events

app = FastAPI(title="ENGIE News API (Local)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev origin
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- Health ----------------
@app.get("/health")
def health():
    return {"status": "ok", "backend": BACKEND_NAME}

# ---------------- Articles (news) ----------------
@app.get("/articles")
def articles():
    """
    Return news articles from the current backend (Supabase/Airtable reader).
    """
    print("📰  Fetching articles from", BACKEND_NAME)
    return get_articles()

@app.post("/refresh")
def refresh():
    """
    Fetch RSS news -> filter -> write to backend (Supabase/Airtable).
    """
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
    """
    Return upcoming energy events (starts_on >= today), ordered asc.
    Reads directly from Supabase via service role on the server.
    """
    print("📅  Fetching upcoming events (Supabase)")
    events = fetch_upcoming_events()
    print(f"✅  Returned {len(events)} upcoming events.")
    return events

@app.post("/refresh/events")
def refresh_events():
    """
    Run the events ETL (Reuters -> normalize -> upsert to Supabase),
    then return simple stats for the UI.
    """
    print("🔄  Running Events ETL (Reuters -> Supabase)...")
    stats = run_events_ingest()
    print(f"✅  Events ETL done. Stats: {stats}")
    return {"ok": True, "stats": stats}
