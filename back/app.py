# app.py — backend entrypoint for Render

import os
from fastapi import Request
from starlette.responses import Response

from back.main import app  # import your FastAPI app from back/main.py

_TOKEN = os.getenv("BACKEND_API_TOKEN", "").strip()

@app.middleware("http")
async def guard_refresh(request: Request, call_next):
    # Always let OPTIONS (preflight) through
    if request.method.upper() == "OPTIONS":
        return await call_next(request)

    path = request.url.path

    # Allow public access if no token is configured
    if path.startswith("/refresh"):
        if not _TOKEN:
            return await call_next(request)

        # Token protection if you ever enable it
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            incoming = auth[7:].strip()
        else:
            incoming = request.headers.get("x-backend-token", "")

        if incoming != _TOKEN:
            return Response(status_code=401)

    return await call_next(request)
