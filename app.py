# app.py (lives in api_backend/, sibling of requirements.txt)
import os
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
from back.main import app as _app  # reuse your existing FastAPI app & routes

app = _app  # expose as "app" for Render

# --- CORS (production) ---
# Comma-separated list of allowed origins, e.g.:
# ALLOW_ORIGINS=https://your-frontend.vercel.app,https://localhost:5173
ALLOW_ORIGINS = [
    o.strip() for o in os.getenv("ALLOW_ORIGINS", "").split(",") if o.strip()
]
if ALLOW_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOW_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# --- Simple auth guard for refresh endpoints ---
API_TOKEN = os.getenv("BACKEND_API_TOKEN", "").strip()
PROTECTED_PATHS = {"/refresh", "/refresh/events"}

@app.middleware("http")
async def guard_refresh(request: Request, call_next):
    if API_TOKEN and request.url.path in PROTECTED_PATHS:
        auth = request.headers.get("authorization") or request.headers.get("Authorization") or ""
        token = auth.split("Bearer ", 1)[1].strip() if auth.startswith("Bearer ") else ""
        if token != API_TOKEN:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return await call_next(request)
