# back/main.py
# back/main.py
from back.app import init_guard_middleware
init_guard_middleware(app)
from dotenv import load_dotenv
load_dotenv()

import os, re
from fastapi import FastAPI
from starlette.responses import Response

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

# ---------------- CORS (explicit, works with Vercel + Render) ----------------
# ALLOW_ORIGINS env (comma separated), plus wildcard for *.vercel.app
_ALLOWED = [
    o.strip() for o in os.getenv(
        "ALLOW_ORIGINS",
        "https://engie-news-repo3-0.vercel.app,http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
]
_VERCL_RE = re.compile(r"^https://[a-z0-9-]+\.vercel\.app$", re.I)

def _origin_ok(origin: str) -> bool:
    if not origin:
        return False
    if origin in _ALLOWED:
        return True
    if _VERCL_RE.match(origin):
        return True
    return False

@app.middleware("http")
async def cors_middleware(request, call_next):
    origin = request.headers.get("origin", "")
    # Handle CORS preflight explicitly
    if request.method.upper() == "OPTIONS":
        headers = {}
        if _origin_ok(origin):
            headers.update({
                "Access-Control-Allow-Origin": origin,
                "Vary": "Origin",
                "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
                "Access-Control-Allow-Headers": request.headers.get(
                    "access-control-request-headers", "*"
                ),
                # We don't use cookies; avoid credential headaches
                "Access-Control-Allow-Credentials": "false",
                "Access-Control-Max-Age": "600",
            })
        return Response(status_code=200, headers=headers)

    # Normal requests: add CORS headers if origin allowed
    response = await call_next(request)
    if _origin_ok(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Credentials"] = "false"
    return response

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
