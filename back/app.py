# app.py (root of the Render service)
import os
from fastapi import Request
from starlette.responses import JSONResponse

from back.main import app as _app  # import your FastAPI app

TOKEN = os.getenv("BACKEND_API_TOKEN", "").strip()

@_app.middleware("http")
async def guard_refresh(request: Request, call_next):
    # Only protect the two refresh endpoints
    if request.url.path.startswith("/refresh"):
        got = request.headers.get("x-backend-token", "")
        if not TOKEN or got != TOKEN:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return await call_next(request)

# Expose `app` for Uvicorn
app = _app
