# back/main.py
from dotenv import load_dotenv
load_dotenv()

import os
import re
from fastapi import FastAPI, Request
from starlette.responses import Response, JSONResponse

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

# ----- Events backend -----
from back.events_ingest import run_events_ingest
from back.supabase_events import fetch_upcoming_events

# ---------------- FastAPI App ----------------
app = FastAPI(title="ENGIE News API (Render)")

# ---------------- Security Token ----------------
BACKEND_API_TOKEN = os.getenv("BACKEND_API_TOKEN", "").strip()

# ---------------- Allowed Origins ----------------
DEFAULT_ALLOWED = (
    "https://engie-news-repo1.vercel.app,"
    "http://localhost:5173"
)

_ALLOWED = [o.strip() for o in os.getenv("ALLOW_ORIGINS", DEFAULT_ALLOWED).split(",")]

# allow wildcard subdomains of Vercel
_VERCEL_RE = re.compile(r"^https://[a-z0-9-]+\.vercel\.app$", re.I)


def _origin_ok(origin: str) -> bool:
    if not origin:
        return False
    if origin in _ALLOWED:
        return True
    if _VERCEL_RE.match(origin):
        return True
    return False


# ---------------- Unified CORS Middleware ----------------
@app.middleware("http")
async def cors_and_guard(request: Request, call_next):
    origin = request.headers.get("origin")

    # ---------------- TOKEN GUARD ----------------
    if request.method.upper() == "POST" and request.url.path.startswith("/refresh"):
        token = request.headers.get("x-backend-token")
        if BACKEND_API_TOKEN and token != BACKEND_API_TOKEN:
            return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    # ---------------- PRE-FLIGHT (OPTIONS) ----------------
    if request.method.upper() == "OPTIONS":
        headers = {}
        if _origin_ok(origin):
            headers = {
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
                "Access-Control-Allow-Headers": request.headers.get(
                    "access-control-request-headers", "*"
                ),
                "Access-Control-Allow-Credentials": "true",
                "Vary": "Origin",
            }
        return Response(status_code=200, headers=headers)

    # ---------------- NORMAL REQUEST ----------------
    response = await call_next(request)

    # Attach CORS headers on valid origins
    if _origin_ok(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"

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
